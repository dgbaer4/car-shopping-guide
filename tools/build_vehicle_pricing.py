"""Build condition-specific static price ranges from reviewed US evidence."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
from statistics import median

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "data/pricing"
OUTPUT = ROOT / "data/vehicle-pricing.v1.json"
CATALOG = ROOT / "data/vehicle-catalog-v0.3-pilot.json"
SCHEMA = ROOT / "data/vehicle-pricing.schema.json"
REFERENCE = "2026-11-25"
FORCAR_SLICE = INPUTS / "forcar-us-2026-11-25.v1.csv"
FORCAR_SHA256 = "d8bbc7d4765d8a51c1de01238a5ad15d7c499cc01f9aed0cd68602ee63bf4c31"
FORCAR_FIELDS = ("make", "model", "model_year", "listings", "avg_price_usd",
                 "min_price_usd", "max_price_usd")
SOURCES = {
    "forcar": {
        "name": "ForCar",
        "url": "https://forcar.org/open-data/",
        "license": "CC BY 4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "changes": "Selected US model-year cohorts and quality-screened observed ranges; linked to EPA configurations.",
    }
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_scope():
    return {(make, model): (pattern, power) for make, model, pattern, power
            in read_json(INPUTS / "used-scope.v1.json")}


def verify_forcar(download):
    raw = download.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FORCAR_SHA256:
        raise ValueError("ForCar download differs from the pinned snapshot")
    scope = read_scope()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    selected = io.StringIO(newline="")
    writer = csv.DictWriter(selected, fieldnames=FORCAR_FIELDS, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(row for row in reader if (row["make"], row["model"]) in scope
                     and 2021 <= int(row["model_year"]) <= 2026)
    if selected.getvalue() != FORCAR_SLICE.read_text(encoding="utf-8"):
        raise ValueError("ForCar input slice differs from the pinned download")


def build():
    vehicles = read_json(CATALOG)["vehicles"]
    scope = read_scope()
    rows, sources, skipped = [], dict(SOURCES), Counter()
    with FORCAR_SLICE.open(encoding="utf-8", newline="") as stream:
        for record in csv.DictReader(stream):
            make, model = record["make"], record["model"]
            pattern, power = scope[make, model]
            year, count, low, central, high = (int(record[key]) for key in (
                "model_year", "listings", "min_price_usd", "avg_price_usd", "max_price_usd"))
            if count < 15:
                skipped["smallSample"] += 1
                continue
            # Screen ranges at cohort level; the publisher supplies no raw observations or quantiles.
            if not 0 < low <= central <= high or low * 100 < 35 * central or high * 10 > 19 * central:
                skipped["wideOrInvalidRange"] += 1
                continue
            rows.append(dict(make=make, model=model, year=year, condition="used", power=power,
                             priceBasis="asking", low=low, central=central, high=high,
                             source="forcar", referenceDate=REFERENCE, methodology="observed-mean",
                             sampleSize=count, confidence="moderate" if count >= 40 else "limited",
                             pattern=pattern))

    for entry in read_json(INPUTS / "manufacturer-msrp.v1.json"):
        source = entry["source"]
        sources[source] = dict(name=entry["make"], url=entry["url"], license="Published MSRP facts",
                               changes="Selected US MSRP values summarized across included grades.")
        values = entry["prices"]
        if len(values) < 2 or any(not isinstance(value, int) or value <= 0 for value in values):
            raise ValueError("At least two documented MSRP prices are required")
        rows.append(dict(make=entry["make"], model=entry["model"], year=entry["year"],
                         condition="new", power=entry["power"], priceBasis="msrp",
                         low=min(values), central=median(values), high=max(values), source=source,
                         referenceDate=entry["date"], methodology="grade-median",
                         sampleSize=len(values), confidence="reference-only", pattern=entry["pattern"]))

    published = []
    links = set()
    for row in rows:
        pattern = row.pop("pattern")
        epa_ids = sorted(vehicle["id"] for vehicle in vehicles
                         if (vehicle["make"], vehicle["year"], vehicle["power"]) ==
                         (row["make"], row["year"], row["power"])
                         and re.fullmatch(pattern, vehicle["model"], re.IGNORECASE))
        if not epa_ids:
            skipped["unlinkedCohort"] += 1
            continue
        keys = {(epa_id, row["condition"]) for epa_id in epa_ids}
        if keys & links:
            raise ValueError(f"Overlapping pricing mappings for {row['model']} {row['year']}")
        links.update(keys)
        published.append({**row, "epaIds": epa_ids, "coverage": "model-year-family"})

    snapshot = dict(schemaVersion="1.0.0", referenceDate=REFERENCE, currency="USD", sources=sources,
                    records=sorted(published, key=lambda row: (row["make"], row["model"], row["year"], row["condition"])))
    schema = read_json(SCHEMA)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(snapshot)
    for row in snapshot["records"]:
        if not row["low"] <= row["central"] <= row["high"] or row["source"] not in sources:
            raise ValueError(f"Invalid pricing summary for {row['model']}")
    return snapshot, vehicles, links, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--verify-forcar", type=Path, help="Compare the input slice with the pinned publisher download")
    args = parser.parse_args()
    if args.verify_forcar:
        verify_forcar(args.verify_forcar)
    snapshot, vehicles, links, skipped = build()
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    if args.write:
        args.output.write_text(payload, encoding="utf-8")
    if args.output.read_text(encoding="utf-8") != payload:
        raise SystemExit("Static pricing data differs from the reviewed inputs")
    covered = {epa_id for epa_id, _ in links}
    print(f"{len(snapshot['records'])} cohorts, {len(covered)}/{len(vehicles)} priced EPA configurations; skipped {dict(skipped)}")
    for key in ("make", "year", "power"):
        totals = Counter(row[key] for row in vehicles)
        for value, total in sorted(totals.items()):
            ids = {row['id'] for row in vehicles if row[key] == value}
            print(key, value, "used", sum(i in ids and c == 'used' for i, c in links),
                  "new", sum(i in ids and c == 'new' for i, c in links), "any", len(ids & covered), "of", total)


if __name__ == "__main__":
    main()
