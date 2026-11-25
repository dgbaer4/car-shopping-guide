"""Validate selected evidence and generate a v2 reconciliation register.

Use --verify-live to check the government records behind approved evidence.
Offline runs reproduce the register from the pinned evidence and snapshots.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from urllib.request import Request, urlopen

if __package__:
    from .import_epa import convert
    from .reconcile_vehicles import EXACT, NO_RATING, configuration, configuration_value, load_json, reconcile, require, write_json
else:
    from import_epa import convert
    from reconcile_vehicles import EXACT, NO_RATING, configuration, configuration_value, load_json, reconcile, require, write_json

EPA_FIELDS = (
    "id", "year", "make", "model", "drive", "VClass", "fuelType1", "atvType",
    "cylinders", "displ", "trany", "evMotor",
)
NHTSA_FIELDS = dict(overall="OverallRating", frontal="OverallFrontCrashRating",
                     side="OverallSideCrashRating", rollover="RolloverRating")


def fetch(url):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Car-Shopping-Guide/0.3"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def epa_signature(row):
    return {key: str(row.get(key, "")) for key in EPA_FIELDS}


def verify_live(pair):
    evidence = pair["evidence"]
    expected_epa = pair["epaDetail"]
    live_epa = fetch(evidence["epaUrl"])
    require(epa_signature(live_epa) == expected_epa, f"{pair['epaId']}: EPA detail changed")
    results = fetch(evidence["url"])["Results"]
    require(len(results) == 1, f"{pair['vehicleId']}: NHTSA detail missing or ambiguous")
    detail = results[0]
    require(str(detail["VehicleId"]) == pair["vehicleId"]
            and all(detail[key] == value for key, value in pair["nativeDetailIdentity"].items())
            and {key: detail[field] for key, field in NHTSA_FIELDS.items()} == pair["rawRatings"],
            f"{pair['vehicleId']}: NHTSA detail changed")
    listing = fetch(evidence["listingUrl"])["Results"]
    require(any(str(row["VehicleId"]) == pair["vehicleId"]
                and row["VehicleDescription"] == detail["VehicleDescription"] for row in listing),
            f"{pair['vehicleId']}: official listing no longer identifies this variant")


def generate(epa, safety, register, reviewed):
    require(reviewed.get("version") == 1, "Unsupported reviewed evidence version")
    epa_index = {row["id"]: row for row in epa["vehicles"]}
    variants = {str(row["vehicleId"]): row for row in safety["records"]}
    associations = []
    for pair in reviewed["pairs"]:
        target = variants[pair["vehicleId"]]
        record = epa_index[pair["epaId"]]
        source = pair["epaDetail"]
        converted = convert(source)
        require(converted is not None and all(record[key] == converted[key] for key in
                ("id", "make", "year", "model", "power", "drivetrain")), f"{record['id']}: EPA evidence changed")
        require(pair["nativeDetailIdentity"] == target.get("nativeDetailIdentity")
                and pair["rawRatings"] == target.get("rawRatings")
                and pair["sourceConfiguration"] == target.get("configuration"),
                f"{target['vehicleId']}: NHTSA evidence changed")
        evidence = pair["evidence"]
        associations.append({
            "epaId": pair["epaId"], "vehicleId": pair["vehicleId"],
            "classification": pair.get("classification", NO_RATING if target["publicationStatus"] == "not_rated" else EXACT),
            "configuration": {"epa": configuration(record), "nhtsa": target["configuration"],
                              "nhtsaModel": target["nativeIdentity"]["model"],
                              "description": target["description"]},
            "evidence": evidence,
        })
    result = {"version": 2, "familyAliases": register["familyAliases"], "associations": associations}
    _, _, report = reconcile(epa["vehicles"], safety, result)
    by_scope = {}
    for row in report["decisions"]:
        raw = row["epaConfiguration"]
        drive = configuration_value("drivetrain", raw["drivetrain"]) if raw["drivetrain"] else None
        key = row["make"], row["year"], row["family"], raw["power"], drive
        by_scope.setdefault(key, set()).add(row["epaId"])
    competing_ids = set().union(*(ids for ids in by_scope.values() if len(ids) > 1))
    for entry in associations:
        require(entry["epaId"] not in competing_ids or entry["classification"] not in (EXACT, NO_RATING),
                f"{entry['epaId']}: multiple EPA configurations share this scope")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("epa", "safety", "aliases", "reviewed", "output"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--verify-live", action="store_true")
    args = parser.parse_args()
    epa, safety, aliases, reviewed = (load_json(path) for path in
                                    (args.epa, args.safety, args.aliases, args.reviewed))
    register = generate(epa, safety, aliases, reviewed)
    if args.verify_live:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for _ in pool.map(verify_live, reviewed["pairs"]):
                pass
    write_json(args.output, register)
    print(f"Validated {len(register['associations'])} reviewed associations")


if __name__ == "__main__":
    main()
