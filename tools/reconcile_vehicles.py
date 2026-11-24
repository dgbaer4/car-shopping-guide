"""Reconcile EPA catalog records and NHTSA ratings without network access."""
import argparse
from collections import Counter
import csv
from datetime import date
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

CONFIG_FIELDS = ("model", "trim", "power", "drivetrain", "body", "battery", "generation")
REQUIRED_CONFIGURATION = ("power", "drivetrain", "body")
POWERTRAINS = {"Gasoline", "Traditional hybrid", "Plug-in hybrid", "Fully electric"}
DRIVETRAINS = {
    "all wheel drive": "awd",
    "front wheel drive": "fwd",
    "rear wheel drive": "rwd",
    "4 wheel drive": "4wd",
    "four wheel drive": "4wd",
}
RATING_FIELDS = {"overall", "frontal", "side", "rollover"}
EXACT = "verified_configuration_match"
APPLICABLE = "verified_rating_applicability"
NO_RATING = "no_published_safety_rating"
REVIEW = "model_family_match_requires_review"
AMBIGUOUS = "ambiguous"
UNMATCHED = "unmatched"
VERIFIED = {EXACT, APPLICABLE}
CLASSIFICATIONS = (EXACT, APPLICABLE, REVIEW, AMBIGUOUS, UNMATCHED, NO_RATING)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def normalized(value):
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def provenance(url, accessed, domain=None):
    parsed = urlsplit(url if isinstance(url, str) else "")
    host = parsed.hostname or ""
    require(parsed.scheme == "https" and host and parsed.username is None
            and parsed.password is None and (domain is None or host == domain
                                             or host.endswith("." + domain)),
            f"Invalid source URL: {url!r}")
    require(isinstance(accessed, str) and date.fromisoformat(accessed).isoformat() == accessed,
            f"Invalid source date: {accessed!r}")
    return parsed


def identity(record):
    make, year, model = (record.get(k) for k in ("make", "year", "model"))
    require(nonempty(make) and type(year) is int and 2021 <= year <= 2026
            and nonempty(model) and normalized(model), f"Invalid vehicle identity: {record!r}")
    return make.casefold(), year, normalized(model)


def vehicle_id(value):
    require(type(value) in (str, int) and re.fullmatch(r"[1-9][0-9]*", str(value)),
            f"Invalid NHTSA VehicleId: {value!r}")
    return str(value)


def configuration(record):
    return {field: record.get(field) for field in CONFIG_FIELDS}


def configuration_value(field, value):
    key = normalized(value)
    return DRIVETRAINS.get(key, key) if field == "drivetrain" else key


def read_register(register):
    # The Stage A workflow passes an empty legacy object.
    if register == {}:
        return {}, {}
    require(type(register.get("version")) is int and register["version"] == 1,
            "Unsupported mapping version")
    aliases = {}
    for entry in register["familyAliases"]:
        side = entry.get("source")
        require(side in ("epa", "nhtsa") and nonempty(entry.get("reason")),
                "Alias requires a source and explanation")
        provenance(entry.get("evidenceUrl"), entry.get("accessed"),
                   "fueleconomy.gov" if side == "epa" else "nhtsa.gov")
        if "comparisonUrl" in entry:
            provenance(entry["comparisonUrl"], entry["accessed"],
                       "nhtsa.gov" if side == "epa" else "fueleconomy.gov")
        key = (side, *identity(entry))
        family = entry.get("family")
        require(nonempty(family) and normalized(family) and key not in aliases,
                f"Invalid or competing family mapping: {key!r}")
        aliases[key] = normalized(family)
    associations = {}
    exact_targets = set()
    for entry in register["associations"]:
        epa_id = entry.get("epaId")
        require(isinstance(epa_id, str) and re.fullmatch(r"epa-[1-9][0-9]*", epa_id)
                and epa_id not in associations, f"Invalid or competing association: {epa_id!r}")
        require(entry.get("classification") in (*VERIFIED, NO_RATING),
                f"{epa_id}: unsupported association classification")
        vid = vehicle_id(entry.get("vehicleId"))
        if entry["classification"] == EXACT:
            require(vid not in exact_targets, f"{vid}: multiple exact associations require applicability review")
            exact_targets.add(vid)
        reviewed = entry.get("configuration")
        require(isinstance(reviewed, dict) and reviewed.keys() == {"epa", "nhtsa", "nhtsaModel", "description"}
                and isinstance(reviewed["epa"], dict) and reviewed["epa"].keys() == set(CONFIG_FIELDS)
                and isinstance(reviewed["nhtsa"], dict)
                and nonempty(reviewed["nhtsaModel"]) and nonempty(reviewed["description"]),
                f"{epa_id}: missing reviewed configuration snapshot")
        evidence = entry["evidence"]
        provenance(evidence.get("url"), evidence.get("accessed"), "nhtsa.gov")
        require(nonempty(evidence.get("reviewer")) and nonempty(evidence.get("statement")),
                f"{epa_id}: association needs a reviewer and an applicability statement")
        fields = evidence.get("ratingFields")
        require(isinstance(fields, list) and all(isinstance(field, str) for field in fields)
                and len(fields) == len(set(fields)) and set(fields) <= RATING_FIELDS
                and bool(fields) == (entry["classification"] in VERIFIED),
                f"{epa_id}: invalid reviewed rating fields")
        associations[epa_id] = entry
    return aliases, associations


