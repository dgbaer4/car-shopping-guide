# Car Shopping Guide v0.3 integration report

**2026-11-25 · Development build for independent review. Staging approval is pending.**

## Integration history

| Change | Commit |
| --- | --- |
| PR #4, NHTSA acquisition, already merged at the starting tip | `fa6231ed8c3d11d123defffface87d0427ecfa6a` |
| PR #5 source head, vehicle reconciliation | `152b1bb176e6963d716950f89d4a82d07af3ff9b` |
| PR #5 integration merge | `a047f0494ae67a1f2c77174cd14a88c291eae62b` |
| PR #6 source head, vehicle equipment acquisition | `51d28e334923d8ddb6e0d2f391100b988fea62f2` |
| PR #6 integration merge | `f5995b42f5f3f7179501b7e63440d525afaa911a` |
| Catalog, engine, browser and regression changes tested below | `23bc0a19f1e61378c028d30a26ec7debf78da918` |

PR #5 review traced stars from individually scoped NHTSA associations to the regenerated v3 artifact and verified the pinned evidence. PR #6 merged cleanly after PR #5. The integration mismatch was the PR #6 equipment sidecar's v2 catalog pin. The builder validates that original pin, regenerates the sidecar byte for byte, then checks the same EPA make, year, model, drivetrain and powertrain identities against v3. The source branches and both historical catalog artifacts were preserved. [PR #4](https://github.com/dgbaer4/car-shopping-guide/pull/4) · [PR #5](https://github.com/dgbaer4/car-shopping-guide/pull/5) · [PR #6](https://github.com/dgbaer4/car-shopping-guide/pull/6)

## Integrated behavior

- The buyer-profile review page uses the existing normalization, eligibility, scoring, and explanation modules. It shows up to five eligible configurations, adds five per expansion, and reports separate counts for configurations needing verification and exclusions. Equal incomplete recommendations use stable EPA ID ordering and the Potential match label.
- All 30 EPA-level equipment fields are explicitly unknown in this snapshot. Verified trim facts, including optional and package-dependent equipment, are shown under possible retail trims where scoped links exist. A missing or uncertain fact cannot satisfy, disqualify, or receive a zero equipment score for a requested feature. Used or new condition, price and other listing-specific facts remain unknown until supported.
- Cash outlay includes down payment, scheduled payments within the ownership period, and running costs. Net ownership cost includes depreciation, taxes and fees, interest during the period, and running costs. Each view shows total, annual and monthly-equivalent costs when its inputs are complete. Cash outlay can be calculated if resale value is unknown. An outstanding balance is separate from cash already spent. The pinned catalog lacks price, fees, finance terms and operating-cost inputs, so live catalog results show missing inputs and available assumptions. Numeric calculations were verified with explicit synthetic inputs.
- The browser retrieves only local static assets. For independent review, run `python -m http.server 8000` from the repository root on a local review machine, open the served guide, and choose **See recommendations** from the buyer profile.

## Data coverage

| Measure | Integrated result |
| --- | --- |
| EPA scope | 1,406 configurations, model years 2021–2026 |
| Configurations by make | Toyota 480, Hyundai 275, Kia 242, Nissan 230, Honda 179 |
| Configurations by powertrain | Gasoline 913, traditional hybrid 295, fully electric 161, plug-in hybrid 37 |
| Efficiency and range | 1,245 combined MPG values, 198 kWh/mile values, 161 EV range values |
| NHTSA evidence | 127 configurations with at least one published category pending approval (9.03%), 23 linked to variants with no published categories, 1,256 unresolved |
| Published rating categories | Overall 109, frontal 124, side 126, rollover 112 |
| Equipment evidence | 42 US retail trims in nine model-year cohorts, 740 of 1,260 equipment statuses documented, 520 unknown |
| Trim links | 46 relationships across 27 EPA configurations (1.92%), zero configuration-level equipment assignments |
| Listing and configuration gaps | No catalog prices, conditions, mileage, body styles or seating capacities |

