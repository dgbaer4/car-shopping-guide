# EPA–NHTSA vehicle reconciliation

This development-time process evaluates US-market Toyota, Nissan, Honda, Hyundai and Kia EPA configurations from model years 2021–2026. It keeps EPA configuration IDs and descriptions and NHTSA VehicleIds and descriptions intact. The static catalog receives ratings only after an association has been reviewed against government evidence.

## What the source audit found

The preserved Stage A artifact contains 1,406 EPA configurations and 1,101 distinct year/make/model query groups. It yielded 283 NHTSA VehicleIds, 774 empty lookup groups and 113 HTTP 400 errors. Every HTTP 400 group contained a slash in its EPA model label, and all 113 slash-containing groups returned HTTP 400 in that run. Of the 774 empty lookup groups, 569 contained an explicit drivetrain token (AWD, FWD, RWD, 4WD or 2WD). A direct spot check reproduced the slash error for the 2021 Accord Sport/Touring and found a published variant under Accord. The 2021 CR-V AWD query returned an empty result while CR-V returned separate AWD and FWD variants. These observations establish naming failures in the sampled cases. The capture leaves remaining empty groups individually unresolved. [Preserved artifact](https://github.com/dgbaer4/car-shopping-guide/actions/runs/45507136855/artifacts/14975252454) · [Accord variants](https://api.nhtsa.gov/SafetyRatings/modelyear/2021/make/HONDA/model/Accord) · [CR-V variants](https://api.nhtsa.gov/SafetyRatings/modelyear/2021/make/HONDA/model/CR-V)

A comparison against the live NHTSA make/year model indexes for five makes in 2021, 2023 and 2026 found identical normalized labels for 103 of 544 distinct EPA query groups. The other 441 groups lacked an exact index label in this sample. Examples include Prius AWD XLE/LTD versus PRIUS (drivetrain and trim), Civic 5Dr versus CIVIC HATCHBACK (body), Elantra Hybrid Blue versus ELANTRA HEV (powertrain abbreviation and trim), and GR 86 versus GR86 (spacing). The 2023 Nissan index lists separate 40 kWh and 60 kWh Leaf variants. The 2022 and 2023 Prius variant listings use the same body and drivetrain descriptors but have different VehicleIds, so the text alone cannot establish continuity through a model-year or generation change. [EPA data](https://www.fueleconomy.gov/feg/download.shtml) · [2023 Toyota index](https://api.nhtsa.gov/SafetyRatings/modelyear/2023/make/TOYOTA) · [2023 Honda index](https://api.nhtsa.gov/SafetyRatings/modelyear/2023/make/HONDA) · [2023 Hyundai index](https://api.nhtsa.gov/SafetyRatings/modelyear/2023/make/HYUNDAI) · [2023 Nissan index](https://api.nhtsa.gov/SafetyRatings/modelyear/2023/make/NISSAN) · [2022 Prius variants](https://api.nhtsa.gov/SafetyRatings/modelyear/2022/make/TOYOTA/model/PRIUS) · [2023 Prius variants](https://api.nhtsa.gov/SafetyRatings/modelyear/2023/make/TOYOTA/model/PRIUS)

The Stage A importer stores the original EPA lookup label as the NHTSA model. All 283 rows have this query-only identity. Forty-four have all four rating values null, and the importer collapses source statuses into null. All 1,406 EPA rows lack a structured body field. The preserved snapshot therefore supports a family review queue and gives no configuration-level approvals. A separate spot check of seven native 2023 model endpoints returned 10 variants across all five makes and produced 12 EPA candidates (four single-candidate and eight ambiguous configurations). That spot check included separate Leaf battery variants and Sportage HEV drivetrains. It was an interface check with partial coverage and no reviewed associations. [2023 Sportage HEV variants](https://api.nhtsa.gov/SafetyRatings/modelyear/2023/make/KIA/model/SPORTAGE%20HEV)

The captured baseline and results with the 114-alias register are recorded in the [coverage report](reconciliation/nhtsa-coverage.json). All counts below are EPA configurations.

| Classification | Preserved data |
| --- | ---: |
| Verified configuration match | 0 |
| Verified rating applicability | 0 |
| Model-family match requiring review | 234 |
| Ambiguous | 98 |
| Unmatched | 1,074 |
| No published safety rating | 0 |
| **Total** | **1,406** |

The [manual review CSV](reconciliation/nhtsa-manual-review.csv) contains all 1,101 EPA lookup groups, with the EPA configuration IDs and candidate VehicleIds. With exact normalized labels and no aliases, 304 configurations had candidates. Aliases raised that to 332. The classifications describe the evidence in the input snapshot. An unmatched configuration may still have a published NHTSA rating.

## Matching and evidence

The reconciler lowercases and tokenizes labels while preserving token boundaries. It checks exact aliases by source, make and model year. Each exception in the [version 1 register](../data/vehicle-reconciliation-mappings.v1.json) has the original model label, a canonical family, the reason, a source URL and the access date. The register covers selected observed exceptions. Raw labels remain available for configuration review. No fuzzy matching or automatic suffix removal runs in the catalog builder.

| Classification | Required evidence | Catalog safety ratings |
| --- | --- | --- |
| `verified_configuration_match` | Reviewed EPA ID and NHTSA VehicleId with same make, model year and canonical family, matching known material attributes, and known powertrain, drivetrain and body on both sides | Reviewed NHTSA rating fields |
| `verified_rating_applicability` | Reviewed association for one EPA ID, with an NHTSA statement or record applying the listed rating categories to that configuration and resolving material gaps; known conflicts block publication | Reviewed NHTSA rating fields |
| `model_family_match_requires_review` | One family candidate or a reviewed target missing from the input | Null |
| `ambiguous` | Multiple candidates without a valid reviewed association | Null |
| `unmatched` | Zero candidates in the supplied input and no reviewed association | Null |
| `no_published_safety_rating` | Reviewed association with all four categories explicitly reported unrated for the applicable NHTSA variant | Null |

NHTSA assigns API ratings to a VehicleId for a specific variant. Its safety-labeling rule describes written notification of a rating or its continued applicability for a different model year and accounts for production changes and optional retesting. This project requires a same-year native VehicleId even when NHTSA carries a rating forward. Trim, build date, generation, battery, steering or restraint differences should be reviewed whenever they affect applicability. Each reviewed association enumerates the published categories it covers, so a newly published category triggers re-review. NHTSA’s ratings FAQ explains its per-category “Not Rated” label. [NHTSA API documentation](https://www.nhtsa.gov/nhtsa-datasets-and-apis) · [NCAP safety labeling rule](https://www.nhtsa.gov/document/final-rule-new-car-assessment-program-ncap-safety-labeling) · [NHTSA ratings FAQ](https://www.nhtsa.gov/ratings)

The reviewer records a government evidence URL, access date, reviewer identifier, covered categories and a statement identifying the underlying evidence and configuration limits. Cite the exact vehicle page, test report, agency applicability record or equivalent NHTSA evidence. For an applicability association, the statement must explain why the ratings apply to the specific EPA configuration and account for any material missing attributes. A generic agency URL, a shared name or equal star values provides insufficient evidence. Code validates IDs, source URLs, years, configurations, scope and rating values. The reviewer verifies the cited source content. The initial register contains family aliases and zero applicability approvals.

## Acquisition handoff

Keep the Stage A envelope with a `records` array and optional `unmatched`, `errors` and `scope`. Preserve unsuccessful lookups for reporting and distinguish empty responses from API or transformation failures. Each row carries `vehicleId`, `make`, `year`, `model`, `description`, `ratings`, `source` and `accessed`. IDs are positive decimal integers or their canonical string equivalents. Ratings use the four keys `overall`, `frontal`, `side` and `rollover` with integer stars from 1 to 5 or null. The source must be the NHTSA rating detail URL for that VehicleId, with an ISO access date.

For review-ready rows, provide the following additional fields. Retain original listing descriptions and source provenance through transformation.

- `nativeIdentity` contains `make`, `year`, `model` and `source`. Use the identity from a NHTSA-native list joined to the same VehicleId. For the API, use the model variant-list URL. A NHTSA-hosted bulk source may also furnish identity. Retain the request label separately if useful.
- `configuration` provides evidence-backed `power`, `drivetrain` and `body`, with `trim`, `battery` and `generation` where known. Use the catalog’s powertrain labels. The reconciler handles common full-name drivetrain equivalents and keeps AWD and 4WD distinct. Unknown attributes may be omitted or null. Independently reviewed enrichment can add configuration attributes when the acquisition feed lacks them.
- `publicationStatus: "not_rated"` is reserved for explicit unrated statuses for all four categories on that variant. Preserve raw category statuses and details where possible. Empty lookups, failed responses and unknown normalized values leave the status unconfirmed.

In each association, `configuration.epa` snapshots `model`, `trim`, `power`, `drivetrain`, `body`, `battery` and `generation` with nulls for missing fields. `configuration.nhtsa` snapshots the target’s structured configuration, and `configuration.nhtsaModel` and `configuration.description` pin its source model and description. Use `epaId`, `vehicleId`, the classification string shown in the table and `evidence` with `url`, `accessed`, `reviewer`, `statement` and `ratingFields`. Each EPA ID has at most one association. Additional EPA IDs sharing a VehicleId require their own applicability evidence. An empty legacy register (`{}`) still works for Stage A. Existing nonempty legacy approvals require fresh review and migration to version 1.

## Integration and verification

1. Download the preserved files or use a versioned acquisition snapshot. Keep partial errors alongside successful records. Generate the reconciliation report and review queue.
2. Inspect ambiguous groups and new source-native variants. Add evidence-backed aliases for names and individual reviewed associations for rating applicability. Have the acquisition specialist supply source-native identity and status without guessing configuration attributes.
3. Build a staging catalog and check both overall and per-make/year coverage. Confirm each populated rating traces to its approved VehicleId, and review missing approved targets and changes in rating categories before any catalog promotion.
4. Run the Python reconciliation and existing Node tests. Validate the stage output against the existing v0.3 schema. The catalog uses the existing optional `safetyRatings` field with either a ratings object or null. The current schema allows it as an additional property, and the builder validates the ratings directly.

```sh
python tools/reconcile_vehicles.py epa.json safety.json data/vehicle-reconciliation-mappings.v1.json reconciliation.json --review-csv manual-review.csv
python tools/build_catalog.py epa.json safety.json data/vehicle-reconciliation-mappings.v1.json catalog.json coverage.json
python -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.mjs
```

## Expanded development catalog for CSG-A02.1

The expanded build uses the original 1,406 EPA configurations and Agent 1’s immutable `2026-11-24.v1.1` safety snapshot at commit `a4601cbc2945f4ea1d3babd059857fa2f0e64964`. The reconciler consumed all 916 variant records from its `nhtsa-safety/1.1` envelope, with native discovery and detail identities, raw category statuses and structured configuration evidence. There are 791 variants with stars and 125 explicitly unrated variants. The native Toyota Tundra Hybrid ISOdynamic seat path for model year 2026 has one unresolved HTTP 400 in that snapshot. [Agent 1 PR](https://github.com/dgbaer4/car-shopping-guide/pull/1) · [Pinned safety input](https://github.com/dgbaer4/car-shopping-guide/blob/a4601cbc2945f4ea1d3babd059857fa2f0e64964/data/development/nhtsa-safety-2026-11-24.v1.1.json.gz) · [Acquisition interface at c1376aa](https://github.com/dgbaer4/car-shopping-guide/blob/c1376aa342c43cde2100c645b47d53f161cc598e/docs/nhtsa-acquisition.md#output-contract-for-reconciliation)

| EPA result | Original capture | Expanded development build |
| --- | ---: | ---: |
| Verified configuration match | 0 | 43 |
| Verified rating applicability across configurations | 0 | 0 |
| Confirmed unrated | 0 | 11 |
| Model-family match requiring review | 234 | 316 |
| Ambiguous | 98 | 437 |
| Unmatched | 1,074 | 599 |
| **Published safety-rating coverage** | **0 / 1,406** | **43 / 1,406 (3.1%)** |

The 43 rated configurations cover Toyota (17), Kia (10), Nissan (8), Honda (7) and Hyundai (1). They include 16 gasoline, 16 traditional hybrid, five plug-in hybrid and six fully electric configurations. The [expanded coverage report](reconciliation/nhtsa-coverage-expanded.json) includes all make/year/powertrain intersections, the original and expanded discovery baselines, verified counts and frozen input digests. The [expanded manual review queue](reconciliation/nhtsa-manual-review-expanded.csv) lists unresolved EPA IDs and possible VehicleIds. The [generated catalog](../data/development/vehicle-catalog-2026-11-24.v2.json.gz) is a development artifact.

### Evidence review and automation

The v2 register contains 418 exact source aliases and 54 reviewed pairs. The [reviewed evidence packet](../data/development/nhtsa-reviewed-evidence.v1.json) links the EPA detail URL for each EPA ID to the NHTSA variant listing and rating detail, including source descriptions, supported attributes, literal rating statuses, pinned star values and the review statement. Agent 2 reviewed the scope of each pair. The utility performed live machine checks of the EPA configuration signature, native listing, NHTSA detail identity and raw ratings for all 54 pairs. These records have no independent human sign-off.

The review prioritized configurations with a uniquely scoped NHTSA native listing and one EPA entry for the covered configuration. It compared named powertrain and drivetrain, reconciled explicit body descriptions with EPA vehicle classes and kept model year and battery boundaries. Where an EPA passenger-car size class was generic, the same-year NHTSA variant listing supplied the body detail for the unique named configuration. This includes the explicitly named 40 kWh Nissan Leaf hatchback, Prius Prime hatchback and Nissan Maxima sedan. This interpretation and the original EPA classification are recorded together in the evidence packet. EPA efficiency classes and NHTSA body descriptions use different vocabularies. Rows with a contradictory known drivetrain or multiple covering release, trim or battery records stay unresolved.

The validator rejects conflicting discovery and detail identities, changed rating values or category availability, contradictory configuration evidence, wrong source URLs and competing native variants without a known material distinction. It requires all four literal NHTSA `Not Rated` categories to confirm an unrated v2 pair. It also preserves the version 1 and empty-register workflows for the original input. Combining old query-only rows with active v2 approvals requires a fresh build with the matching evidence inputs.

The generator compiles reviewed evidence deterministically. Its optional live check reads government endpoints and compares them with pinned values. It never updates an approval from a changed response. Cross-configuration approvals require scoped agency evidence and one explicit EPA ID per output association. An agency scope can be recorded for several pairs and compiled together. This pass found insufficient authoritative scope to transfer stars to an additional EPA ID with a differing trim or configuration. For example, the Prologue AWD Elite and Touring rows remain unresolved, the 2023 Kicks has release-specific variants, and the 2024–2025 Kona Electric acquisition describes RWD while the EPA scope is FWD.

### Reproduce and integrate

Download the preserved EPA JSON and decompress the pinned acquisition snapshot to `safety.json`. The v2 mapping file supplies the aliases to the generator. The generator rebuilds its associations from the separately pinned evidence packet.

```sh
python tools/generate_reconciliation_associations.py epa.json safety.json \
  data/vehicle-reconciliation-mappings.v2.json data/development/nhtsa-reviewed-evidence.v1.json \
  rebuilt-mappings.json --verify-live
cmp data/vehicle-reconciliation-mappings.v2.json rebuilt-mappings.json
python tools/build_catalog.py epa.json safety.json rebuilt-mappings.json catalog.json coverage.json
python tools/reconcile_vehicles.py epa.json safety.json rebuilt-mappings.json reconciliation.json \
  --review-csv manual-review.csv
gzip -n -c -9 catalog.json > catalog.json.gz
```

For controlled integration, pin both source digests from the coverage report, regenerate offline or recheck live with `--verify-live`, run the tests and schema validation, and review the coverage diff before promoting a catalog. If a source changes a published category, star value or configuration, review the scope and update the evidence packet before rebuilding.

Further coverage depends chiefly on authoritative trim, build-date, battery and restraint applicability. Allow roughly two to four engineering days for a focused second batch of common passenger vehicles if manufacturer or NHTSA configuration records are obtainable. A broad review of the unresolved queue would take longer and has no defensible coverage estimate until those sources are confirmed.

## CSG-A02.2 coverage and applicability review

The [CSG-A02.2 report](reconciliation/csg-a02.2.md) documents the development catalog's increase to 127 rated configurations, its source checks and remaining gaps, and the compact independent-review sample.
