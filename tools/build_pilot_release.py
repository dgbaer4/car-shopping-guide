"""Generate a safety-free catalog and package the staging Pages tree."""

import argparse
import json
from pathlib import Path
import shutil

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path("data/vehicle-catalog-v0.3-pilot.json")
EQUIPMENT = Path("data/development/equipment/vehicle-equipment.v1.json")
VEHICLE_FIELDS = {
    "id", "make", "model", "year", "trim", "power", "body", "drivetrain", "features",
    "mpg", "kwhPerMile", "electricRangeMiles", "possibleTrimIds", "seats", "highSeating",
}
ASSETS = (
    Path("index.html"), EQUIPMENT,
    *(Path("engine") / (module + ".mjs") for module in (
        "browser-results", "pilot", "pilot-cost", "recommendation", "results",
        "scoring", "explanation", "ownership-cost",
    )),
)


def pilot_catalog():
    source = json.loads((ROOT / "data/vehicle-catalog-v0.3-integration.json").read_text())
    vehicles = [
        {**{key: row[key] for key in VEHICLE_FIELDS if key in row},
         "sources": [entry for entry in row["sources"] if
                     entry["url"] == "https://www.fueleconomy.gov/feg/download.shtml"
                     and set(entry["fields"]) <= VEHICLE_FIELDS]}
        for row in source["vehicles"]
    ]
    pilot = {"schemaVersion": "0.3", "vehicles": vehicles}
    schema = json.loads((ROOT / "data/vehicle-catalog.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(pilot)
    return json.dumps(pilot, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-catalog", action="store_true")
    parser.add_argument("--site", type=Path, help="Package the static release in a new directory")
    args = parser.parse_args()
    payload = pilot_catalog()
    if args.write_catalog:
        (ROOT / CATALOG).write_text(payload)
    if (ROOT / CATALOG).read_text() != payload:
        raise SystemExit("Pilot catalog differs from its generated projection")
    if args.site:
        args.site.mkdir()
        for asset in (*ASSETS, CATALOG):
            target = args.site / asset
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / asset, target)
        (args.site / ".nojekyll").touch()
    print("Validated the pilot catalog and release asset allowlist")


if __name__ == "__main__":
    main()