Coverage denominators for EPA configurations and retail equipment facts differ. [Safety coverage and unresolved queue](reconciliation/csg-a02.2.md) · [Equipment coverage](vehicle-equipment-acquisition.md)

## Verification results

| Check | Observed result |
| --- | --- |
| `python -m unittest discover -s tests -p 'test_*.py'` | 46 passed |
| `node --test tests/*.test.mjs` | All 7 test files passed |
| `node --test --experimental-test-isolation=none tests/*.test.mjs` | 26 reported tests passed, including the 4 integration tests and the foundation assertion file |
| Draft 2020-12 schema and semantic checks | 1,406 catalog rows, 42 equipment trims and 46 relationships passed, including source formats, v2 digest and v3 EPA identity compatibility |
| Deterministic regeneration | Association register, v3 catalog including gzip bytes, NHTSA coverage JSON, unresolved CSV, equipment sidecar and equipment coverage reproduced byte-for-byte. Two independent builds matched the tracked integrated catalog. |
| Browser end-to-end | Chromium at 390 px, starting from saved buyer profiles. The gasoline profile showed 5 then 10 eligible recommendations with explanations and both cost perspectives. It reported 913 eligible and 493 exclusions. Return and v0.2 export passed. Requiring heated front seats produced 0 eligible and 913 needing verification. No page errors or outbound requests. |
| Repository diff | `git diff --check` passed |

Python 3.12 and Node 24.22.3 were used. The catalog SHA-256 is `27b2e2526369baed8ab78a380d49b4eb8515cd9b720d61bcab000acd91994641`. The first coverage comparison differed only in the reconstructed EPA JSON's serialization hash. Restoring the original importer's field order reproduced the recorded input hash and identical report. The first browser harness reused its initial profile during the second scenario. The passing rerun used isolated browser contexts. Staging and Safari acceptance are pending.

## Independent safety evidence review and approval gates

- Live EPA configuration details, NHTSA listings and NHTSA variant details matched all 11 sampled associations. The sample covered the 2023–2024 Leaf battery/grade aliases, 2025 CR-V gasoline FWD and AWD, 2026 Corolla Cross AWD gasoline and hybrid, and three category/concern controls. The directly downloaded Safercar CSV matched all 96 pinned bulk rows, including the recorded 2022 Ioniq 5 AWD frontal passenger airbag inspection concern. [Reviewed evidence](../data/development/nhtsa-reviewed-evidence.v2.json) · [Safercar export](https://static.nhtsa.gov/nhtsa/downloads/Safercar/Safercar_data.csv)
- Corolla Cross VehicleId 16983 retained frontal and side stars with overall and rollover unknown. Sportage PHEV VehicleId 17072 supplied zero published ratings and remained unrated. Twelve Camry, Ariya and production-window controls retained unknown ratings and applicability. The browser gives applicability status without presenting pending stars as verified or using them in scoring. [Corolla Cross](https://api.nhtsa.gov/SafetyRatings/VehicleId/16983) · [Sportage PHEV](https://api.nhtsa.gov/SafetyRatings/VehicleId/17072) · [Ioniq 5 AWD](https://api.nhtsa.gov/SafetyRatings/VehicleId/16597)
- **Human approval required before staging or publishing safety claims.** Review whether the linked variants apply to the EPA configurations, especially battery and drivetrain scope, restraint exceptions, and production or VIN boundaries. Review the Ioniq 5 concern and how it should accompany any published rating. The 2026 Tundra Hybrid ISOdynamic variant lookup returned HTTP 400 in the pinned acquisition. Its 12 potentially overlapping EPA rows require scope and acquisition follow-up. Keep the applicability and ratings for unresolved configurations unknown until scoped evidence is available. [Applicability and gaps](reconciliation/csg-a02.2.md)
- Staging acceptance should assess sparse catalog coverage and provisional match thresholds. Hard requirements that the catalog cannot confirm may legitimately yield an empty initial list. Pricing and operating inputs remain a dependency for numeric ownership estimates on the live catalog. [Approved results requirements](results-interface.md)
