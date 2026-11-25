"""Build the equipment sidecar from reviewed, source-scoped trim matrices."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from validate_vehicle_equipment import validate, coverage


def build(evidence, catalog, digest):
    records = []
    for matrix in evidence["matrices"]:
        columns = matrix["columns"]
        if not columns or len(set(t["id"] for t in columns)) != len(columns):
            raise ValueError("Missing or duplicate matrix columns")
        for column in columns:
            records.append({**column, **matrix["scope"], "facts": {}})
        for row in matrix["rows"]:
            if len(row["cells"]) != len(columns):
                raise ValueError(f"Column count mismatch for {row['field']}")
            for record, cell in zip(records[-len(columns):], row["cells"]):
                if cell is None:
                    continue
                field = row["field"]
                if field in record["facts"]:
                    raise ValueError(f"Duplicate fact {record['id']}: {field}")
                record["facts"][field] = {
                    "value": cell,
                    "trimId": record["id"],
                    "source": row.get("source", matrix["source"]),
                    "locator": row["locator"],
                    "evidence": row["evidence"],
                }
    snapshot = {
        "schemaVersion": "vehicle-equipment/1.0",
        "market": "US",
        "catalogSha256": digest,
        "sources": evidence["sources"],
        "trims": sorted(records, key=lambda item: item["id"]),
        "relationships": sorted(evidence["relationships"], key=lambda item: (item["epaId"], item["trimId"])),
    }
    validate(snapshot, catalog)
    return snapshot


def read_catalog(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if raw.startswith(b"\x1f\x8b") else raw), hashlib.sha256(raw).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    catalog, digest = read_catalog(args.catalog)
    snapshot = build(json.loads(args.evidence.read_text(encoding="utf-8")), catalog, digest)
    write_json(args.snapshot, snapshot)
    write_json(args.report, coverage(snapshot, catalog))


if __name__ == "__main__":
    main()
