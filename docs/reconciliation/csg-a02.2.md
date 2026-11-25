# CSG-A02.2 NHTSA applicability and coverage

The development catalog now contains **127 rated EPA configurations out of 1,406 (9.03%)**, up from **43 (3.06%)**. Within the 29 prioritized model families, coverage increased from **19 of 754 (2.52%)** to **103 of 754 (13.66%)**. This pass added 84 rated associations and 12 explicitly unrated associations, preserving all 54 previous associations and their evidence. An EPA configuration counts as rated when at least one of the four catalog rating categories has published stars.

| Overall goal | EPA configurations required | Remaining |
| --- | ---: | ---: |
| 15% | 211 | 84 |
| 30% | 422 | 295 |
| 50% | 703 | 576 |

| Method | New rated | New confirmed unrated |
| --- | ---: | ---: |
| Same-year configuration review with Safercar corroboration, existing candidate set | 66 | 8 |
| Same review after a source alias corrected the candidate set | 18 | 4 |
| Transfer across distinct configurations | 0 | 0 |

[Development catalog](../../data/development/vehicle-catalog-2026-11-24.v3.json.gz) · [Mapping register](../../data/vehicle-reconciliation-mappings.v3.json) · [Reviewed evidence](../../data/development/nhtsa-reviewed-evidence.v2.json) · [Coverage by manufacturer, year, powertrain and prioritized family](nhtsa-coverage-a02.2.json) · [Unresolved queue](nhtsa-unresolved-a02.2.csv)

## Applicability method

1. Compare the EPA detail record to the NHTSA year/make/model listing and variant detail. Keep source-native names and VehicleIds. Check the same model year, powertrain, body and drivetrain. EPA size classes describe efficiency groups and can use different labels from NHTSA body styles. Check manufacturer model-year specifications where the EPA label omits a distinction such as battery capacity.
2. Find a unique Safercar row for that year, make, model and drivetrain. Cross-check body and original category values and read the category notes and concerns. Check early and late variants in the API as well. The export sometimes uses release labels in its model or body text even when the numeric release field is `1`. A blank export rating alone provides no proof of unpublished status. Require the live NHTSA detail to report all four categories as `Not Rated` before classifying a configuration as confirmed unrated.
3. Pin the individual EPA and NHTSA identities, the native listing and rating URLs, the rating fields and raw values, the matching bulk row, any footnotes, the review statement, the access date and the reviewer. The generator rejects changed API identity and values during live verification. The builder checks the pinned bulk row against the approved body, drive, year and rating values. Independent review should check the source scope and the inference connecting the records.
4. For a multi-configuration approval, obtain the NHTSA rating notification, category applicability statement or equivalent agency record that explicitly enumerates the covered trims or configuration scope. Use manufacturer specifications to connect the stated boundaries to EPA rows. Keep separate scopes for each year, drivetrain, structural generation, battery, restraint arrangement and applicable production range. Compile one approved association per EPA ID under the shared source and scope, retaining each category's values. A manufacturer's trim or feature table can establish configuration identity. An automaker award page or a single tested VIN leaves broader NCAP applicability unresolved.

NHTSA's labeling rule describes written notifications for newly rated vehicles and for carryovers, with agency engineering review of manufacturer submissions for trim and corporate-twin applicability. The rule describes optional retesting for midyear production changes and material safety equipment differences. The communication guidelines also describe VIN or date disclosures for revised ratings. No trim-line notification covering the unresolved priority groups was identified in the public material reviewed. The review used the same-year official ratings directly and kept generation transitions within their model years. [NCAP safety labeling rule, pp. 29–34 and 40–42](https://www.nhtsa.gov/document/final-rule-new-car-assessment-program-ncap-safety-labeling) · [NHTSA communication guidelines](https://www.nhtsa.gov/ratings/government-5-star-safety-ratings-motor-vehicles-advertising-and-communication-usage)

