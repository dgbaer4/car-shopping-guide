# Car Shopping Guide roadmap and development backlog

Version assignments are provisional and depend on owner approval and development findings.

| Version | Planned scope |
| --- | --- |
| v0.4 Pilot Preview | Recommendation quality, used-car catalog integrity, the local Shopping Tracker, and device-enrolled private price sharing. Controlled staging, live intake verification, and physical iPad acceptance follow integration. |
| v0.5 | Mature the Shopping Tracker, expand licensed used-car pricing, and add owner administration, normalization, and publication of explicitly approved observations. Display approved observations separately from representative pricing. |
| v0.6 | New-car eligibility and availability enhancements, current and upcoming model-year acquisition and MSRP, and live inventory discovery. Test model-year rollover and verify actual condition and availability. |
| v0.7 | Evaluate statistical incorporation of sufficiently reliable contributed observations into representative estimates. Require adequate sample sizes, appropriate price categories and validation before use. |
| v0.8–v0.9 | Expand coverage, improve accuracy and accessibility, and prepare operations and release controls. |
| v1.0 | Full production release. |

## v0.5 owner administration and normalization

Build an owner-authenticated, iPad-friendly browser administration page and a private Sheets **Administration** tab. Provide a manual **Evaluate and Normalize** action, deterministic validation, scoped aliases, catalog matching, duplicate and anomaly detection, privacy screening, an unmatched queue and individual exception review. Keep raw observations and review provenance private. Bulk approval applies only to publication-safe records. Publication needs explicit owner authorization and separate treatment of any public attribution consent.

A manually triggered GitHub `workflow_dispatch` process should accept only the approved sanitized batch, validate against a pinned catalog/schema and alias version, and produce a deterministic versioned pricing data asset and a reviewable pull request. Keep raw or private data out of GitHub. Preserve stable IDs, original receipt and review history, and distinctions between advertised, quoted and reported completed purchase prices, and between vehicle-only and out-the-door prices. Keep publication manual, with no scheduled processing or automatic release. [Issue #18](https://github.com/dgbaer4/car-shopping-guide/issues/18) · [Observation architecture](https://github.com/dgbaer4/car-shopping-guide/issues/9)

For the tracker, improve per-candidate comparisons and deliberate reuse of a vehicle-only observation as an estimate input. Out-the-door totals need an explicit component breakdown before comparing component costs. Establish retention, takedown and review responsibilities before publication.

## Evidence and acceptance backlog

- Expand authoritative US trim and equipment coverage and verify listing-level equipment. Review NHTSA applicability, category concerns and restraints before approving publication or scoring. [v0.3 evidence queue](https://github.com/dgbaer4/car-shopping-guide/blob/c20c0cc4be1dc7f13c7b24e190ee0bc2a2859130/docs/reconciliation/csg-a02.2.md)
- Expand licensed pricing coverage and defensible local tax, insurance, maintenance and resale assumptions. Preserve manual quotes for unpriced cohorts and label coverage and date clearly.
- Calibrate the shortlist with owner-reviewed profiles and compare verified condition, body style and charging feasibility against real vehicles. Continue Safari export, print and browser recovery acceptance.
- Treat the v0.6 new-car acquisition and eligibility work as a separate owner decision. The June 30 used-only rule applies to model year 2027 only. [Issue #17](https://github.com/dgbaer4/car-shopping-guide/issues/17)
- Preserve financing regression coverage. A future owner decision is required for financing or amortization presentation.