def index_safety(records):
    variants = {}
    for row in records:
        vid = vehicle_id(row.get("vehicleId"))
        require(vid not in variants, f"Duplicate NHTSA VehicleId: {vid}")
        query_identity = identity(row)
        source = provenance(row.get("source"), row.get("accessed"), "nhtsa.gov")
        require(source.path.rstrip("/").lower() == f"/safetyratings/vehicleid/{vid}",
                f"{vid}: rating URL must identify the same VehicleId")
        ratings = row.get("ratings")
        require(isinstance(ratings, dict) and ratings.keys() == RATING_FIELDS
                and all(v is None or type(v) is int and 1 <= v <= 5 for v in ratings.values()),
                f"{vid}: invalid rating values or fields")
        native = row.get("nativeIdentity")
        if native is not None:
            require(identity(native)[:2] == query_identity[:2],
                    f"{vid}: native make or model year conflicts with the record")
            identity_source = provenance(native.get("source"), row["accessed"], "nhtsa.gov")
            if identity_source.hostname == "api.nhtsa.gov":
                path = unquote(identity_source.path.rstrip("/")).casefold()
                expected = f"/safetyratings/modelyear/{native['year']}/make/{native['make']}/model/{native['model']}"
                require(path == expected.casefold(),
                        f"{vid}: native identity URL does not identify the listed variant group")
            require(nonempty(row.get("description")), f"{vid}: missing native description")
        variants[vid] = row
    return variants


def validate_association(epa, variant, entry, epa_key, nhtsa_key):
    label = f"{epa['id']} / {variant['vehicleId']}"
    native = variant.get("nativeIdentity")
    require(native is not None, f"{label}: query-only NHTSA identity cannot establish applicability")
    require(epa_key[:2] == nhtsa_key[:2], f"{label}: manufacturer or model year conflict")
    require(epa_key == nhtsa_key, f"{label}: model family conflict")

    reviewed = entry["configuration"]
    target = variant.get("configuration")
    require(isinstance(target, dict) and set(target) <= set(CONFIG_FIELDS) - {"model"}
            and all(value is None or nonempty(value) for value in target.values()),
            f"{label}: missing or invalid NHTSA configuration")
    require(reviewed == {"epa": configuration(epa), "nhtsa": target,
                         "nhtsaModel": native["model"], "description": variant["description"]},
            f"{label}: source configuration changed since review")
    require(epa.get("power") in POWERTRAINS and target.get("power") in POWERTRAINS,
            f"{label}: missing or invalid powertrain")
    for field in CONFIG_FIELDS[1:]:
        left, right = epa.get(field), target.get(field)
        if field in REQUIRED_CONFIGURATION:
            require(nonempty(right), f"{label}: missing NHTSA {field}")
        # A documented applicability statement can resolve an attribute absent in EPA.
        if entry["classification"] == EXACT and field in REQUIRED_CONFIGURATION:
            require(nonempty(left), f"{label}: missing EPA {field} for an exact match")
        if field == "trim" and left == "EPA configuration; retail trim unverified":
            left = None
        if left is not None and right is not None:
            require(nonempty(left) and configuration_value(field, left) == configuration_value(field, right),
                    f"{label}: conflicting {field}")

    published = {field for field, value in variant["ratings"].items() if value is not None}
    require(published == set(entry["evidence"]["ratingFields"]),
            f"{label}: published rating fields changed since review")
    if entry["classification"] == NO_RATING:
        require(not published and variant.get("publicationStatus") == "not_rated",
                f"{label}: no published ratings must be explicitly confirmed by NHTSA")
    else:
        require(published and variant.get("publicationStatus") != "not_rated",
                f"{label}: verified mapping lacks a published rating")


