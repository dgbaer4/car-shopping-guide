# Future development backlog

## Data and recommendations

- **Safety evidence.** Independently approve the NHTSA variant-to-configuration mappings and the treatment of category concerns before enabling any stars or safety scoring. Prioritize the Ioniq 5 airbag concern, production and restraint boundaries, and the Tundra ISOdynamic acquisition failure. Defer broader acquisition until after the cash pilot. [Evidence and review queue](reconciliation/csg-a02.2.md)
- **Equipment evidence.** Expand US model-year and trim coverage with authoritative evidence. Verify installed equipment and package boundaries against a specific listing or build record before promoting a potential match. [Acquisition scope](vehicle-equipment-acquisition.md)
- **Verified local cost inputs.** Evaluate licensed inventory prices, local tax and fee sources, and defensible insurance, maintenance and resale inputs. Establish how to label the age, region and coverage of each estimate. Add actual quote and listing comparisons while keeping modeled values separate from eligibility.
- **Match validation.** Calibrate ranking and labels with owner-reviewed profiles and inventory, compare body-style and used-condition evidence, and verify charging feasibility for electric and plug-in hybrid profiles.

## Interface and release

- **Financing.** Keep the existing amortization and ownership-cost tests. Reintroduce financing questions and comparisons only after a separate scope decision and review of term, APR, payment and loan-balance presentation.
- **Acceptance.** Test Safari export, printing, browser recovery and mobile accessibility. Assess whether users can gather listing-level evidence and update their estimates without losing context. Staging uses the allowlisted static release built by `tools/build_pilot_release.py`.
