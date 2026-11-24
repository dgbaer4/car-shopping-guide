# Vehicle data governance — v0.3

Approved 2026-11-24.

- Consumer Reports is excluded from acquisition, derived scores, redistribution and runtime. Do not use subscriber credentials or content.
- Prefer US federal government vehicle datasets; review dataset-specific notices and third-party material before publication.
- Manufacturer specifications: record factual attributes with source URLs and verification dates; do not reproduce protected descriptions or images.
- IIHS and commercial datasets: exclude from published data until applicable reuse terms are reviewed.
- Unknown values remain null or absent, never false or zero by default.
- NHTSA complaints and recalls are not comparative reliability rates. Do not derive reliability rankings from raw counts.
- Preserve model year, drivetrain, configuration identity, source field mapping and verification date.
- Never infer installed optional equipment from availability alone.
- All acquisition runs at development time. Runtime uses static catalog files only.
- Require source review, schema validation and regression tests before staging deployment.
