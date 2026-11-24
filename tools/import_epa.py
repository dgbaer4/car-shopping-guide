"""Development-only EPA CSV importer. No credentials, no runtime requests.
Usage: python tools/import_epa.py vehicles.csv output.json
Obtain vehicles.csv from https://www.fueleconomy.gov/feg/download.shtml
Keep EPA configurations separate from retail trims until independently mapped.
"""
import csv
import json
import sys
from pathlib import Path
from datetime import date

MAKES = {"Toyota", "Nissan", "Honda", "Hyundai", "Kia"}
SOURCE = "https://www.fueleconomy.gov/feg/download.shtml"

def positive(row, key):
    try:
        x = float(row.get(key, ""))
        return x if 0 < x < float("inf") else None
    except (ValueError, TypeError):
        return None

def convert(row):
    year = int(row["year"])
    if row["make"] not in MAKES or not 2021 <= year <= 2026:
        return None
    fuel = row.get("fuelType1", "")
    atv = row.get("atvType", "")
    if fuel == "Electricity":
        power = "Fully electric"
    elif atv == "Plug-in Hybrid":
        power = "Plug-in hybrid"
    elif atv == "Hybrid":
        power = "Traditional hybrid"
    elif fuel in {"Regular Gasoline", "Premium Gasoline", "Midgrade Gasoline"}:
        power = "Gasoline"
    else:
        return None
    v = {"id": "epa-" + row["id"], "make": row["make"], "model": row["model"],
         "year": year, "trim": "EPA configuration; retail trim unverified",
         "power": power, "drivetrain": row.get("drive") or None, "features": {},
         "verificationStatus": "Retail trim mapping pending"}
    fields = ["make", "model", "year", "power", "drivetrain"]
    if power != "Fully electric":
        v["mpg"] = positive(row, "comb08")
        fields.append("mpg")
    if power in {"Fully electric", "Plug-in hybrid"}:
        kwh = positive(row, "combE")
        v["kwhPerMile"] = kwh / 100 if kwh else None
        fields.append("kwhPerMile")
        if power == "Fully electric":
            v["electricRangeMiles"] = positive(row, "range")
            fields.append("electricRangeMiles")
    v["sources"] = [{"url": SOURCE, "fields": fields, "accessed": date.today().isoformat(),
                     "notes": "EPA vehicle ID " + row["id"] + "; import date, not independent source verification."}]
    return v

def main():
    src, dest = map(Path, sys.argv[1:])
    with src.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"id","year","make","model","fuelType1","atvType","comb08","combE","range","drive"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Missing EPA fields: " + str(required - set(reader.fieldnames or [])))
        vehicles = [v for row in reader if (v := convert(row)) is not None]
    if not vehicles or len({v["id"] for v in vehicles}) != len(vehicles):
        raise ValueError("Empty output or duplicate EPA IDs")
    dest.write_text(json.dumps({"schemaVersion":"0.3","vehicles":vehicles}, indent=2)+"\n", encoding="utf-8")
    print(f"Imported {len(vehicles)} EPA configurations")

if __name__ == "__main__":
    main()
