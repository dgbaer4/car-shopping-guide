"""Development-only NHTSA safety importer. Python 3.10+.
Usage: python tools/import_nhtsa.py epa.json safety.json
Fetch model-level variants; never automatically assign ratings to EPA trims.
"""
import json, sys, time
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import quote
from datetime import date

BASE = "https://api.nhtsa.gov/SafetyRatings"
def get(path):
    url = BASE + "/" + path + "?format=json"
    for attempt in range(3):
        try:
            with urlopen(url, timeout=30) as response:
                payload = json.load(response)
            if not isinstance(payload.get("Results"), list):
                raise ValueError("Invalid NHTSA response")
            return payload["Results"], url
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

def rating(value):
    try:
        n = int(value)
        return n if 1 <= n <= 5 else None
    except (ValueError, TypeError):
        return None

def main():
    src, dest = map(Path, sys.argv[1:])
    catalog = json.loads(src.read_text())
    groups = sorted({(v["year"], v["make"], v["model"]) for v in catalog["vehicles"]})
    records, unmatched, errors = {}, [], []
    for year, make, model in groups:
        path = f"modelyear/{year}/make/{quote(make, safe='')}/model/{quote(model, safe='')}"
        try:
            variants, url = get(path)
            if not variants:
                unmatched.append([year, make, model])
            for variant in variants:
                vid = str(variant["VehicleId"])
                if vid in records:
                    continue
                time.sleep(.25)
                results, detail_url = get("VehicleId/" + quote(vid, safe=""))
                if len(results) != 1:
                    errors.append({"vehicleId":vid,"reason":"Unexpected rating response"})
                    continue
                r = results[0]
                fields = {"overall":"OverallRating","frontal":"OverallFrontCrashRating","side":"OverallSideCrashRating","rollover":"RolloverRating"}
                records[vid] = {"vehicleId":vid,"year":year,"make":make,"model":model,
                    "description":variant.get("VehicleDescription"),
                    "ratings":{k:rating(r.get(v)) for k,v in fields.items()},
                    "source":detail_url,"accessed":date.today().isoformat(),
                    "mappingStatus":"Requires configuration match"}
        except (OSError, ValueError, KeyError) as exc:
            errors.append({"group":[year,make,model],"reason":str(exc)})
        time.sleep(.25)
    dest.write_text(json.dumps({"records":list(records.values()),"unmatched":unmatched,"errors":errors},indent=2)+"\n")
    print(f"{len(records)} variants; {len(unmatched)} unmatched groups; {len(errors)} errors")
    if errors:
        sys.exit(1)

if __name__ == "__main__":
    main()
