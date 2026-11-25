import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from extract_honda_equipment import extract
from import_vehicle_equipment import build
from validate_vehicle_equipment import FIELDS, SCHEMA, coverage, validate

DATA = ROOT / "data/development/equipment"


class EquipmentTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads((DATA / "vehicle-equipment.v1.json").read_text())
        self.evidence = json.loads((DATA / "vehicle-equipment-evidence.v1.json").read_text())
        # This slice uses exact catalog identities from the pinned development build.
        self.catalog = {"vehicles": [
            {"id": "epa-48500", "make": "Nissan", "model": "Sentra", "year": 2025,
             "power": "Gasoline", "drivetrain": "Front-Wheel Drive", "features": {}},
            {"id": "epa-48501", "make": "Nissan", "model": "Sentra SR", "year": 2025,
             "power": "Gasoline", "drivetrain": "Front-Wheel Drive", "features": {}},
        ]}
        self.snapshot["relationships"] = [
            x for x in self.snapshot["relationships"] if x["epaId"] in {"epa-48500", "epa-48501"}
        ]
        self.evidence["relationships"] = self.snapshot["relationships"]

    def sentra(self, trim):
        return next(r for r in self.snapshot["trims"] if r["model"] == "Sentra" and r["trim"] == trim)

    def test_schema_and_repeatable_import(self):
        Draft202012Validator.check_schema(SCHEMA)
        digest = self.snapshot["catalogSha256"]
        validate(self.snapshot, self.catalog, digest)
        self.assertEqual(build(self.evidence, self.catalog, digest), self.snapshot)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            validate(self.snapshot, self.catalog, "0" * 64)

    def test_separate_trim_statuses_and_shared_epa_id(self):
        for trim, status in [("S", "unavailable"), ("SV", "package-dependent"), ("SR", "standard")]:
            self.assertEqual(self.sentra(trim)["facts"]["Heated front seats"]["value"], status)
            self.assertNotIn("Lane-keeping assistance", self.sentra(trim)["facts"])
        self.assertEqual(sum(x["epaId"] == "epa-48500" for x in self.snapshot["relationships"]), 2)
        report = coverage(self.snapshot, self.catalog)
        self.assertEqual(report["linkedEpaConfigurations"], 2)
        self.assertEqual(report["epaConfigurationsWithAppliedEquipment"], 0)
        rows = next(x for x in report["trimCoverage"] if x["scope"] == ["Nissan"])
        self.assertEqual(rows["fields"]["Lane-keeping assistance"], {"unknown": 3})

    def test_reject_copied_cross_trim_fact(self):
        self.sentra("S")["facts"]["Heated front seats"] = copy.deepcopy(
            self.sentra("SR")["facts"]["Heated front seats"]
        )
        with self.assertRaisesRegex(ValueError, "Fact trim scope mismatch"):
            validate(self.snapshot, self.catalog)

    def test_reject_cross_year_source_and_epa_link(self):
        source = self.snapshot["sources"]["nissan-sentra"]
        source["year"] = 2024
        with self.assertRaisesRegex(ValueError, "Fact source scope mismatch"):
            validate(self.snapshot, self.catalog)
        source["year"] = 2025
        self.catalog["vehicles"][0]["year"] = 2026
        with self.assertRaisesRegex(ValueError, "Cross-year"):
            validate(self.snapshot, self.catalog)

    def test_reject_wrong_epa_identity(self):
        self.catalog["vehicles"][0]["model"] = "Altima"
        with self.assertRaisesRegex(ValueError, "EPA identity mismatch"):
            validate(self.snapshot, self.catalog)

    def test_reject_malformed_matrices_and_boolean_facts(self):
        matrix = self.evidence["matrices"][0]
        matrix["rows"][0]["cells"].pop()
        with self.assertRaisesRegex(ValueError, "Column count mismatch"):
            build(self.evidence, self.catalog, self.snapshot["catalogSha256"])
        self.sentra("SV")["facts"]["Heated front seats"]["value"] = True
        with self.assertRaises(ValidationError):
            validate(self.snapshot, self.catalog)

    def test_questionnaire_features_have_contract_fields(self):
        source = (ROOT / "index.html").read_text()
        import re
        groups = source.split("const groups=", 1)[1].split(";", 1)[0]
        options = [name for group in re.findall(r"\[([^\]]+)\]", groups)
                   for name in re.findall(r"'([^']+)'", group)]
        self.assertEqual(set(FIELDS) - {"body", "seats", "power", "drivetrain"}, set(options))


class HondaExtractionTests(unittest.TestCase):
    def test_year_and_ordered_trim_columns_are_required(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "matrix.html"
            path.write_text("""<title>2025 Honda Civic Sedan Specifications &amp; Features</title>
                <table><tr><th>2025 HONDA CIVIC SEDAN SPECIFICATIONS &amp; FEATURES</th>
                <th>LX</th><th>Sport</th></tr>
                <tr><td>Remote Engine Start</td><td>-</td><td>•</td></tr></table>""",
                encoding="utf-8")
            rows = extract(path, 2025, "Civic Sedan", ["LX", "Sport"])
            self.assertEqual(rows[0]["cells"], ["unavailable", "standard"])
            with self.assertRaisesRegex(ValueError, "title"):
                extract(path, 2026, "Civic Sedan", ["LX", "Sport"])
            with self.assertRaisesRegex(ValueError, "trim columns"):
                extract(path, 2025, "Civic Sedan", ["Sport", "LX"])
