# US vehicle equipment acquisition

CSG-A03 adds a development-time sidecar for catalog v0.3. The initial acquisition covers **42 US retail trims in nine model-year cohorts**, spanning all five priority manufacturers and model years 2024–2026. It records **740 known equipment statuses**, including confirmed unavailability, out of 1,260 trim-by-equipment cells. The remaining 520 equipment cells are unknown. It records a further 135 body, seating, drivetrain and powertrain facts. The pinned EPA baseline has **1,406 configurations and zero with known catalog equipment**. The sidecar adds 46 supported trim relationships across 27 distinct EPA configurations (1.9%). There are zero EPA configuration-level equipment assignments from this process.

| Make | Retail trims | Known equipment cells | Linked EPA configurations | EPA baseline |
| --- | ---: | ---: | ---: | ---: |
| Honda | 20 | 442 | 13 | 179 |
| Hyundai | 5 | 47 | 5 | 275 |
| Kia | 5 | 75 | 1 | 242 |
| Nissan | 3 | 60 | 2 | 230 |
| Toyota | 9 | 116 | 6 | 480 |

The [coverage report](vehicle-equipment-coverage.v1.json) includes counts by make, year and EPA model, plus status counts by make, year and retail model, and every field's value or unknown status for each acquired trim. EPA and retail model names are reported at their respective grains. The retail denominator counts acquired trims only because the EPA catalog does not enumerate retail trim identities.

## Sources and reuse

