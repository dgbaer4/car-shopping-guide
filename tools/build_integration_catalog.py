"""Regenerate and validate the v0.3 development catalog from pinned inputs."""

import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from build_catalog import build as build_safety_catalog
from generate_reconciliation_associations import generate
from import_vehicle_equipment import build as build_equipment, read_catalog
from reconcile_vehicles import NO_RATING, load_json
from validate_vehicle_equipment import FIELDS, coverage, validate

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DEV = DATA / "development"


def encode(value, compact=False):
    if compact:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def same(actual, expected, label):
    if actual != expected:
        raise ValueError(f"{label} drifted from the pinned artifact")


def build():
    baseline, v2_digest = read_catalog(DEV / "vehicle-catalog-2026-11-24.v2.json.gz")
    safety, _ = read_catalog(DEV / "nhtsa-safety-2026-11-24.v1.1.json.gz")
    register = load_json(DATA / "vehicle-reconciliation-mappings.v3.json")
    reviewed = load_json(DEV / "nhtsa-reviewed-evidence.v2.json")

    # The historical catalog preserves each original EPA row and source.
    epa = {"schemaVersion": "0.3", "vehicles": [
        {**{k: v for k, v in row.items() if k not in {"sources", "safetyRatings"}},
         "sources": [source for source in row["sources"] if "safetyRatings" not in source["fields"]]}
        for row in baseline["vehicles"]
    ]}
    generated_register = generate(epa, safety, register, reviewed)
    same(encode(generated_register), (DATA / "vehicle-reconciliation-mappings.v3.json").read_text(),
         "Safety association register")
    catalog, report = build_safety_catalog(epa, safety, generated_register)
    v3 = DEV / "vehicle-catalog-2026-11-24.v3.json.gz"
    same(encode(catalog).encode("utf-8"), gzip.decompress(v3.read_bytes()), "Safety catalog")

    equipment_dir = DEV / "equipment"
    equipment = build_equipment(load_json(equipment_dir / "vehicle-equipment-evidence.v1.json"), baseline, v2_digest)
    snapshot_file = equipment_dir / "vehicle-equipment.v1.json"
    same(json.dumps(equipment, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
         snapshot_file.read_text(encoding="utf-8"), "Equipment sidecar")
    same(json.dumps(coverage(equipment, baseline), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
         (ROOT / "docs/vehicle-equipment-coverage.v1.json").read_text(encoding="utf-8"), "Equipment coverage")
    validate(equipment, baseline, v2_digest)
    validate(equipment, catalog)
    links = defaultdict(list)
    for relationship in equipment["relationships"]:
        links[relationship["epaId"]].append(relationship["trimId"])

    unrated = {row["epaId"] for row in report["reconciliation"]["decisions"]
               if row["classification"] == NO_RATING}
    configuration_fields = {"body", "drivetrain", "power", "seats"}
    for vehicle in catalog["vehicles"]:
        vehicle["features"] = {**dict.fromkeys(set(FIELDS) - configuration_fields), **vehicle["features"]}
        vehicle["possibleTrimIds"] = links[vehicle["id"]]
        vehicle["safetyEvidence"] = (
            "review-required" if vehicle["safetyRatings"] is not None else
            "no-published-rating" if vehicle["id"] in unrated else "unknown"
        )

    schema = load_json(DATA / "vehicle-catalog.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(catalog)
    return catalog


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", default=DATA / "vehicle-catalog-v0.3-integration.json")
    args = parser.parse_args()
    catalog = build()
    args.output.write_text(encode(catalog, compact=True), encoding="utf-8")
    print(f"Validated and built {len(catalog['vehicles'])} configurations")
