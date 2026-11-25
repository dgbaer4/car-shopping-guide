# Car Shopping Guide

Car Shopping Guide v0.3 — Pilot Preview compares vehicle configurations for an outright cash purchase. It includes a buyer interview, local progress saving, profile export, and editable ownership-cost estimates. Keep personal buyer responses out of this public repository.

## Development and staging

Run `python -m http.server 8000` from the integration checkout and open the local guide. GitHub Pages serves the static release on the `staging` branch. Use `python tools/build_pilot_release.py --site /path/to/new-directory` to build the allowlisted staging tree.

[Staging preview](https://dgbaer4.github.io/car-shopping-guide/) · [Integration report](docs/integration-report-v0.3.md) · [Future development backlog](docs/future-development-backlog.md)