| Cohort | Accepted source and extraction |
| --- | --- |
| 2024 Honda CR-V | Scoped rows from the [Honda News specification matrix](https://hondanews.com/en-US/releases/release-13f25e90cfe47cd58453f1f710054868-2024-honda-cr-v-specifications-features) |
| 2025 Honda Accord and Civic Sedan | Scoped rows from the [Accord](https://hondanews.com/en-US/releases/release-008e554add341b8444085beaa2074089-2025-honda-accord-specifications-features) and [Civic](https://hondanews.com/en-US/releases/release-c28e8d1efb94e520fef21ff3f800cb30-2025-honda-civic-sedan-specifications-features) Honda News matrices |
| 2026 Honda Civic Sedan | Reviewed mark, trim and rating comparisons from the [Honda Information Center](https://www.hondainfocenter.com/2026/Civic-Sedan/Feature-Guide/Civic-Sedan-Specifications/) |
| 2026 Hyundai IONIQ 5 | All-grade equipment statements, selected trim-specific notes and EPA range by drive and grade from the [year-specific Hyundai overview](https://www.hyundaiusa.com/us/en/vehicles/2026-ioniq-5) |
| 2026 Kia K4 Sedan | Reviewed grade and package rows in [Kia's full-line brochure, PDF pp. 30–31](https://www.kia.com/us/content/dam/kia/us/brochures/KIA_Full-Line_Brochure.pdf), the [dated pricing announcement](https://www.kiamedia.com/us/en/media/pressreleases/24161/kia-announces-pricing-for-2026-k4-compact-sedan) and [EPA vehicle 50059](https://www.fueleconomy.gov/ws/rest/vehicle/50059) |
| 2025 Nissan Sentra | Integrated trim tables and package list in the [US Nissan press kit](https://usa.nissannews.com/en-US/releases/2025-nissan-sentra-press-kit) |
| 2026 Toyota Camry and 2025 Toyota Prius | Explicit grade, package and all-grade statements in Toyota's [Camry](https://pressroom.toyota.com/toyota-camry-brings-bold-new-nightshade-edition-to-lineup-in-2026/) and [Prius](https://pressroom.toyota.com/2025-toyota-prius-gets-a-moody-vibe-with-new-nightshade-grade/) US releases |

Manufacturer copyright applies to the underlying brochures and pages. Under the project [data governance policy](data-governance.md), the register retains factual statuses and specifications, original paraphrases, and citations. Source HTML, PDFs, graphics and marketing descriptions are excluded from redistribution. Direct public HTML and brochure downloads were used where accessible. The Kia Media feature matrix and Toyota's Camry product PDF returned HTTP 403 during direct access. The Kia pricing fact comes from the publicly indexed dated announcement and the Camry facts come from the accessible Toyota release. The yearless Hyundai comparison currently serves a different model year, so the 2026 overview supplies this snapshot. The dated Kia pricing release identifies EX heat as available, while the later combined sedan/hatchback brochure groups it under EX. The register uses the explicit sedan availability announcement for EX and leaves the other sedan heated-seat cells open pending trim-specific verification.

[NHTSA vPIC](https://vpic.nhtsa.dot.gov/api/) was evaluated for manufacturer-reported vehicle identity, body and classification. Its scope and completeness vary by manufacturer and identifier. It is a candidate source for class, seating and drive corroboration with a scoped vehicle identifier. It supplied zero retail equipment claims in this snapshot. Consumer Reports and NHTSA crash-test inputs are outside this acquisition.

[FMVSS 111](https://www.ecfr.gov/current/title-49/subtitle-B/chapter-V/part-571/subpart-B/section-571.111) was evaluated for rear visibility. US final requirements apply by manufacture date starting May 1, 2018 to passenger cars under S5.5 and covered multipurpose passenger vehicles, trucks, buses and low-speed vehicles under S6.2, subject to the applicable 4,536 kg (10,000 lb) GVWR threshold. Check low-speed vehicle-specific provisions and applicable exemptions under the federal rules. The phased period ran from May 1, 2016 through April 30, 2018. This is a rear-image performance requirement. A regulatory inference should require scoped US certification, manufacture date, classification, GVWR and exemption review, and it supplies no evidence about a 360-degree camera or parking sensors. Every camera fact here comes from model-specific equipment material. [Final rule, 79 FR 19178](https://www.govinfo.gov/content/pkg/FR-2014-04-07/pdf/2014-07469.pdf)

## Repeatable acquisition and validation

1. Download authorized, year-specific US public source documents for local review. Check the actual page title and trim columns. When model or trim versions differ, record an explicit scope and leave unclear cells unknown.
2. Transcribe normalized facts into [the reviewed evidence register](../data/development/equipment/vehicle-equipment-evidence.v1.json). A matrix names one market, model year, make and retail model. Columns name trims. Each row has an ordered cell per column, an evidence paraphrase and a source locator. JSON `null` leaves the fact unknown. Use row-specific source IDs when corroboration varies. Preserve source date and reuse conditions in each source entry.
3. For Honda News bullet-and-dash comparison tables, the extractor reads a local document, checks the exact year, model and ordered column labels, and emits normalized rows. Review section identity, package dependencies and footnotes before adopting the output. HTML layout or unrecognized marker changes raise a review error. For narrative sources and Kia's PDF, review the full grade and package descriptions, then record just scoped factual rows. For Nissan, distinguish factory options generally from options explicitly tied to named packages.
4. Verify any proposed EPA relationship with explicit grade names or corroborated vehicle attributes, such as matching powertrain, body, drivetrain and published fuel economy or electric range. Record the evidence and preserved catalog identity for each link. When specifications are shared by several trims, record separate links. Leave ambiguous IDs open.

Run from the repository root with Python 3 and Node. Python tooling uses `jsonschema` 4 and `lxml` for the Honda extraction aid.

```sh
python -m pip install -r tools/requirements-equipment.txt
mkdir -p /tmp/csg-equipment
curl -fL 'https://raw.githubusercontent.com/dgbaer4/car-shopping-guide/199407312dc5d5df3c1e98f3b82b86206da405fe/data/development/vehicle-catalog-2026-11-24.v2.json.gz' \
  -o /tmp/csg-equipment/catalog.json.gz
sha256sum /tmp/csg-equipment/catalog.json.gz
```

Expected SHA-256 for the compressed catalog is `eee9f0dd35d21ccddef9db9dea49d6b1d9651192b58734b657e3a9ddb350c0ad`. This pins the denominator and EPA identities to PR #2's published artifact.

```sh
curl -fL 'https://hondanews.com/en-US/releases/release-008e554add341b8444085beaa2074089-2025-honda-accord-specifications-features' \
  -o /tmp/csg-equipment/accord.html
python tools/extract_honda_equipment.py /tmp/csg-equipment/accord.html \
  2025 Accord LX SE Sport EX-L Sport-L Touring

python tools/import_vehicle_equipment.py \
  data/development/equipment/vehicle-equipment-evidence.v1.json \
  /tmp/csg-equipment/catalog.json.gz \
  /tmp/csg-equipment/equipment.json /tmp/csg-equipment/coverage.json
python tools/validate_vehicle_equipment.py \
  /tmp/csg-equipment/equipment.json /tmp/csg-equipment/catalog.json.gz
cmp /tmp/csg-equipment/equipment.json data/development/equipment/vehicle-equipment.v1.json
cmp /tmp/csg-equipment/coverage.json docs/vehicle-equipment-coverage.v1.json
python -m unittest discover -s tests -p 'test*.py'
node --test tests/*.test.mjs
```

The [schema](../data/vehicle-equipment.schema.json) defines the sidecar contract. The validator checks the version and typed fields, catalog hash, duplicate identities, fact-to-trim and source market/year/model scopes, and EPA make/year/drivetrain/powertrain compatibility. This structural validation guards against common propagation errors. The manufacturer's comparison or evidence locator remains the authority for reviewing the individual claim.

## Proposed catalog adapter

Keep the trim sidecar and EPA catalog as separate static inputs. Use the explicit relationship table to show a candidate's plausible trims, with an open candidate set unless separate evidence establishes completeness. Allow a verified retail identity or build record to narrow the set. For a retail-trim display, report standard availability alongside a condition for packaged or optional equipment. For an individual listing, require installation evidence for those conditional features. An adapter may translate a verified standard entry to `true` and confirmed unavailable to `false` for the matching equipment scope. Optional, package-dependent and unknown should map to `null` unless listing evidence settles the question. A known EPA drive configuration can establish drivetrain independently of a trim's set of available drivetrains. This proposal requires review before the engine consumes the sidecar.

## Expansion queue

- Extend the already-tested Honda table parser to scoped 2021–2023 tables and add Nissan table extraction with explicit checks for colspans, dash meanings and named packages.
- Prioritize US year-specific trim matrices for Toyota RAV4, Honda CR-V, Nissan Rogue, Hyundai Tucson and Kia Sportage, followed by plug-in hybrids and other EVs. A single matrix can fill several trims and detect variation across years.
- Resolve Kia's remaining DMS versus non-DMS sedan configurations, Toyota's Prius drivetrain terminology and Camry Nightshade membership, and the unnamed Civic 31-MPG rows through authoritative configuration evidence.
- Fill backup camera, seating and package-dependent comfort fields via full trim tables. Verify the interaction method for climate controls directly from a year- and trim-scoped manual or hardware documentation.
