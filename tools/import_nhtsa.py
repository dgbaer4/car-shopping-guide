"""Acquire US NHTSA safety variants using native discovery (Python 3.10+)."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from http.client import IncompleteRead
import json
import math
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE = "https://api.nhtsa.gov/SafetyRatings"
YEARS = tuple(range(2021, 2027))
MAKES = {make.upper(): make for make in ("Toyota", "Nissan", "Honda", "Hyundai", "Kia")}
FIELDS = {
    "overall": "OverallRating",
    "frontal": "OverallFrontCrashRating",
    "side": "OverallSideCrashRating",
    "rollover": "RolloverRating",
}
CONFIG_FIELDS = ("power", "drivetrain", "body", "trim", "battery", "generation")
TRANSIENT = {408, 425, 429, 500, 502, 503, 504}


class AcquisitionError(Exception):
    def __init__(self, status, reason, http_status=None, attempts=None):
        super().__init__(reason)
        self.status = status
        self.http_status = http_status
        self.attempts = attempts


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(value, output, indent=2, allow_nan=False)
            output.write("\n")
            output.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def retry_after(value):
    if not value:
        return 0
    try:
        delay = float(value)
        return max(0, delay) if math.isfinite(delay) else 0
    except ValueError:
        try:
            return max(0, parsedate_to_datetime(value).timestamp() - time.time())
        except (ValueError, OverflowError, TypeError):
            return 0


def reject_nonfinite(value):
    raise ValueError(f"Non-finite JSON value: {value}")


def rows(payload):
    result = payload["Results"]
    if (not isinstance(result, list) or any(not isinstance(row, dict) for row in result)
            or type(payload.get("Count")) is not int or payload["Count"] != len(result)):
        raise ValueError("Invalid NHTSA result count or rows")
    return result


class Client:
    def __init__(self, cache, *, timeout=12, interval=0.3, attempts=3,
                 seconds=2400, max_age_days=30, force_refresh=False, opener=urlopen):
        self.cache = cache
        self.timeout = timeout
        self.interval = interval
        self.attempts = attempts
        self.opener = opener
        self.max_age_days = max_age_days
        self.force_refresh = force_refresh
        self.deadline = time.monotonic() + seconds
        self.next_request = 0
        self.counts = Counter()

    def get(self, path, validate):
        url = BASE + "/" + path + "?format=json"
        entry = self.cache / "v1" / (sha256(url.encode()).hexdigest() + ".json")
        refresh = False
        try:
            cached = json.loads(entry.read_text(encoding="utf-8"), parse_constant=reject_nonfinite)
            if cached["source"] != url:
                raise ValueError("Cache URL mismatch")
            accessed = datetime.fromisoformat(cached["accessed"]).date().isoformat()
            fetched = datetime.fromisoformat(cached.get("fetchedAt", accessed))
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if fetched > now or fetched.date().isoformat() != accessed:
                raise ValueError("Cache acquisition timestamp mismatch")
            result = validate(rows(cached["payload"]))
            stale = bool(self.max_age_days and
                         (now - fetched).total_seconds() >= self.max_age_days * 86400)
            if not stale and not self.force_refresh:
                self.counts["cacheHits"] += 1
                return result, url, accessed
            refresh = True
            if stale:
                self.counts["staleCacheEntries"] += 1
            if self.force_refresh:
                self.counts["forcedRefreshes"] += 1
        except FileNotFoundError:
            pass
        except (ValueError, KeyError, TypeError):
            self.counts["invalidCacheEntries"] += 1

        for attempt in range(1, self.attempts + 1):
            delay = max(0, self.next_request - time.monotonic())
            if time.monotonic() + delay >= self.deadline:
                raise AcquisitionError("deferred", "Request budget exhausted or retry deferred",
                                       attempts=attempt - 1)
            time.sleep(delay)
            self.next_request = time.monotonic() + self.interval
            self.counts["httpAttempts"] += 1
            try:
                request = Request(url, headers={"Accept": "application/json",
                                                "User-Agent": "CarShoppingGuide-catalog/1.0"})
                with self.opener(request, timeout=min(
                        self.timeout, max(0.01, self.deadline - time.monotonic()))) as response:
                    payload = json.load(response, parse_constant=reject_nonfinite)
                result = validate(rows(payload))
            except HTTPError as exc:
                code = exc.code
                wait = retry_after(exc.headers.get("Retry-After") if exc.headers else None)
                exc.close()
                if code not in TRANSIENT:
                    raise AcquisitionError("permanent_failure", f"HTTP {code}", code, attempt) from exc
                self.next_request = max(self.next_request, time.monotonic() + wait)
                error = AcquisitionError("transient_failure", f"HTTP {code}", code, attempt)
            except (URLError, TimeoutError, ConnectionError, IncompleteRead) as exc:
                error = AcquisitionError("transient_failure", str(exc), attempts=attempt)
            except (ValueError, KeyError, TypeError) as exc:
                raise AcquisitionError("invalid_response", str(exc), attempts=attempt) from exc
            else:
                fetched = datetime.now(timezone.utc)
                accessed = fetched.date().isoformat()
                write_json(entry, {"source": url, "accessed": accessed,
                                   "fetchedAt": fetched.isoformat(), "payload": payload})
                if refresh:
                    self.counts["refreshedResponses"] += 1
                    if path.startswith("VehicleId/") and result is not None:
                        self.counts["refreshedRecords"] += 1
                return result, url, accessed
            if attempt == self.attempts or self.next_request >= self.deadline:
                raise error
            self.counts["retries"] += 1
            self.next_request = max(self.next_request, time.monotonic() + 2 ** (attempt - 1))


def name(row, field):
    value = row[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid {field}")
    return value


def vehicle_id(row):
    value = row["VehicleId"]
    if type(value) is int and value > 0:
        return str(value)
    if isinstance(value, str) and value.isascii() and value.isdecimal() and int(value) > 0:
        return str(int(value))
    raise ValueError("Invalid native VehicleId")


def discovery(rows, year, make=None):
    names = set()
    for row in rows:
        if row["ModelYear"] != year or (make and name(row, "Make") != make):
            raise ValueError("Discovery row outside requested scope")
        names.add(name(row, "Model" if make else "Make"))
    return sorted(names)


def variant_rows(rows):
    return [(vehicle_id(row), name(row, "VehicleDescription")) for row in rows]


def detail_rows(rows, vid):
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError("Expected one result for native VehicleId")
    row = rows[0]
    if vehicle_id(row) != vid or type(row["ModelYear"]) is not int:
        raise ValueError("Invalid detail ID or model year")
    name(row, "Make")
    name(row, "Model")
    name(row, "VehicleDescription")
    return row


def rating(value):
    if type(value) is int and 1 <= value <= 5:
        return value
    if isinstance(value, str) and value.strip() in {"1", "2", "3", "4", "5"}:
        return int(value)
    return None


def normalized(value):
    return " ".join(value.casefold().split())


def identity_signature(identity):
    return (identity["year"], *(normalized(identity[key]) for key in
                                ("make", "model", "description")))


def configuration(description, source, accessed):
    # The source description refers to this exact VehicleId.
    evidence = {}
    attributes = dict.fromkeys(CONFIG_FIELDS)

    def capture(field, examples):
        matches = [(match.group(), value) for pattern, value in examples
                   for match in re.finditer(pattern, description, re.IGNORECASE)]
        if matches and len({value for _, value in matches}) == 1:
            token, value = matches[0]
            attributes[field] = value
            evidence[field] = {"source": source, "accessed": accessed,
                               "field": "VehicleDescription", "token": token}

    capture("power", [
        (r"\b(?:PHEV|PLUG[- ]IN HYBRID)\b", "Plug-in hybrid"),
        (r"\bHEV\b", "Traditional hybrid"),
        (r"\b(?:BEV|ELECTRIC)\b", "Fully electric"),
        (r"\bGASOLINE\b", "Gasoline"),
    ])
    capture("drivetrain", [(rf"\b{token}\b", token)
                           for token in ("AWD", "4WD", "FWD", "RWD", "2WD")])
    capture("body", [
        (r"\bSUV\b", "SUV"),
        (r"\b(?:[345]\s+HB|HATCHBACK)\b", "Hatchback"),
        (r"\bSEDAN\b", "Sedan"),
        (r"\bVAN\b", "Van"),
        (r"\bPU/CC\b", "Crew cab pickup"),
        (r"\bPU/EC\b", "Extended cab pickup"),
    ])
    batteries = list(re.finditer(r"\b(\d+(?:\.\d+)?)\s*kWh\s+battery\b",
                                 description, re.IGNORECASE))
    if batteries and len({match[1] for match in batteries}) == 1:
        battery = batteries[0]
        attributes["battery"] = f"{battery[1]} kWh"
        evidence["battery"] = {"source": source, "accessed": accessed,
                               "field": "VehicleDescription", "token": battery.group()}
    return attributes, evidence


def acquire(client, years, makes, checkpoint):
    errors, unsupported, scopes = [], [], []
    variants, records = {}, {}
    attempted_details = set()
    ids_by_scope = {}
    counts = Counter(models=0)

    def query(path, validate, stage, **identity):
        try:
            result, url, accessed = client.get(path, validate)
        except AcquisitionError as exc:
            errors.append({"stage": stage, **identity, "status": exc.status,
                           "source": BASE + "/" + path + "?format=json",
                           "httpStatus": exc.http_status, "attempts": exc.attempts,
                           "reason": str(exc)})
            return None
        if not result:
            unsupported.append({"stage": stage, **identity, "source": url,
                                "accessed": accessed, "reason": "empty_results"})
        return result, url, accessed

    def snapshot(finished):
        handoff, conflicts = {}, []
        for vid, identities in sorted(variants.items(), key=lambda item: int(item[0])):
            record = records.get(vid)
            signatures = {identity_signature(identity) for identity in identities}
            if len(signatures) != 1 or (record and identity_signature(record) not in signatures):
                conflicts.append({"stage": "identity", "vehicleId": vid,
                                  "status": "identity_conflict",
                                  "source": BASE + f"/VehicleId/{vid}?format=json",
                                  "reason": "Native listings or rating detail disagree",
                                  "discovery": identities, "record": record})
                continue
            if record:
                listing = min(identities, key=lambda item: item["source"])
                identity = {key: listing[key] for key in
                            ("make", "year", "model", "source", "accessed")}
                handoff[vid] = {**record, "nativeIdentity": identity}
        handoff_records = list(handoff.values())
        scope_report = []
        for scope in scopes:
            entry = scope.copy()
            ids = ids_by_scope.get((scope["year"], scope["make"]), set())
            if "models" in scope:
                usable = ids & handoff.keys()
                entry.update({"variants": len(ids), "records": len(usable),
                              "rated": sum(handoff[i]["status"] == "rated" for i in usable),
                              "unrated": sum(handoff[i]["status"] == "unrated" for i in usable),
                              "detailUnavailable": sum(handoff[i]["status"] == "detail_unavailable"
                                                       for i in usable)})
                if (ids - usable) or "status" not in scope:
                    entry["status"] = "partial"
            scope_report.append(entry)
        all_errors = errors + conflicts
        report = {
            "complete": finished and not all_errors,
            "discoveryFinished": finished,
            "scope": {"market": "US", "years": years, "makes": [MAKES[m] for m in makes]},
            "counts": {**counts, "uniqueVariants": len(variants),
                       "records": len(handoff), "rated": sum(r["status"] == "rated" for r in handoff_records),
                       "unrated": sum(r["status"] == "unrated" for r in handoff_records),
                       "detailUnavailable": sum(r["status"] == "detail_unavailable"
                                                for r in handoff_records),
                       "unsupported": len(unsupported), "errors": len(all_errors),
                       "identityConflicts": len(conflicts)},
            "errorsByStatus": dict(Counter(e["status"] for e in all_errors)),
            "requests": dict(client.counts),
            "byYearMake": scope_report,
            "configurationCounts": {key: sum(r["configuration"][key] is not None for r in handoff_records)
                                    for key in CONFIG_FIELDS},
            "publicationCounts": dict(Counter(r["publicationStatus"] for r in handoff_records)),
        }
        checkpoint({"schemaVersion": "nhtsa-safety/1.1", "coverage": report,
                    "scope": report["scope"], "records": handoff_records,
                    "pendingVariants": [{"vehicleId": vid, "discovery": variants[vid]}
                                        for vid in sorted(variants.keys() - records.keys(), key=int)],
                    "unmatched": [], "unsupported": unsupported, "errors": all_errors})
        return report["complete"]

    try:
        for year in years:
            year_path = f"modelyear/{year}"
            native = query(year_path, lambda r: discovery(r, year), "year", year=year)
            if native is None:
                continue
            for make in makes:
                scope = {"year": year, "make": MAKES[make]}
                scopes.append(scope)
                if make not in native[0]:
                    unsupported.append({"stage": "make", **scope, "source": native[1],
                                        "accessed": native[2], "reason": "not_listed"})
                    scope["status"] = "not_listed"
                    continue
                error_start = len(errors)
                ids = ids_by_scope.setdefault((year, MAKES[make]), set())
                make_path = f"{year_path}/make/{quote(make, safe='')}"
                models = query(make_path, lambda r: discovery(r, year, make), "make", **scope)
                if models is None:
                    scope["status"] = "failed"
                    continue
                scope["models"] = len(models[0])
                counts["models"] += scope["models"]
                for model in models[0]:
                    model_path = f"{make_path}/model/{quote(model, safe='')}"
                    listing = query(model_path, variant_rows, "model", year=year,
                                    make=MAKES[make], model=model)
                    if listing is None:
                        continue
                    listed, listing_url, listed_date = listing
                    for vid, description in listed:
                        ids.add(vid)
                        context = {"year": year, "make": MAKES[make], "model": model,
                                   "description": description, "source": listing_url,
                                   "accessed": listed_date}
                        aliases = variants.setdefault(vid, [])
                        if context not in aliases:
                            aliases.append(context)
                        if vid in attempted_details:
                            continue
                        attempted_details.add(vid)
                        detail = query(f"VehicleId/{vid}",
                                       lambda r: detail_rows(r, vid),
                                       "vehicle", vehicleId=vid, year=year, make=MAKES[make])
                        if detail is None:
                            continue
                        row, source, accessed = detail
                        fields = row or {}
                        ratings = {key: rating(fields.get(field)) for key, field in FIELDS.items()}
                        native_ratings = {key: rating(value) for key, value in fields.items()
                                          if "rating" in key.lower()}
                        raw_ratings = {key: fields.get(field) for key, field in FIELDS.items()}
                        publication = ("published" if any(v is not None for v in ratings.values())
                                       else "not_rated" if all(isinstance(v, str) and
                                                              normalized(v) == "not rated"
                                                              for v in raw_ratings.values())
                                       else "unknown")
                        detail_description = fields.get("VehicleDescription", description)
                        config, evidence = configuration(detail_description, source, accessed) if row else (
                            dict.fromkeys(CONFIG_FIELDS), {})
                        records[vid] = {
                            "vehicleId": vid, "year": fields.get("ModelYear", year),
                            "make": fields.get("Make", MAKES[make]).strip().title(),
                            "nativeDetailIdentity": ({key: fields[key] for key in
                                                      ("Make", "ModelYear", "Model", "VehicleDescription")}
                                                     if row else None),
                            "model": fields.get("Model", model),
                            "description": detail_description,
                            "ratings": ratings,
                            "nativeRatings": native_ratings,
                            "rawRatings": raw_ratings,
                            "rawNativeRatings": {key: fields[key] for key in native_ratings},
                            "publicationStatus": publication,
                            "configuration": config,
                            "configurationEvidence": evidence,
                            "nativeSafetyEquipment": {key: fields[key] for key in (
                                "NHTSAElectronicStabilityControl", "NHTSAForwardCollisionWarning",
                                "NHTSALaneDepartureWarning") if key in fields},
                            "status": ("detail_unavailable" if row is None else
                                       "rated" if any(v is not None for v in native_ratings.values())
                                       else "unrated"),
                            "discovery": aliases, "source": source, "accessed": accessed,
                            "mappingStatus": "Requires configuration match",
                        }
                scope["status"] = "partial" if len(errors) > error_start else "queried"
                print(f"{year} {make}: {scope['models']} models, {len(ids)} variants, "
                      f"{len(errors) - error_start} errors", file=sys.stderr, flush=True)
                snapshot(False)
    except KeyboardInterrupt:
        errors.append({"stage": "run", "status": "interrupted", "reason": "Interrupted"})
        snapshot(False)
        return False
    return snapshot(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--year", type=int, choices=YEARS, action="append")
    parser.add_argument("--make", type=str.upper, choices=sorted(MAKES), action="append")
    parser.add_argument("--seconds", type=float, default=2400)
    parser.add_argument("--cache-max-age-days", type=float, default=30,
                        help="Response lifetime in days. Use 0 to reuse valid responses indefinitely.")
    parser.add_argument("--force-refresh", action="store_true",
                        help="Reacquire valid cached responses in the selected scope.")
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("--seconds must be positive and finite")
    if not math.isfinite(args.cache_max_age_days) or args.cache_max_age_days < 0:
        parser.error("--cache-max-age-days must be nonnegative and finite")
    destinations = [p.resolve() for p in (args.output, args.report) if p is not None]
    if len(set(destinations)) != len(destinations):
        parser.error("output and report must be different files")

    def checkpoint(data):
        write_json(args.output, data)
        if args.report:
            write_json(args.report, {"schemaVersion": data["schemaVersion"], **data["coverage"],
                                     "unsupported": data["unsupported"], "errors": data["errors"]})

    client = Client(args.cache, seconds=args.seconds, max_age_days=args.cache_max_age_days,
                    force_refresh=args.force_refresh)
    complete = acquire(client, sorted(set(args.year or YEARS)),
                       sorted(set(args.make or MAKES)), checkpoint)
    return 0 if complete else 2


if __name__ == "__main__":
    sys.exit(main())
