import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[1]


class ObservationSchemaTest(unittest.TestCase):
    def test_exchange_fixtures(self):
        schema = json.loads((ROOT / "data/observations.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for privacy in ("private", "shared"):
            with self.subTest(privacy=privacy):
                path = ROOT / "tests/fixtures" / f"observations-{privacy}.json"
                data = json.loads(path.read_text())
                validator.validate(data)
                data["observations"][0]["email"] = "unexpected@example.org"
                with self.assertRaises(ValidationError):
                    validator.validate(data)
