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


def native_text(value):
    return " ".join(value.casefold().split()) if isinstance(value, str) else None


def native_key(record):
    make, year, _ = identity(record)
    return native_text(make), year, native_text(record["model"])


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
    require(type(register.get("version")) is int and register["version"] in (1, 2),
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
        if register["version"] == 2:
            require(evidence.get("reviewMethod") in ("agent_reviewed", "independently_human_reviewed"),
                    f"{epa_id}: missing review method")
            require(valid_ratings(evidence.get("reviewedRatings")),
                    f"{epa_id}: invalid reviewed rating values")
            require(provenance(evidence.get("epaUrl"), evidence["accessed"], "fueleconomy.gov").path
                    == f"/ws/rest/vehicle/{epa_id[4:]}", f"{epa_id}: EPA evidence URL has a different ID")
            for side in ("epaAttributes", "nhtsaAttributes"):
                values = evidence.get(side)
                require(isinstance(values, dict) and values.keys() <= set(CONFIG_FIELDS[1:])
                        and all(nonempty(value) for value in values.values()),
                        f"{epa_id}: invalid {side} evidence")
            if entry["classification"] == APPLICABLE:
                scope = provenance(evidence.get("scopeUrl"), evidence["accessed"], "nhtsa.gov")
                require(bool(scope.path.strip("/")), f"{epa_id}: missing NHTSA applicability scope")
        associations[epa_id] = entry
    return aliases, associations


def valid_ratings(ratings):
    return (isinstance(ratings, dict) and ratings.keys() == RATING_FIELDS
            and all(v is None or type(v) is int and 1 <= v <= 5 for v in ratings.values()))


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
        require(valid_ratings(ratings),
                f"{vid}: invalid rating values or fields")
        native = row.get("nativeIdentity")
        if native is not None:
            require(identity(native)[:2] == query_identity[:2],
                    f"{vid}: native make or model year conflicts with the record")
            identity_source = provenance(native.get("source"), native.get("accessed", row["accessed"]), "nhtsa.gov")
            if identity_source.hostname == "api.nhtsa.gov":
                path = unquote(identity_source.path.rstrip("/")).casefold()
                expected = f"/safetyratings/modelyear/{native['year']}/make/{native['make']}/model/{native['model']}"
                require(path == expected.casefold(),
                        f"{vid}: native identity URL does not identify the listed variant group")
            require(nonempty(row.get("description")), f"{vid}: missing native description")
            detail = row.get("nativeDetailIdentity")
            if detail is not None:
                detail_identity = {"make": detail.get("Make"), "year": detail.get("ModelYear"),
                                   "model": detail.get("Model")}
                require(native_key(detail_identity) == native_key(native)
                        and native_text(detail.get("VehicleDescription")) == native_text(row["description"]),
                        f"{vid}: conflicting native detail and discovery identities")
            for item in row.get("discovery", []):
                require(native_key(item) == native_key(native)
                        and native_text(item.get("description")) == native_text(row["description"]),
                        f"{vid}: competing native discovery identity")
                provenance(item.get("source"), item.get("accessed"), "nhtsa.gov")
        if "rawRatings" in row:
            raw = row["rawRatings"]
            require(isinstance(raw, dict) and raw.keys() == RATING_FIELDS
                    and all(ratings[key] == (int(value) if str(value) in ("1", "2", "3", "4", "5") else None)
                            for key, value in raw.items()), f"{vid}: raw and normalized ratings disagree")
            if row.get("publicationStatus") == "not_rated":
                require(all(isinstance(value, str) and value.strip().casefold() == "not rated"
                            for value in raw.values()), f"{vid}: unrated status lacks explicit raw evidence")
            if row.get("publicationStatus") == "published":
                require(any(value is not None for value in ratings.values()),
                        f"{vid}: published status has no stars")
        variants[vid] = row
    return variants


BULK_RATING_FIELDS = {
    "overall": "OVERALL_STARS", "frontal": "OVERALL_FRNT_STARS",
    "side": "OVERALL_SIDE_STARS", "rollover": "ROLLOVER_STARS",
}
BULK_BODY_TYPES = {"4 dr": "Sedan", "4dr": "Sedan", "5 hb": "Hatchback", "suv": "SUV"}


def validate_bulk_evidence(evidence, native, attributes, ratings, label):
    bulk = evidence["bulkEvidence"]
    url = provenance(bulk.get("url"), evidence["accessed"], "nhtsa.gov")
    require(url.path == "/nhtsa/downloads/Safercar/Safercar_data.csv",
            f"{label}: invalid Safercar source")
    record = bulk.get("record", {})
    require(record.get("MAKE", "").casefold() == native["make"].casefold()
            and record.get("MODEL_YR") == str(native["year"])
            and normalized(record.get("MODEL", "")) == normalized(native["model"]),
            f"{label}: Safercar identity differs from the native variant")
    require(record.get("PRODUCTION_RELEASE") == "1"
            and configuration_value("drivetrain", record.get("DRIVE_TRAIN", ""))
            == configuration_value("drivetrain", attributes["drivetrain"])
            and BULK_BODY_TYPES.get(normalized(record.get("BODY_STYLE", ""))) == attributes["body"],
            f"{label}: Safercar release, drivetrain or body differs")
    expected = {field: "" if rating is None else str(rating) for field, rating in ratings.items()}
    require({field: record.get(key) for field, key in BULK_RATING_FIELDS.items()} == expected,
            f"{label}: Safercar rating values differ")
    notes = bulk.get("notes")
    require(isinstance(notes, dict) and all(
        not re.search(r"ratings? appl|manufactur|produced|equipped with|\bVIN\b", value, re.I)
        for value in notes.values()), f"{label}: Safercar notes require scope review")


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
    evidence = entry["evidence"]
    effective = [configuration(epa), target.copy()]
    for original, key in zip(effective, ("epaAttributes", "nhtsaAttributes")):
        for field, value in evidence.get(key, {}).items():
            previous = original.get(field)
            require(previous is None or configuration_value(field, previous) == configuration_value(field, value),
                    f"{label}: {key} conflicts with source {field}")
            original[field] = value
    epa_attributes, target = effective
    require(epa_attributes.get("power") in POWERTRAINS and target.get("power") in POWERTRAINS,
            f"{label}: missing or invalid powertrain")
    for field in CONFIG_FIELDS[1:]:
        left, right = epa_attributes.get(field), target.get(field)
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
    if "reviewedRatings" in evidence:
        require(evidence["reviewedRatings"] == variant["ratings"],
                f"{label}: published rating values changed since review")
        require(evidence["url"] == variant["source"] and evidence.get("listingUrl") == native["source"],
                f"{label}: source provenance changed since review")
        require(variant.get("status") != "detail_unavailable",
                f"{label}: NHTSA rating detail unavailable")
    if "bulkEvidence" in evidence:
        validate_bulk_evidence(evidence, native, target, variant["ratings"], label)
    if entry["classification"] == NO_RATING:
        if "reviewedRatings" in evidence:
            require("rawRatings" in variant, f"{label}: missing raw evidence for unrated status")
        require(not published and variant.get("publicationStatus") == "not_rated",
                f"{label}: no published ratings must be explicitly confirmed by NHTSA")
    else:
        require(published and variant.get("publicationStatus") != "not_rated",
                f"{label}: verified mapping lacks a published rating")
    return target


def distinguish_configurations(left, right):
    if not isinstance(right, dict):
        return False
    return any(
        nonempty(left.get(field)) and nonempty(right.get(field))
        and configuration_value(field, left[field]) != configuration_value(field, right[field])
        for field in (*REQUIRED_CONFIGURATION, "battery", "generation")
    )


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
    power_coverage = {}
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
                verified_attributes = validate_association(epa, variants[vid], entry, family_key, nhtsa_keys[vid])
                if register.get("version") == 2 and entry["classification"] != APPLICABLE:
                    require(all(other == vid or distinguish_configurations(
                        verified_attributes, variants[other].get("configuration")) for other in matches),
                        f"{epa_id}: competing NHTSA variant lacks a material distinction")
                status, reason = entry["classification"], entry["evidence"]["statement"]
            else:
                status = REVIEW if len(matches) <= 1 else AMBIGUOUS
                reason = f"Reviewed VehicleId {vid} is absent from this NHTSA input"
        decisions.append({
            "epaId": epa_id, "make": epa["make"], "year": epa["year"],
            "epaConfiguration": configuration(epa), "epaSources": epa["sources"], "family": family,
            "reviewMethod": entry["evidence"].get("reviewMethod") if entry and vid in variants else None,
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
        power_counts = power_coverage.setdefault(epa["make"], {}).setdefault(str(epa["year"]), {}).setdefault(
            epa["power"], dict.fromkeys(CLASSIFICATIONS, 0))
        power_counts[status] += 1
    require(not associations.keys() - ids, "Unknown EPA ID in association register")
    report = {
        "coverage": {"total": len(records), "byClassification": dict(totals),
                     "byMakeAndYear": coverage, "byMakeYearAndPowertrain": power_coverage,
                     "publishedConfigurations": sum(totals[status] for status in VERIFIED)},
        "acquisition": {"nhtsaVariants": len(variants),
                        "schemaVersion": safety.get("schemaVersion"),
                        "sourceCoverage": safety.get("coverage"),
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
