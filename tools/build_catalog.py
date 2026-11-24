"""Build a catalog from EPA records and explicitly reviewed NHTSA mappings.
Usage: python tools/build_catalog.py epa.json safety.json mappings.json catalog.json report.json
Mappings: object keyed by EPA id, value {vehicleId, evidenceUrl, reviewed: true}.
"""
import json, sys
from pathlib import Path
from collections import Counter

def build(epa, safety, mappings):
    records = epa["vehicles"]
    if not records or len({v["id"] for v in records}) != len(records):
        raise ValueError("Empty catalog or duplicate IDs")
    if safety.get("errors"):
        raise ValueError("Safety acquisition has unresolved errors")
    variants = {str(v["vehicleId"]): v for v in safety["records"]}
    if set(mappings) - {v["id"] for v in records}:
        raise ValueError("Unknown EPA mapping ID")
    coverage = Counter()
    for v in records:
        if v["make"] not in {"Toyota","Nissan","Honda","Hyundai","Kia"} or not 2021 <= v["year"] <= 2026:
            raise ValueError("Out of scope record")
        if not v.get("sources") or not all(s.get("url","").startswith("https://") for s in v["sources"]):
            raise ValueError("Missing source")
        for key in ("mpg","kwhPerMile"):
            x = v.get(key)
            if x is not None and (type(x) not in (float,int) or not 0 < x < float("inf")):
                raise ValueError("Invalid efficiency")
        if any(x is not None and type(x) is not bool for x in v.get("features",{}).values()):
            raise ValueError("Invalid feature value")
        m = mappings.get(v["id"])
        if m:
            r = variants[str(m["vehicleId"])]
            if m.get("reviewed") is not True or not m.get("evidenceUrl","").startswith("https://") or (r["year"],r["make"]) != (v["year"],v["make"]):
                raise ValueError("Unverified mapping")
            if any(x is not None and (type(x) is not int or not 1 <= x <= 5) for x in r["ratings"].values()):
                raise ValueError("Invalid safety rating")
            v["safetyRatings"] = r["ratings"]
            v["sources"].append({"url":r["source"],"fields":["safetyRatings"],"accessed":r["accessed"],"notes":m["evidenceUrl"]})
        for k in ("mpg","kwhPerMile","electricRangeMiles","body","seats","price","safetyRatings"):
            coverage[k] += int(v.get(k) is not None)
        coverage["backupCameraVerified"] += int(v.get("features",{}).get("Backup camera") is not None)
    report = {"total":len(records),"byMake":dict(Counter(v["make"] for v in records)), "byYear":dict(Counter(v["year"] for v in records)), "byPower":dict(Counter(v["power"] for v in records)), "fieldCoverage":dict(coverage),"unmatchedSafetyGroups":safety.get("unmatched",[])}
    return {"schemaVersion":"0.3","vehicles":records},report

if __name__ == "__main__":
    a,b,c,d,e = map(Path,sys.argv[1:])
    catalog,report = build(*(json.loads(p.read_text()) for p in (a,b,c)))
    for p,obj in ((d,catalog),(e,report)):
        p.write_text(json.dumps(obj,indent=2,allow_nan=False)+"\n")
    print(json.dumps(report,indent=2))
