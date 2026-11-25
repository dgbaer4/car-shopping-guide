"""Produce the CSG-A02.2 coverage and unresolved queue from pinned inputs."""
import argparse
from collections import Counter, defaultdict
import csv
from hashlib import sha256
from math import ceil
from pathlib import Path

if __package__:
    from .reconcile_vehicles import (
        NO_RATING, VERIFIED, configuration_value, distinguish_configurations, load_json, normalized,
        reconcile, write_json,
    )
else:
    from reconcile_vehicles import (
        NO_RATING, VERIFIED, configuration_value, distinguish_configurations, load_json, normalized,
        reconcile, write_json,
    )

PRIORITIES = {
    "Toyota": ("Corolla Cross", "Corolla", "Camry", "Prius Prime", "Prius", "RAV4"),
    "Honda": ("Civic", "Accord", "CR-V", "HR-V", "Prologue"),
    "Nissan": ("Sentra", "Altima", "Rogue", "Kicks", "Leaf", "Ariya"),
    "Hyundai": ("Elantra", "Sonata", "Tucson", "Kona", "Ioniq 5", "Ioniq 6"),
    "Kia": ("Forte", "K4", "K5", "Sportage", "Niro", "EV6"),
}


def starts_with(model, family):
    return model == family or model.startswith(family + " ")


def priority_family(row):
    make = row["make"]
    model = normalized(row["epaConfiguration"]["model"])
    if make == "Toyota" and starts_with(model, "prius phev"):
        return "Prius Prime"
    return next((family for family in PRIORITIES.get(make, ())
                 if starts_with(model, normalized(family))), None)


def coverage(rows):
    rated = sum(row["classification"] in VERIFIED for row in rows)
    return {"total": len(rows), "rated": rated,
            "confirmedUnrated": sum(row["classification"] == NO_RATING for row in rows),
            "percentRated": round(100 * rated / len(rows), 2) if rows else 0}


