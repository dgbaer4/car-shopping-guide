"""Validate the equipment sidecar against its schema and pinned EPA catalog."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "data/vehicle-equipment.schema.json").read_text())
FIELDS = tuple(SCHEMA["$defs"]["facts"]["properties"])


def validate(snapshot, catalog, digest=None):
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(snapshot)
    if digest is not None and digest != snapshot["catalogSha256"]:
        raise ValueError("Catalog SHA-256 mismatch")

    sources = snapshot["sources"]
    trims = {}
    for trim in snapshot["trims"]:
        trim_id = trim["id"]
        if trim_id in trims:
            raise ValueError(f"Duplicate trim ID: {trim_id}")
        trims[trim_id] = trim
        for fact in trim["facts"].values():
            source = sources.get(fact["source"])
            if not source or any(source[k] != trim[k] for k in ("market", "year", "make", "model")):
                raise ValueError(f"Fact source scope mismatch: {trim_id}")

    vehicles = {vehicle["id"]: vehicle for vehicle in catalog["vehicles"]}
    if len(vehicles) != len(catalog["vehicles"]):
        raise ValueError("Duplicate catalog IDs")
    seen = set()
    for link in snapshot["relationships"]:
        key = link["epaId"], link["trimId"]
        vehicle, trim = vehicles.get(key[0]), trims.get(key[1])
        if key in seen or vehicle is None or trim is None:
            raise ValueError(f"Duplicate or unresolved relationship: {key}")
        seen.add(key)
        source = sources.get(link["source"])
        if not source or any(source[k] != trim[k] for k in ("market", "year", "make", "model")):
            raise ValueError(f"Relationship source scope mismatch: {key}")
        if any(vehicle.get(k) != link["epaIdentity"][k] for k in ("model", "power", "drivetrain")):
            raise ValueError(f"EPA identity mismatch: {key}")
        if any(vehicle[k] != trim[k] for k in ("year", "make")):
            raise ValueError(f"Cross-year or cross-make relationship: {key}")
        for field in ("power", "drivetrain"):
            value = trim["facts"].get(field, {}).get("value")
            if value is not None and field == "drivetrain" and vehicle[field] not in value:
                raise ValueError(f"Drivetrain mismatch: {key}")
            if value is not None and field == "power" and vehicle[field] != value:
                raise ValueError(f"Powertrain mismatch: {key}")


def coverage(snapshot, catalog):
    trim_groups = defaultdict(list)
    epa_groups = defaultdict(list)
    for trim in snapshot["trims"]:
        trim_groups[(trim["make"],)].append(trim)
        trim_groups[(trim["make"], trim["year"])].append(trim)
        trim_groups[(trim["make"], trim["year"], trim["model"])].append(trim)
    for vehicle in catalog["vehicles"]:
        epa_groups[(vehicle["make"],)].append(vehicle)
        epa_groups[(vehicle["make"], vehicle["year"])].append(vehicle)
        epa_groups[(vehicle["make"], vehicle["year"], vehicle["model"])].append(vehicle)
    linked = {item["epaId"] for item in snapshot["relationships"]}

    def summarize(trims):
        counts = {}
        for field in FIELDS:
            values = [trim["facts"].get(field, {}).get("value") for trim in trims]
            counts[field] = dict(Counter(
                value if isinstance(value, str) and value in
                {"standard", "optional", "package-dependent", "unavailable", "unknown"}
                else "unknown" if value is None else "verified"
                for value in values
            ))
        return {"trimRecords": len(trims), "fields": counts}

    return {
        "baseline": {
            "catalogConfigurations": len(catalog["vehicles"]),
            "catalogConfigurationsWithEquipment": sum(
                any(value is not None for value in v.get("features", {}).values())
                for v in catalog["vehicles"]
            ),
            "sidecarTrimRecords": 0,
            "sidecarLinkedEpaConfigurations": 0,
        },
        "snapshot": summarize(snapshot["trims"]),
        "relationships": len(snapshot["relationships"]),
        "linkedEpaConfigurations": len(linked),
        "epaCoverage": [{"scope": list(scope), "configurations": len(rows),
                         "linked": sum(row["id"] in linked for row in rows)}
                        for scope, rows in sorted(epa_groups.items())],
        "trimCoverage": [{"scope": list(scope), **summarize(rows)}
                         for scope, rows in sorted(trim_groups.items())],
        "trims": [{"id": trim["id"], "fields": {
            field: trim["facts"].get(field, {}).get("value", "unknown") for field in FIELDS
        }} for trim in snapshot["trims"]],
        "epaConfigurationsWithAppliedEquipment": 0,
    }


def main():
    from import_vehicle_equipment import read_catalog

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("catalog", type=Path)
    args = parser.parse_args()
    catalog, digest = read_catalog(args.catalog)
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    validate(snapshot, catalog, digest)
    print(f"Validated {len(snapshot['trims'])} trims and {len(snapshot['relationships'])} EPA links")


if __name__ == "__main__":
    main()
