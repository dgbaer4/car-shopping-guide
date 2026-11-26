"""Validate and package the pilot projection from the pinned v0.3 release."""

import argparse
from collections import Counter
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import shutil
import subprocess

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
RELEASE = "0f2b704ab9187fb0a19544e0cf727edbf47fd755"
INTEGRATION = "c20c0cc4be1dc7f13c7b24e190ee0bc2a2859130"
CATALOG = "data/vehicle-catalog-v0.3-pilot.json"
PRICING = "data/vehicle-pricing.v1.json"
CLASSIFICATIONS = "docs/catalog-classification-v0.4.csv"
MATRIX = "docs/catalog-coverage-v0.4.csv"
COUNTS = "docs/catalog-configuration-counts-v0.4.csv"
YEARS = range(2021, 2027)
MAKES = {"Toyota", "Honda", "Hyundai", "Kia", "Nissan"}
PICKUP_CLASSES = {
    "Small Pickup Trucks 2WD", "Small Pickup Trucks 4WD",
    "Standard Pickup Trucks 2WD", "Standard Pickup Trucks 4WD",
}
SANTA_CRUZ = "Hyundai identifies Santa Cruz as a compact pickup"


def from_git(ref, path):
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT)


def validate(payload, schema_path):
    schema = json.loads(from_git(INTEGRATION, schema_path))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def encode(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def build():
    released = from_git(RELEASE, CATALOG)
    if sha256(released).hexdigest() != "a7e676890e05b0506c898f3971f492fb4dd813da46e9589d5a59c86ee61338be":
        raise ValueError("Released catalog digest changed")
    catalog = json.loads(released)
    with (ROOT / CLASSIFICATIONS).open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    evidence = {row["epa_id"]: row for row in rows}
    ids = {v["id"] for v in catalog["vehicles"]}
    if len(ids) != len(catalog["vehicles"]) or len(evidence) != len(rows) or set(evidence) != ids:
        raise ValueError("Classification evidence must match the released EPA IDs")
    retained = []
    excluded = []
    for vehicle in catalog["vehicles"]:
        row = evidence[vehicle["id"]]
        identity = vehicle["make"], vehicle["model"], str(vehicle["year"])
        if identity != (row["manufacturer"], row["model"], row["model_year"]):
            raise ValueError(f"Classification identity mismatch for {vehicle['id']}")
        if vehicle["make"] not in MAKES or vehicle["year"] not in YEARS or not row["epa_class"]:
            raise ValueError(f"Unreviewed catalog scope for {vehicle['id']}")
        santa_cruz = vehicle["make"] == "Hyundai" and vehicle["model"].startswith("Santa Cruz ")
        if row["scope_override"] != (SANTA_CRUZ if santa_cruz else ""):
            raise ValueError(f"Unexpected classification override for {vehicle['id']}")
        target = excluded if row["epa_class"] in PICKUP_CLASSES or santa_cruz else retained
        target.append(vehicle)

    catalog["vehicles"] = retained
    validate(catalog, "data/vehicle-catalog.schema.json")
    approved_ids = {vehicle["id"] for vehicle in retained}
    equipment_path = "data/development/equipment/vehicle-equipment.v1.json"
    equipment = json.loads((ROOT / equipment_path).read_text(encoding="utf-8"))
    if any(row["epaId"] not in approved_ids for row in equipment["relationships"]):
        raise ValueError("An equipment relationship points outside the pilot scope")
    pricing = json.loads(from_git(RELEASE, PRICING))
    priced_rows = []
    for row in pricing["records"]:
        if not set(row["epaIds"]) <= ids:
            raise ValueError("Pricing references an ID outside the released catalog")
        approved_links = [key for key in row["epaIds"] if key in approved_ids]
        if approved_links:
            priced_rows.append({**row, "epaIds": approved_links})
    pricing["records"] = priced_rows
    validate(pricing, "data/vehicle-pricing.schema.json")

    coverage = io.StringIO(newline="")
    writer = csv.writer(coverage, lineterminator="\n")
    writer.writerow(("Manufacturer", "EPA model", *(f"{year} released" for year in YEARS),
                     *(f"{year} retained" for year in YEARS), "Released", "Excluded pickups", "Retained"))
    counts = Counter((v["make"], v["model"], v["year"]) for v in retained)
    removals = Counter((v["make"], v["model"], v["year"]) for v in excluded)
    for make, model in sorted({(v["make"], v["model"]) for v in retained + excluded}):
        kept = [counts[make, model, year] for year in YEARS]
        released = [count + removals[make, model, year] for year, count in zip(YEARS, kept)]
        writer.writerow((make, model, *released, *kept, sum(released), sum(released) - sum(kept), sum(kept)))

    totals = io.StringIO(newline="")
    writer = csv.writer(totals, lineterminator="\n")
    writer.writerow(("Manufacturer", "Model year", "Powertrain", "Released", "Excluded pickups", "Retained"))
    counts = Counter((v["make"], v["year"], v["power"]) for v in retained)
    removals = Counter((v["make"], v["year"], v["power"]) for v in excluded)
    for make in sorted(MAKES):
        for year in YEARS:
            for power in ("Gasoline", "Traditional hybrid", "Plug-in hybrid", "Fully electric"):
                key = make, year, power
                writer.writerow((*key, counts[key] + removals[key], removals[key], counts[key]))
    return {CATALOG: encode(catalog), PRICING: encode(pricing), MATRIX: coverage.getvalue(),
            COUNTS: totals.getvalue()}



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--site", type=Path, help="Package the approved static paths in a new directory")
    parser.add_argument("--intake-url", help="HTTPS Apps Script /exec URL for an explicitly configured test package")
    args = parser.parse_args()
    if args.intake_url and (not args.site or not re.fullmatch(
        r"https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec", args.intake_url
    )):
        parser.error("--intake-url requires --site and a Google Apps Script /exec URL")
    for path, payload in build().items():
        destination = ROOT / path
        if args.write:
            destination.write_text(payload, encoding="utf-8")
        if destination.read_bytes() != payload.encode("utf-8"):
            raise SystemExit(f"{path} differs from the generated projection")
    if args.site:
        release_paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", RELEASE], cwd=ROOT, text=True
        ).splitlines()
        assets = [path for path in release_paths if path in {".nojekyll", "index.html"}
                  or path.startswith(("assets/", "data/", "engine/"))]
        assets.extend(("engine/browser-observations.mjs", "engine/observation-config.mjs",
                       "engine/observations.mjs", "owner-credentials.html"))
        args.site.mkdir()
        for asset in assets:
            target = args.site / asset
            target.parent.mkdir(parents=True, exist_ok=True)
            if asset == "engine/observation-config.mjs" and args.intake_url:
                target.write_text(f"export const intakeUrl = {json.dumps(args.intake_url)};\n", encoding="utf-8")
            else:
                shutil.copyfile(ROOT / asset, target)
    print("Validated catalog scope, pricing links and coverage matrix")


if __name__ == "__main__":
    main()