def grouped_coverage(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return {name: coverage(group) for name, group in sorted(groups.items())}


def epa_scope(row):
    epa = row["epaConfiguration"]
    return (row["make"], row["year"], row["family"], epa["power"],
            configuration_value("drivetrain", epa["drivetrain"] or ""))


def triage(row, variants, native_models, failed_scopes, scope_counts):
    epa = row["epaConfiguration"]
    make_year = normalized(row["make"]), row["year"]
    model = normalized(epa["model"])
    candidates = [variants[candidate["vehicleId"]] for candidate in row["candidates"]]
    hints = []
    if not candidates:
        hints = sorted(name for name in native_models[make_year]
                       if starts_with(model, name) or starts_with(name, model))
        if any(model.startswith(name) for name in failed_scopes[make_year]):
            return "acquisition_error_overlap", hints
        if hints:
            return "possible_missing_model_alias", hints
        return "no_discovered_same_year_candidate", hints
    viable = [variant for variant in candidates if not distinguish_configurations(
        epa, variant.get("configuration"))]
    if not viable:
        return "known_configuration_conflict", hints
    if any(variant.get("status") == "detail_unavailable" for variant in viable):
        return "acquisition_error_overlap", hints
    if all(variant.get("publicationStatus") == "not_rated" for variant in viable):
        return "only_explicitly_unrated_candidates", hints
    if len(viable) > 1:
        return "multiple_potential_variants", hints
    if scope_counts[epa_scope(row)] > 1:
        return "missing_authoritative_applicability", hints
    if any(not epa.get(field) for field in ("body", "drivetrain", "power")) or any(
        not viable[0].get("configuration", {}).get(field) for field in ("body", "drivetrain", "power")
    ):
        return "missing_structured_attributes_and_scope", hints
    return "missing_authoritative_applicability", hints


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("epa", "safety", "baseline", "register", "catalog", "report", "queue"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    epa, safety, baseline, register = (load_json(path) for path in
                                       (args.epa, args.safety, args.baseline, args.register))
    _, legacy, before = reconcile(epa["vehicles"], safety, baseline)
    variants, associations, after = reconcile(epa["vehicles"], safety, register)
    rows = after["decisions"]
    current = coverage(rows)
    goals = {f"{percent}%": ceil(len(rows) * percent / 100) for percent in (15, 30, 50)}
    new = {key: value for key, value in associations.items() if key not in legacy}
    reviewed = Counter()
    old_rows = {row["epaId"]: row for row in before["decisions"]}
    new_rows = {row["epaId"]: row for row in rows}
    for epa_id, entry in new.items():
        outcome = "rated" if entry["classification"] in VERIFIED else "confirmed_unrated"
        old_candidates = {candidate["vehicleId"] for candidate in old_rows[epa_id]["candidates"]}
        new_candidates = {candidate["vehicleId"] for candidate in new_rows[epa_id]["candidates"]}
        method = ("alias_and_same_year_source_match" if old_candidates != new_candidates
                  else "same_year_source_match")
        reviewed[method, outcome] += 1

    native_models = defaultdict(set)
    for variant in variants.values():
        native = variant.get("nativeIdentity") or variant
        native_models[normalized(native["make"]), native["year"]].add(normalized(native["model"]))
    failed_scopes = defaultdict(set)
    for failure in safety.get("errors", []):
        if failure.get("model"):
            # A model-level failure is only a possible overlap for an EPA family.
            failed_scopes[normalized(failure["make"]), failure["year"]].add(
                normalized(failure["model"]).split(" hybrid ")[0])

    gaps = Counter()
    scope_counts = Counter(map(epa_scope, rows))
    with args.queue.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("epa_id", "make", "year", "epa_model", "powertrain", "drivetrain",
                         "priority_family", "classification", "first_review_blocker",
                         "candidate_vehicle_ids", "candidate_sources", "unverified_name_hints"))
        for row in rows:
            if row["classification"] in (*VERIFIED, NO_RATING):
                continue
            blocker, hints = triage(row, variants, native_models, failed_scopes, scope_counts)
            gaps[blocker] += 1
            epa = row["epaConfiguration"]
            writer.writerow((row["epaId"], row["make"], row["year"], epa["model"], epa["power"],
                             epa["drivetrain"], priority_family(row), row["classification"], blocker,
                             " ".join(c["vehicleId"] for c in row["candidates"]),
                             " ".join(c["source"] for c in row["candidates"]), " | ".join(hints)))

    priority_rows = [row for row in rows if priority_family(row)]
    write_json(args.report, {
        "overall": current,
        "baseline": coverage(before["decisions"]),
        "milestones": {name: {"target": target, "achieved": current["rated"] >= target,
                              "remaining": max(0, target - current["rated"])}
                       for name, target in goals.items()},
        "classifications": after["coverage"]["byClassification"],
        "priorityFamilies": {
            "baseline": coverage([row for row in before["decisions"] if priority_family(row)]),
            "overall": coverage(priority_rows),
            "byFamily": grouped_coverage(
                priority_rows, lambda row: f"{row['make']} {priority_family(row)}"),
        },
        "byMake": grouped_coverage(rows, lambda row: row["make"]),
        "byYear": grouped_coverage(rows, lambda row: str(row["year"])),
        "byPowertrain": grouped_coverage(rows, lambda row: row["epaConfiguration"]["power"]),
        "byMakeYearAndPowertrain": after["coverage"]["byMakeYearAndPowertrain"],
        "gainsByMethod": {method: {outcome: reviewed[method, outcome]
                                  for outcome in ("rated", "confirmed_unrated")}
                          for method in sorted({method for method, _ in reviewed})},
        "unresolvedFirstReviewBlocker": dict(gaps),
        "acquisition": {
            "variants": len(variants),
            "publicationStatus": dict(Counter(row.get("publicationStatus") for row in variants.values())),
            "errors": safety.get("errors", []),
        },
        "sha256": {name: sha256(getattr(args, name).read_bytes()).hexdigest()
                   for name in ("epa", "safety", "baseline", "register", "catalog")},
    })


if __name__ == "__main__":
    main()
