# NHTSA safety-rating acquisition

CSG-A01 starts at commit `3d544495a251e1a73d0e7f82f9e49cf7874e1032`. Acquisition runs during catalog maintenance. The default scope covers the five priority makes in `data/acquisition-priorities.json` and US model years 2021–2026. It includes every model NHTSA lists within that scope, regardless of powertrain. A vehicle’s absence from the API does not establish whether NHTSA tested it.

## Source and diagnosis

NHTSA's datasets page describes NCAP crashworthiness and lists official Safety Ratings API discovery and detail endpoints. The endpoint at `/SafetyRatings` returns a model-year index, not a bulk set of variant ratings. The datasets page describes NCAP as raw data and directs readers to its API. We did not verify a bulk download with equivalent current coverage, native IDs, and published variant ratings. The importer therefore uses the documented Safety Ratings API, with one public HTTPS request at a time and no credentials. [NHTSA datasets and APIs](https://www.nhtsa.gov/nhtsa-datasets-and-apis) · [Live year index](https://api.nhtsa.gov/SafetyRatings?format=json)

The [first run's artifact](https://github.com/dgbaer4/car-shopping-guide/actions/runs/45507136855/artifacts/14975252454) contains 1,406 EPA configurations, 283 safety variants, 774 unmatched group queries, and 113 errors. Every error was HTTP 400, and every affected EPA model string contained a slash. The old importer URL-encoded each string and retried those permanent errors. A live request for EPA's `Accord Hybrid Sport/Touring` reproduced HTTP 400 even with the slash encoded. EPA's `Camry Hybrid LE` returned HTTP 200 with zero results, while the discovered NHTSA label `CAMRY HYBRID` returned one variant for 2024. These checks establish two failure modes in the old input strategy. They do not establish the cause of each empty group. [Rejected Honda query](https://api.nhtsa.gov/SafetyRatings/modelyear/2021/make/Honda/model/Accord%20Hybrid%20Sport%2FTouring?format=json) · [Empty Toyota query](https://api.nhtsa.gov/SafetyRatings/modelyear/2024/make/Toyota/model/Camry%20Hybrid%20LE?format=json) · [Native Toyota query](https://api.nhtsa.gov/SafetyRatings/modelyear/2024/make/TOYOTA/model/CAMRY%20HYBRID?format=json)

## Run and resume

From the repository root, with Python 3.10 or later:

```sh
python tools/import_nhtsa.py build/safety.json \
  --report build/nhtsa-coverage.json --cache build/nhtsa-cache
```

Repeat `--year` and `--make` to select a narrower scope. `--seconds` sets the network budget, with a default of 2,400 seconds. Exit code 0 means all discovered queries were resolved successfully or returned an explicit empty result. Exit code 2 means the output is partial. Unexpected local failures, such as filesystem errors, fail the command. Progress is logged after each queried make and year. The utility atomically replaces the JSON files at each progress checkpoint and on normal completion or Ctrl+C.

The importer traverses year → native make → native model → listed variant → native `VehicleId` detail. It validates each response before caching, checks that a detail row matches the requested ID, year, and make, and preserves discovery labels for IDs found under multiple model queries. The client uses a 12-second socket timeout, at least 300 ms between request starts, and at most three attempts for connection issues, timeouts, and selected transient HTTP responses. For 429 and other transient HTTP responses it honors `Retry-After` when present, subject to the run budget. Permanent HTTP errors and invalid responses are reported after one attempt.

Rerun the same command with the same cache to resume. Validated responses, including explicit empty results, are stored atomically under `CACHE/v1/`, keyed by URL. Successful entries keep their original acquisition date. Failed, deferred, and invalid responses are not cached. A failed run can rebuild its output from disk even if an interruption occurred between output checkpoints. Use a separate cache directory for a fresh snapshot, since model listings and ratings can change. Narrow runs can warm the same cache before a full run.

## Output contract for reconciliation

The JSON document uses `schemaVersion: "nhtsa-safety/1.0"`. The separate coverage file contains the same schema version, coverage fields, unsupported entries, and errors.

| Field | Meaning |
| --- | --- |
| `records[]` | One row per native `vehicleId`, stored as a decimal string. Core fields are `year`, project-cased `make`, NHTSA `model`, `description`, four-key `ratings`, detail URL `source`, and UTC acquisition date `accessed` in ISO format. |
| `records[].ratings` | `overall`, `frontal`, `side`, and `rollover`. Values are integers from 1–5 or null. |
| `records[].nativeRatings` | Star-rating fields returned by NHTSA, keyed by the original API field name, including available subratings. Unpublished or non-star values are null. See the cached response for original literals. |
| `records[].configuration` | Available NHTSA stability control and warning-system fields. Body and drivetrain wording remain in the native description. |
| `records[].status` | `rated` means at least one published star rating. `unrated` means a valid detail response contained no published star rating. `detail_unavailable` means discovery listed the ID but its detail query returned an empty result. |
| `records[].discovery`, `pendingVariants[]` | Discovery context includes year, make, native model label, native variant description, listing URL and acquisition date. A pending variant has a native ID and discovery context but its detail request failed or was deferred. |
| `coverage` | Requested scope, completion flags, totals, per-year/make results, request counters, and errors grouped by status. `complete` describes query resolution for this scope, not market-wide coverage or readiness for production use. |
| `unsupported[]` | Empty successful API responses and makes missing from the year discovery response. |
| `errors[]` | Stage, available identifiers, source URL, status, HTTP status, attempts and reason. Statuses include transient failure, permanent failure, invalid response, deferred and interrupted. |
| `unmatched` | Legacy array retained empty. EPA reconciliation owns this information. |

The importer keeps the old builder's record field names. The CLI changes from `EPA_INPUT SAFETY_OUTPUT` to `SAFETY_OUTPUT --cache CACHE` because EPA is unnecessary for discovery. To integrate, use a complete snapshot and pass the reconciliation specialist’s reviewed mapping file to the existing builder. Map only IDs whose provenance and configuration you verified independently. For a partial run, keep `safety.json`, `nhtsa-coverage.json`, and the cache for resumption. The workflow builds a separate EPA-only `catalog-incomplete.json` with zero applied mappings and labels the catalog, coverage, and artifact as development-only. The original builder still rejects safety inputs with unresolved errors.

## Workflow verification

The proposed workflow uses checkout v5, setup-python v6, cache v5, and upload-artifact v6. The published action manifests specify the Node.js 24 runtime for these versions. It restores successful responses across runs, handles importer exit code 2 as a warning, and uploads the independently reported acquisition coverage and explicitly incomplete development build. [Checkout](https://github.com/actions/checkout/blob/v5/action.yml) · [Setup Python](https://github.com/actions/setup-python/blob/v6/action.yml) · [Cache restore](https://github.com/actions/cache/blob/v5/restore/action.yml) · [Artifact upload](https://github.com/actions/upload-artifact/blob/v6/action.yml)

Run the controlled tests with:

```sh
python -m unittest discover -s tests -p test_import_nhtsa.py
node --test tests/*.test.mjs
```

When an owner authorizes remote verification, dispatch the workflow explicitly against the review branch and use the new run ID to inspect results:

```sh
gh workflow run catalog-acquisition.yml --repo dgbaer4/car-shopping-guide \
  --ref feature/nhtsa-acquisition
gh run list --repo dgbaer4/car-shopping-guide --workflow catalog-acquisition.yml \
  --branch feature/nhtsa-acquisition
gh run watch RUN_ID --repo dgbaer4/car-shopping-guide --exit-status
gh run download RUN_ID --repo dgbaer4/car-shopping-guide \
  --name stage-a-development-only --dir build/actions-verification
```

## Observed verification

The live run traversed all 30 requested year-and-make pairs, enumerating
582 native model labels and acquiring 916 variant records.
Of those, 791 had a published star rating and 125
had detail responses with no published stars. The run had 0
unavailable details, 0 empty or unlisted queries, and 1
permanent HTTP failure. The run retained 283 of the first artifact’s
283 distinct safety IDs. These counts measure native acquisition coverage.
EPA configuration coverage depends on independently reviewed reconciliation.

The 2026 Toyota discovery response lists
`TUNDRA HYBRID W/ ISODYNAMIC PERFORMANCE SEAT`. The official model route
returns HTTP 400 for that native label with the slash encoded. The importer
attempted it once in each run, retained the other models and variants, and
marked the snapshot incomplete. No alternate model association was assigned.
[NHTSA model listing](https://api.nhtsa.gov/SafetyRatings/modelyear/2026/make/TOYOTA?format=json) · [Failing model route](https://api.nhtsa.gov/SafetyRatings/modelyear/2026/make/TOYOTA/model/TUNDRA%20HYBRID%20W%2F%20ISODYNAMIC%20PERFORMANCE%20SEAT?format=json)

| Model year | Variant records |
| --- | ---: |
| 2021 | 139 |
| 2022 | 148 |
| 2023 | 153 |
| 2024 | 164 |
| 2025 | 158 |
| 2026 | 154 |

The acquisition used responses dated 2026-11-24 through 2026-11-24 UTC.
The full run resumed after an interrupt and made 1,039
live requests with 495 cache hits. A second full replay
reused 1,533 cached responses, reproduced all
records exactly, and attempted only the unresolved Toyota request. The [captured coverage and error
report](nhtsa-acquisition-verification.json) records the resumed run. The generated
`safety.json` has SHA-256 `a3efa74dcfd41ef09aa99c8ee06838ec4adbcdf19947e6bc80800788d88e7cdf`.

All five Python tests and all 17 existing Node tests passed. Actionlint v1.7.11
passed. A local execution of the incomplete-build step using the first run’s
1,406 EPA configurations produced an explicitly incomplete development catalog
with zero mapped safety ratings. GitHub Actions execution remains to be verified
by an authorized dispatch.