def reconcile(records, safety, register):
    aliases, associations = read_register(register)
    variants = index_safety(safety["records"])
    candidates = {}
    nhtsa_keys = {}
    for vid, row in variants.items():
        key = identity(row.get("nativeIdentity") or row)
        family = aliases.get(("nhtsa", *key), key[2])
        # The old importer echoes the EPA query. Use EPA aliases in that case.
        if row.get("nativeIdentity") is None:
            family = aliases.get(("epa", *key), key[2])
        nhtsa_keys[vid] = (*key[:2], family)
        candidates.setdefault(nhtsa_keys[vid], []).append(vid)

    ids = set()
    decisions = []
    totals = Counter(dict.fromkeys(CLASSIFICATIONS, 0))
    coverage = {}
    for epa in records:
        epa_id = epa.get("id")
        require(isinstance(epa_id, str) and re.fullmatch(r"epa-[1-9][0-9]*", epa_id)
                and epa_id not in ids, f"Invalid or duplicate EPA ID: {epa_id!r}")
        ids.add(epa_id)
        require(epa.get("sources"), f"{epa_id}: missing EPA source")
        for source in epa["sources"]:
            provenance(source.get("url"), source.get("accessed"))
        require(any(urlsplit(source["url"]).hostname in
                    {"www.fueleconomy.gov", "fueleconomy.gov", "www.epa.gov", "epa.gov"}
                    for source in epa["sources"]), f"{epa_id}: missing authoritative EPA provenance")
        key = identity(epa)
        family = aliases.get(("epa", *key), key[2])
        family_key = (*key[:2], family)
        matches = sorted(candidates.get(family_key, ()), key=int)
        entry = associations.get(epa_id)
        vid = vehicle_id(entry["vehicleId"]) if entry is not None else None
        status = UNMATCHED
        reason = "No candidate in this NHTSA input"
        if len(matches) == 1:
            status, reason = REVIEW, "Family candidate requires applicability evidence"
        elif matches:
            status, reason = AMBIGUOUS, "Multiple family candidates require configuration review"
        if entry is not None:
            require(entry["configuration"]["epa"] == configuration(epa),
                    f"{epa_id}: EPA configuration changed since review")
            if vid in variants:
                validate_association(epa, variants[vid], entry, family_key, nhtsa_keys[vid])
                status, reason = entry["classification"], entry["evidence"]["statement"]
            else:
                status = REVIEW if len(matches) <= 1 else AMBIGUOUS
                reason = f"Reviewed VehicleId {vid} is absent from this NHTSA input"
        decisions.append({
            "epaId": epa_id, "make": epa["make"], "year": epa["year"],
            "epaConfiguration": configuration(epa), "epaSources": epa["sources"], "family": family,
            "classification": status, "reason": reason, "reviewedVehicleId": vid,
            "candidates": [{
                "vehicleId": item, "model": variants[item]["model"],
                "nativeIdentity": variants[item].get("nativeIdentity"),
                "description": variants[item].get("description"),
                "source": variants[item]["source"],
            } for item in matches],
        })
        totals[status] += 1
        year_counts = coverage.setdefault(epa["make"], {}).setdefault(
            str(epa["year"]), dict.fromkeys(CLASSIFICATIONS, 0))
        year_counts[status] += 1
    require(not associations.keys() - ids, "Unknown EPA ID in association register")
    report = {
        "coverage": {"total": len(records), "byClassification": dict(totals),
                     "byMakeAndYear": coverage},
        "acquisition": {"nhtsaVariants": len(variants),
                        "queryOnlyVariants": sum(v.get("nativeIdentity") is None for v in variants.values()),
                        "unmatchedGroups": safety.get("unmatched", []),
                        "errors": safety.get("errors", []), "scope": safety.get("scope")},
        "decisions": sorted(decisions, key=lambda row: int(row["epaId"][4:])),
    }
    return variants, associations, report


def load_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON object key: {key!r}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8")


def write_review_csv(path, report):
    groups = {}
    for row in report["decisions"]:
        if row["classification"] in (*VERIFIED, NO_RATING):
            continue
        key = (
            row["make"], row["year"], row["epaConfiguration"]["model"], row["family"],
            row["classification"], row["reason"],
            " ".join(candidate["vehicleId"] for candidate in row["candidates"]),
        )
        groups.setdefault(key, []).append(row["epaId"])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("make", "year", "epa_model", "candidate_family", "classification",
                         "reason", "candidate_vehicle_ids", "epa_ids"))
        writer.writerows((*key, " ".join(groups[key])) for key in sorted(groups))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("epa", "safety", "mappings", "report"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--review-csv", type=Path)
    args = parser.parse_args()
    _, _, report = reconcile(load_json(args.epa)["vehicles"], load_json(args.safety),
                             load_json(args.mappings))
    write_json(args.report, report)
    if args.review_csv is not None:
        write_review_csv(args.review_csv, report)


if __name__ == "__main__":
    main()
