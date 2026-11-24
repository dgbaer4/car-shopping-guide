"""Build a catalog from EPA records and reviewed NHTSA associations.

Usage: python tools/build_catalog.py epa.json safety.json mappings.json catalog.json report.json
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sys

if __package__:
    from .reconcile_vehicles import VERIFIED, load_json, reconcile, write_json
else:
    from reconcile_vehicles import VERIFIED, load_json, reconcile, write_json


def build(epa, safety, mappings):
    records = deepcopy(epa["vehicles"])
    if not records:
        raise ValueError("Empty catalog")
    variants, associations, reconciliation = reconcile(records, safety, mappings)
    verified = {
        row["epaId"]: row["reviewedVehicleId"]
        for row in reconciliation["decisions"] if row["classification"] in VERIFIED
    }
    coverage = Counter()
    for vehicle in records:
        if vehicle["make"] not in {"Toyota", "Nissan", "Honda", "Hyundai", "Kia"}:
            raise ValueError("Out of scope record")
        for key in ("mpg", "kwhPerMile"):
            value = vehicle.get(key)
            if value is not None and (type(value) not in (float, int) or not 0 < value < float("inf")):
                raise ValueError("Invalid efficiency")
        if any(value is not None and type(value) is not bool
               for value in vehicle.get("features", {}).values()):
            raise ValueError("Invalid feature value")
        vehicle["safetyRatings"] = None
        sources = []
        for source in vehicle["sources"]:
            fields = source.get("fields", [])
            if "safetyRatings" in fields:
                source["fields"] = [field for field in fields if field != "safetyRatings"]
                if not source["fields"]:
                    continue
            sources.append(source)
        vehicle["sources"] = sources
        vid = verified.get(vehicle["id"])
        if vid is not None:
            row = variants[vid]
            evidence = associations[vehicle["id"]]["evidence"]
            vehicle["safetyRatings"] = row["ratings"].copy()
            sources.append({
                "url": row["source"], "fields": ["safetyRatings"], "accessed": row["accessed"],
                "notes": f"NHTSA VehicleId {vid}; applicability evidence: {evidence['url']}",
            })
        for key in ("mpg", "kwhPerMile", "electricRangeMiles", "body", "seats", "price", "safetyRatings"):
            coverage[key] += int(vehicle.get(key) is not None)
        coverage["backupCameraVerified"] += int(vehicle.get("features", {}).get("Backup camera") is not None)
    report = {
        "total": len(records), "byMake": dict(Counter(v["make"] for v in records)),
        "byYear": dict(Counter(v["year"] for v in records)),
        "byPower": dict(Counter(v["power"] for v in records)), "fieldCoverage": dict(coverage),
        "unmatchedSafetyGroups": safety.get("unmatched", []), "reconciliation": reconciliation,
    }
    return {"schemaVersion": "0.3", "vehicles": records}, report


if __name__ == "__main__":
    a, b, c, d, e = map(Path, sys.argv[1:])
    catalog, report = build(*(load_json(path) for path in (a, b, c)))
    write_json(d, catalog)
    write_json(e, report)
    print(f"Built {report['total']} configurations with {report['fieldCoverage']['safetyRatings']} verified safety ratings")
