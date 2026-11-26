"""Package the static observation preview from the released baseline assets."""

import argparse
from pathlib import Path
from shutil import copyfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = (
    ".nojekyll", "index.html",
    "data/development/equipment/vehicle-equipment.v1.json",
    "data/vehicle-catalog-v0.3-pilot.json", "data/vehicle-pricing.v1.json",
    *(f"assets/vehicles/{name}.webp" for name in (
        "sedan", "hatchback", "wagon", "compact-crossover", "midsize-suv",
        "full-size-suv", "pickup",
    )),
    *(f"engine/{name}.mjs" for name in (
        "browser-results", "pilot", "pilot-cost", "vehicle-pricing", "recommendation",
        "results", "scoring", "explanation", "ownership-cost", "browser-observations",
        "observation-config", "observations",
    )),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path, help="New directory for the static site")
    site = parser.parse_args().site
    site.mkdir()
    for asset in ASSETS:
        target = site / asset
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(ROOT / asset, target)


if __name__ == "__main__":
    main()
