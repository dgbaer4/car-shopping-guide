# CSG-I10 representative US vehicle pricing

The first reviewable checkpoint supports sourced used asking prices across all five pilot makes and all six model years, plus a small set of new MSRP references. It supports a meaningful gasoline, hybrid and EV comparison for the Walnut Creek–Moraga profile. Coverage is 118 of 1,406 EPA configurations (8.4%). Use this checkpoint for UAT of priced cohorts and the explicit quote-entry path. Release-wide pricing coverage and verified transaction estimates remain open.

## Source evaluation

| Source | Accuracy, coverage and freshness | Reuse and maintenance decision |
| --- | --- | --- |
| ForCar model-year CSV | Nationwide advertised used-car listings collected since June 2026. Publishes observed minimum/maximum, arithmetic mean and listing count. The download has 7,574 all-market rows and the publisher says it rebuilds daily. Independent collection, deduplication, dealer mix, title mix and sale completion could not be verified. | Free download, no credentials. The publisher explicitly licenses the aggregate under CC BY 4.0. Reuse the reviewed subset with attribution and a reproducible quality screen. [Publisher, method and license](https://forcar.org/open-data/) |
| Manufacturer media releases | Authoritative for the cited model-year grade MSRPs as of publication. Grade bounds and median describe the included lineup. MSRP excludes destination in this snapshot and gives no evidence of discounts, inventory, current dealer asks or completed transactions. | Free, manual review of selected published price facts with attribution. Preserve dates, body and powertrain scope. Do not copy OEM prose or images. The Toyota full-line PDF returned HTTP 403, so the snapshot includes no Toyota MSRP derived from it. [Honda](https://hondanews.com/en-US/releases/release-bb136e6e7af7ccb6b0336e10d81121d6-2026-honda-civic-hatchback-pricing-and-epa-ratings-september) · [Kia K4 sedan](https://www.kiamedia.com/us/es/media/pressreleases/22503/kia-america-announces-2025-k4-pricing) · [Kia K4 hatchback](https://www.kiamedia.com/us/en/media/pressreleases/24087/kia-america-announces-2026-k4-hatchback-pricing) · [Nissan](https://usa.nissannews.com/en-US/releases/more-features-more-range-still-under-30k-all-new-2026-nissan-leaf-priced-from-29990-msrp) · [Toyota](https://pressroom.toyota.com/toyota-full-line-pricing/) |
| MarketCheck developer API | Inventory and pricing endpoints could provide more recent and detailed listing coverage. The free plan has limited access and commercial plans have usage fees. | Current developer terms restrict redistribution and persistent caching. Excluded. No account, calls or purchases. [Pricing](https://developers.marketcheck.com/pricing) · [Terms](https://developers.marketcheck.com/uk/terms) |
| NHTSA vPIC | Free federal make/model/year and VIN decoding. An identity source that does not provide retail prices. | Available for future mapping checks without sourcing any prices. [API](https://vpic.nhtsa.dot.gov/api/) |
| GSA fleet auctions and Cox Manheim index | GSA documents public sales of retired fleet vehicles. The Manheim index measures wholesale movements. Neither examined public source provides an in-scope representative national retail transaction range by model, year and condition. | Use as context. Fleet auction and wholesale amounts describe a different market. [GSA](https://www.gsa.gov/buy-through-us/products-and-services/transportation-and-logistics-services/fleet-management/vehicle-leasing/sales-of-gsa-fleet-vehicles) · [Manheim methodology](https://www.coxautoinc.com/insights/manheim-insights/) |
| Marketplace dumps | Free or nominally open mirrors can contain ads and identifiers from third-party marketplaces. The Craigslist snapshot predates most target model years. | Excluded due to age or uncertain upstream rights. An uploader’s license alone does not establish permission to republish marketplace records. [Craigslist snapshot](https://zenodo.org/records/10457828) · [Cars.com-derived mirror](https://huggingface.co/datasets/KTHESAT/usa-used-car-market-cars-com) |

## Acquisition and schema

ForCar (2026), *US used-car market data*, is credited under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). We selected columns and cohorts, screened ranges and mapped records to the EPA configurations. The standalone CSV slice and generated JSON contain aggregates only. ForCar’s source, license and changes travel with the generated data. [Source attribution](https://forcar.org/open-data/)

1. The source download on 2026-11-25 was [the model-year CSV](https://forcar.org/datasets/used-car-prices-by-model-year.csv), SHA-256 `d8bbc7d4765d8a51c1de01238a5ad15d7c499cc01f9aed0cd68602ee63bf4c31`. The vendor replaces that URL daily. The repository pins the seven aggregate columns for the 87 selected model-years. Run `python tools/build_vehicle_pricing.py --verify-forcar /path/to/pinned-download.csv` when the original download is available.
2. Check source-native badge and scope against the pilot catalog. `data/pricing/used-scope.v1.json` records reviewed, anchored aliases and required powertrains. New prices are manually transcribed as numeric grade facts in `manufacturer-msrp.v1.json`. The builder matches exact make, year and powertrain before applying an alias. It does not interpolate across years or copy a price into another condition. A family estimate spans trims and drivelines within its allowed scope. It is not an assertion that every constituent listing shares the exact EPA configuration.
3. Retain used cohorts with at least 15 listings, an ordered positive range, an observed low at least 35% of the mean, and an observed high at most 190% of the mean. These screening thresholds reject unusually broad or suspect cohorts without transforming raw extremes into invented percentiles. They are not statistical confidence intervals and can exclude real broad markets. Fifteen cohorts failed sample size, 31 failed range screening, and one passing cohort lacked a supported EPA linkage. Used rows with 15–39 observations are labeled limited and those with 40+ moderate. MSRP uses the median of the stated grades, with reference-only confidence and grade count rather than listing count.
4. Run `python tools/build_vehicle_pricing.py --write` to refresh the generated asset deliberately. Running without `--write` checks exact bytes and prints coverage. Refresh the upstream pin, reviewed scope and version/date together after reviewing coverage changes. The optional pinned-download check independently verifies the slice. The current asset SHA-256 is `3c405c5b68ad60afee026fa1f307748fe7478f0eb3b69b018ec205ed85f06572`.
5. [The JSON schema](../data/vehicle-pricing.schema.json) defines USD, basis, condition, low/central/high, method, sample count, confidence, reference date, source attribution and linked EPA IDs. The builder validates each range and rejects duplicate EPA ID/condition links. Runtime reads only the versioned result. The release allowlist excludes input evidence and development safety data. No runtime API or credentials.

## Coverage

There are 40 used asking-price cohorts and four new MSRP cohorts. Used estimates cover 112 configurations. New MSRP covers nine, three of which also have used prices. Coverage counts EPA configurations, including configuration variants that share a family estimate.

| Make | Used | New MSRP | Either / catalog |
| --- | ---: | ---: | ---: |
| Honda | 25 | 1 | 26 / 179 |
| Hyundai | 15 | 0 | 15 / 275 |
| Kia | 18 | 5 | 20 / 242 |
| Nissan | 27 | 3 | 30 / 230 |
| Toyota | 27 | 0 | 27 / 480 |

| Model year | Used | New MSRP | Either / catalog |
| --- | ---: | ---: | ---: |
| 2021 | 6 | 0 | 6 / 212 |
| 2022 | 20 | 0 | 20 / 225 |
| 2023 | 26 | 0 | 26 / 234 |
| 2024 | 29 | 0 | 29 / 247 |
| 2025 | 21 | 3 | 21 / 243 |
| 2026 | 10 | 6 | 16 / 245 |

| Powertrain | Used | New MSRP | Either / catalog |
| --- | ---: | ---: | ---: |
| Gasoline | 37 | 5 | 39 / 913 |
| Traditional hybrid | 18 | 1 | 19 / 295 |
| Plug-in hybrid | 1 | 0 | 1 / 37 |
| Fully electric | 56 | 3 | 59 / 161 |

## Comparison and acceptance

The Walnut Creek–Moraga test uses the existing commuter profile, with home charging and EVs also considered. Defaults use 12,500 miles per year, four years, $4.50 per gallon and $0.30 per kWh. Tax, fees, insurance, maintenance, registration and resale are editable scenario assumptions. Shopping ZIP, mileage, trim and actual condition do not adjust the acquired price.

| Used candidate | Observed ads / mean | Annual energy | Four-year cash / net |
| --- | --- | ---: | ---: |
| 2025 Nissan Versa, gasoline | $7,250–$21,995 / $16,535 (61) | $1,607 | $34,917 / $27,476 |
| 2026 Toyota Prius, hybrid | $24,900–$40,241 / $33,713 (29) | $987 | $51,332 / $36,161 |
| 2023 Hyundai Ioniq 6 long-range RWD, electric | $14,900–$32,000 / $24,143 (27) | $884 | $40,393 / $29,529 |

At these inputs the Versa has the highest energy cost and lowest net ownership cost. The Prius at a hypothetical $21,500 entered price shows $24,150 estimated at purchase, yet remains a potential budget fit until an out-the-door quote is entered. A user-entered $24,300 confirmed out-the-door quote meets the $25,000 all-in cap. Unknown equipment and mileage still require verification. Switching the Prius to new shows price-dependent totals as unavailable because the snapshot has no matching MSRP. Operating costs remain available from independent energy and running-cost inputs.

- All 46 Python tests and 33 Node checks passed. Schema validation, exact regeneration and sanitized local packaging passed. Node tests cover strict ceilings, missing price evidence, new/used separation, provisional versus confirmed quote handling, and recalculation.
- Chromium passed the complete interview, export and pricing flow at 390 px against the local static package. It checked the three powertrains, condition switching, missing-price behavior, quote confirmation, editable gas prices, pagination, and same-origin requests. The public staging site was outside this assignment.

## Next acquisition increments

1. Request a CC BY model/year/powertrain split with median and P10/P90, plus sample window, title-screening and listing deduplication details. Start with RAV4, CR-V, Corolla, Civic, Elantra and popular plug-in hybrids. Replacing raw extrema with published quantiles can recover useful cohorts currently rejected.
2. Add current OEM references with exact model year, US body/powertrain and destination charges where published. Prioritize Toyota and Hyundai, then gaps by cohort frequency. Keep launch MSRP visibly historical where it is the only reference.
3. Acquire completed retail transaction aggregates only with a verified public reuse grant. Keep estimates separate from approved seller quotes. With sparse coverage, test both sourced and quote-only paths before declaring the pricing blocker cleared for the general catalog.

## UAT handoff

The pricing UI changes are localized to `engine/browser-results.mjs` and short styles in `index.html`. The view contract is `item.pricing.conditions` plus `item.pricing.records.new/used`. Preserve `priceBasis`, range, record date and attribution in card layouts. Quote state is keyed by EPA ID and selected condition. `assessBudget` owns the distinction between projected fit and a user-confirmed quote. The pricing loader expects `data/vehicle-pricing.v1.json` in the static release tree.