The public Safercar export contains variant rows, restraint fields, test numbers and category footnotes. It lacks API VehicleIds, so the join uses the native variant's identity and corroborates category values. The Crash Test Database supplies engineering records and test vehicles, which can identify a tested build. It does not establish which other production vehicles inherit its ratings. NHTSA's NCAP archive includes a database named `NCAP 6-14-10.mdb`; this pass used the current Safercar export and API for 2021–2026. [Safercar download and data dictionary](https://www.nhtsa.gov/file-downloads?p=nhtsa/downloads/Safercar/) · [NCAP archive](https://www.nhtsa.gov/file-downloads?p=nhtsa/downloads/NCAP/) · [Crash Test Database](https://www.nhtsa.gov/research-data/databases-and-software) · [Safety Ratings API](https://www.nhtsa.gov/nhtsa-datasets-and-apis)

## Remaining gaps

The 1,256 unresolved rows are grouped by the first review blocker the pinned inputs expose. Candidate aliases and acquisition overlap are triage signals. The search for alias hints uses normalized token prefixes within the same make and model year solely for the queue. Priority coverage uses listed family prefixes solely for reporting, with Prius PHEV included under Prius Prime.

| First review blocker | EPA configurations |
| --- | ---: |
| Multiple EPA configurations within a rating scope need authoritative applicability evidence | 455 |
| Possible missing model alias | 452 |
| Missing structured vehicle attributes and scope | 117 |
| No same-year candidate or alias lead in the snapshot | 115 |
| All currently viable candidates are explicitly unrated | 51 |
| Multiple potentially applicable NHTSA variants | 38 |
| Known configuration conflict | 16 |
| Possible overlap with an acquisition failure | 12 |

- **Trim and equipment.** Toyota identifies the 2025 Camry as hybrid-only and documents LE, SE, XLE and XSE in both drivetrains. NHTSA lists separate FWD and AWD records. The reviewed public material leaves the NCAP trim scope unresolved for the five EPA entries. Nissan Ariya ratings exclude front-center-airbag vehicles. Battery and drive alone cannot clear the restraint exclusion. [Toyota Camry specifications](https://pressroom.toyota.com/toyota-camry-goes-exclusively-hybrid-plus-a-new-look-and-more-technology/) · [2025 Ariya listing](https://api.nhtsa.gov/SafetyRatings/modelyear/2025/make/NISSAN/model/ARIYA)
- **Production windows.** The 2023 Camry rating records identify distinct January build windows and direct consumers to Toyota for the intervening period. The 2023 Kicks changes at a January VIN cutoff, even though both variants show the same catalog stars. The 2024 Ioniq 5 and Tucson have build or plant boundaries. EPA configurations do not identify those production ranges. [2023 Camry variants](https://api.nhtsa.gov/SafetyRatings/modelyear/2023/make/TOYOTA/model/CAMRY) · [2023 Kicks variants](https://api.nhtsa.gov/SafetyRatings/modelyear/2023/make/NISSAN/model/KICKS) · [Safercar export](https://static.nhtsa.gov/nhtsa/downloads/Safercar/Safercar_data.csv)
- **Battery, drive and generation.** The 2023–2025 Leaf source records separate 40 kWh and 60 kWh batteries, while the redesigned 2026 model lists 53 kWh and 75 kWh. Nissan ties the three 2026 US 75 kWh wheel configurations to retail grades. The reviewed NHTSA row identifies 75 kWh FWD but does not enumerate all three grades. Some Kona Electric rows have opposite drive descriptions across the two sources. [2026 Leaf specifications](https://usa.nissannews.com/en-US/releases/2026-nissan-leaf-specifications) · [2026 Leaf rating variants](https://api.nhtsa.gov/SafetyRatings/modelyear/2026/make/NISSAN/model/LEAF%20PLUS%20%2875%20KWH%20BATTERY%29) · [2025 Kona Electric listing](https://api.nhtsa.gov/SafetyRatings/modelyear/2025/make/HYUNDAI/model/KONA%20ELECTRIC)
- **Acquisition and publication.** The pinned input has 916 variants (791 with stars, 125 explicitly unrated). It has one HTTP 400 model-level failure for the 2026 Toyota Tundra Hybrid with ISOdynamic seat. The 12 EPA rows flagged for possible overlap share the wider Tundra family. EPA does not identify which rows have that seat. The 51 rows with only unrated candidates still need scope evidence before any configuration-level unrated finding.

## Independent review package

Sample the groups below in order. The evidence file contains the original EPA configuration signature and NHTSA category record for each cited EPA ID. The sample is designed to cover the main decisions that can affect publication across multiple rows.

| Priority | Shared evidence and risk | Samples |
| --- | --- | --- |
| 1 | Battery and model aliases. Compare Nissan's same-year S and SV Plus specifications to the 40 and 60 kWh agency rows, particularly where EPA lists motor power as TBD. | EPA 46016 and 46017 for 2023, 46973 and 46974 for 2024. [Nissan 2023](https://usa.nissannews.com/en-US/releases/2023-nissan-leaf-press-kit) · [Nissan 2024](https://usa.nissannews.com/en-US/releases/2024-nissan-leaf-press-kit) |
| 2 | Body vocabulary, powertrain and duplicate labels. Verify the CR-V gasoline selection where hybrid EPA rows share the same text. Verify Corolla Cross gasoline AWD versus hybrid AWD. | EPA 47949, 47956, 48938 and 48939. [Safercar](https://static.nhtsa.gov/nhtsa/downloads/Safercar/Safercar_data.csv) |
| 3 | Partial and unpublished categories. Confirm no stars leak from explicitly unrated variants and partial fields are retained literally. Check the retained concern for the 2022 Ioniq 5 AWD. | EPA 44588, 47223 and 44922. [Corolla Cross 16983](https://api.nhtsa.gov/SafetyRatings/VehicleId/16983) · [Sportage PHEV 17072](https://api.nhtsa.gov/SafetyRatings/VehicleId/17072) · [Ioniq 5 16597](https://api.nhtsa.gov/SafetyRatings/VehicleId/16597) |
| 4 | Scope rejection. Confirm the catalog leaves the cited Camry, Ariya, and production-window cases unresolved. | EPA 48030–48034, 48718–48723 and 45766. [Unresolved rows](nhtsa-unresolved-a02.2.csv) |

Agent 2 reviewed evidence. Automated validation rechecked live EPA configuration signatures, NHTSA listings and NHTSA details for all 150 associations and verified the 96 new Safercar row snapshots against the downloaded CSV. Independent human review remains pending.

## Reproduce the catalog and reports

Use the original Stage A EPA JSON and the pinned Agent 1 safety snapshot. The archive download returned HTTP 403 during this pass. The EPA JSON was reconstructed from the version 2 development catalog by removing the generated ratings and their source entries, then serializing the retained data in the original EPA importer's field order. Its SHA-256 matched the recorded Stage A EPA hash exactly. The safety input SHA-256 also matched the previous report. The Safercar CSV used for this review had SHA-256 `db62cffdad8cf8007c51448700802132ec4ecab7724f6f16e0bc54cf8238a89d`. The pinned reviewed rows permit offline builds if the CSV is updated later. [Stage A artifact](https://github.com/dgbaer4/car-shopping-guide/actions/runs/45507136855/artifacts/14975252454) · [Pinned safety acquisition](https://github.com/dgbaer4/car-shopping-guide/blob/a4601cbc2945f4ea1d3babd059857fa2f0e64964/data/development/nhtsa-safety-2026-11-24.v1.1.json.gz)

```sh
register=data/vehicle-reconciliation-mappings.v3.json
evidence=data/development/nhtsa-reviewed-evidence.v2.json
catalog=data/development/vehicle-catalog-2026-11-24.v3.json.gz

python tools/generate_reconciliation_associations.py epa.json safety.json "$register" "$evidence" rebuilt.json
cmp rebuilt.json "$register"
python tools/build_catalog.py epa.json safety.json rebuilt.json catalog.json build-report.json
gzip -n -9 -c catalog.json | cmp - "$catalog"
python tools/report_nhtsa_coverage.py epa.json safety.json data/vehicle-reconciliation-mappings.v2.json \
  "$register" "$catalog" coverage.json unresolved.csv
cmp coverage.json docs/reconciliation/nhtsa-coverage-a02.2.json
cmp unresolved.csv docs/reconciliation/nhtsa-unresolved-a02.2.csv
python -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.mjs
```

Add `--verify-live` to the generator to recheck EPA and NHTSA API responses and `--safercar-csv Safercar_data.csv` to compare against a downloaded bulk export. This pass ran 27 Python and 17 Node tests, validated catalog v0.3 schema conformance, checked historical evidence preservation, and reproduced the register, uncompressed catalog, compressed catalog and build report byte-for-byte.
