import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.build_catalog import build
from tools.reconcile_vehicles import (
    AMBIGUOUS, APPLICABLE, EXACT, NO_RATING, REVIEW, UNMATCHED,
    configuration, load_json, reconcile,
)

EPA_URL = "https://www.fueleconomy.gov/feg/download.shtml"
NHTSA_URL = "https://api.nhtsa.gov/SafetyRatings"
TODAY = "2026-11-24"


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.epa = {
            "id": "epa-101", "make": "Toyota", "year": 2023, "model": "Prius AWD",
            "power": "Traditional hybrid", "drivetrain": "All-Wheel Drive", "body": "Hatchback",
            "sources": [{"url": EPA_URL, "accessed": TODAY, "fields": ["model"]}],
        }
        self.variant = {
            "vehicleId": 202, "make": "TOYOTA", "year": 2023, "model": "PRIUS",
            "nativeIdentity": {"make": "TOYOTA", "year": 2023, "model": "PRIUS",
                               "source": NHTSA_URL + "/modelyear/2023/make/TOYOTA/model/PRIUS"},
            "description": "2023 Toyota PRIUS 5 HB AWD", "source": NHTSA_URL + "/VehicleId/202",
            "accessed": TODAY, "ratings": dict(overall=5, frontal=5, side=5, rollover=None),
            "configuration": dict(power="Traditional hybrid", drivetrain="AWD", body="Hatchback"),
        }
        self.mapping = {
            "version": 1, "familyAliases": [
                {"source": "epa", "make": "Toyota", "year": 2023, "model": "Prius AWD",
                 "family": "Prius", "evidenceUrl": EPA_URL, "accessed": TODAY,
                 "reason": "Candidate from original label"},
            ], "associations": [],
        }
        self.safety = {"records": [self.variant], "errors": [], "unmatched": []}

    def approve(self, classification=EXACT):
        self.mapping["associations"].append({
            "epaId": self.epa["id"], "vehicleId": self.variant["vehicleId"],
            "classification": classification,
            "configuration": {
                "epa": configuration(self.epa), "nhtsa": self.variant["configuration"].copy(),
                "nhtsaModel": self.variant["nativeIdentity"]["model"],
                "description": self.variant["description"],
            },
            "evidence": {"url": self.variant["source"], "accessed": TODAY,
                         "reviewer": "Fixture reviewer", "statement": "Fixture applicability evidence",
                         "ratingFields": [k for k, value in self.variant["ratings"].items()
                                          if value is not None]},
        })

    def decision(self):
        return reconcile([self.epa], self.safety, self.mapping)[2]["decisions"][0]

    def catalog(self):
        return build({"vehicles": [self.epa]}, self.safety, self.mapping)[0]["vehicles"][0]

    def test_alias_candidate_is_not_a_verified_match(self):
        row = self.decision()
        self.assertEqual(row["classification"], REVIEW)
        self.assertEqual(row["epaConfiguration"]["model"], "Prius AWD")
        self.assertEqual(row["candidates"][0]["description"], self.variant["description"])
        self.assertIsNone(self.catalog()["safetyRatings"])

    def test_verified_configuration_and_provenance(self):
        self.approve()
        result = self.catalog()
        self.assertEqual(self.decision()["classification"], EXACT)
        self.assertEqual(result["safetyRatings"], self.variant["ratings"])
        self.assertEqual(result["sources"][-1]["url"], self.variant["source"])
        self.assertNotIn("safetyRatings", self.epa)

    def test_partial_acquisition_preserves_independently_verified_rating(self):
        self.approve()
        self.safety["errors"] = [{"group": [2024, "Toyota", "Prius"], "reason": "HTTP 400"}]
        self.assertEqual(self.catalog()["safetyRatings"], self.variant["ratings"])
        self.safety["records"] = []
        self.assertIn("absent", self.decision()["reason"])
        self.assertIsNone(self.catalog()["safetyRatings"])

    def test_applicability_covers_source_attribute_missing_from_epa(self):
        self.epa.pop("body")
        self.approve(APPLICABLE)
        self.assertEqual(self.decision()["classification"], APPLICABLE)
        self.assertEqual(self.catalog()["safetyRatings"]["overall"], 5)

    def test_exact_requires_body_evidence(self):
        self.epa.pop("body")
        self.approve()
        with self.assertRaisesRegex(ValueError, "missing EPA body"):
            self.decision()

    def test_similar_names_and_years_are_independent(self):
        for model, year, make in [
            ("Prius Prime", 2023, "Toyota"), ("Prius AWD", 2024, "Toyota"),
            ("Prius AWD", 2023, "Honda"),
        ]:
            with self.subTest(model=model, year=year, make=make):
                self.epa.update(model=model, year=year, make=make)
                self.assertEqual(self.decision()["classification"], UNMATCHED)
        self.approve()
        with self.assertRaisesRegex(ValueError, "manufacturer or model year"):
            self.decision()
        self.epa["make"] = "Toyota"
        self.epa["year"] = 2024
        self.mapping["associations"] = []
        self.approve()
        with self.assertRaisesRegex(ValueError, "manufacturer or model year"):
            self.decision()

    def test_conflicting_configurations_even_with_evidence(self):
        for field, left, right in (
            ("power", "Gasoline", "Traditional hybrid"),
            ("drivetrain", "4WD", "AWD"),
            ("body", "Sedan", "Hatchback"),
            ("trim", "LE", "XLE"),
            ("generation", "4", "5"),
            ("battery", "40 kWh", "60 kWh"),
        ):
            with self.subTest(field=field):
                epa, variant = copy.deepcopy(self.epa), copy.deepcopy(self.variant)
                self.epa[field] = left
                self.variant["configuration"][field] = right
                self.approve(APPLICABLE)
                with self.assertRaisesRegex(ValueError, f"conflicting {field}"):
                    self.decision()
                self.epa.clear()
                self.epa.update(epa)
                self.variant.clear()
                self.variant.update(variant)
                self.mapping["associations"].clear()

    def test_ambiguous_family_needs_review(self):
        second = copy.deepcopy(self.variant)
        second.update(vehicleId=203, source=NHTSA_URL + "/VehicleId/203",
                      description="2023 Toyota PRIUS 5 HB FWD")
        self.safety["records"].insert(0, second)
        row = self.decision()
        self.assertEqual(row["classification"], AMBIGUOUS)
        self.assertEqual([item["vehicleId"] for item in row["candidates"]], ["202", "203"])
        self.assertIsNone(self.catalog()["safetyRatings"])

    def test_no_ratings_requires_explicit_publication_status(self):
        self.variant["ratings"] = dict.fromkeys(self.variant["ratings"])
        self.assertEqual(self.decision()["classification"], REVIEW)
        self.approve(NO_RATING)
        with self.assertRaisesRegex(ValueError, "explicitly confirmed"):
            self.decision()
        self.variant["publicationStatus"] = "not_rated"
        self.assertEqual(self.decision()["classification"], NO_RATING)
        self.assertIsNone(self.catalog()["safetyRatings"])

    def test_legacy_query_and_existing_ratings_cannot_publish(self):
        self.approve()
        self.variant.pop("nativeIdentity")
        self.epa["safetyRatings"] = {"overall": 5}
        self.epa["sources"].append({"url": self.variant["source"], "accessed": TODAY,
                                    "fields": ["safetyRatings"]})
        with self.assertRaisesRegex(ValueError, "query-only"):
            self.decision()
        self.mapping["associations"] = []
        result = self.catalog()
        self.assertIsNone(result["safetyRatings"])
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(self.epa["safetyRatings"], {"overall": 5})

    def test_source_changes_require_new_review(self):
        self.approve()
        self.variant["description"] += " (revised)"
        with self.assertRaisesRegex(ValueError, "source configuration changed"):
            self.decision()

    def test_new_rating_category_requires_scope_review(self):
        self.approve()
        self.variant["ratings"]["rollover"] = 4
        with self.assertRaisesRegex(ValueError, "rating fields changed"):
            self.decision()

    def test_identity_url_must_reference_native_model(self):
        self.variant["nativeIdentity"]["source"] += "%20PRIME"
        with self.assertRaisesRegex(ValueError, "native identity URL"):
            self.decision()

    def test_conflicting_mapping_and_duplicate_ids_rejected(self):
        self.approve()
        self.approve(APPLICABLE)
        with self.assertRaisesRegex(ValueError, "competing association"):
            self.decision()
        self.mapping["associations"].clear()
        self.mapping["familyAliases"] *= 2
        with self.assertRaisesRegex(ValueError, "competing family mapping"):
            self.decision()
        self.mapping["familyAliases"].pop()
        self.safety["records"].append(dict(self.variant, vehicleId="202"))
        with self.assertRaisesRegex(ValueError, "Duplicate NHTSA VehicleId"):
            self.decision()
        self.safety["records"].pop()
        with self.assertRaisesRegex(ValueError, "duplicate EPA ID"):
            reconcile([self.epa, self.epa], self.safety, self.mapping)

    def test_bad_identifiers_rejected(self):
        self.epa["id"] = "epa-001"
        with self.assertRaisesRegex(ValueError, "Invalid or duplicate EPA ID"):
            self.decision()
        self.variant["vehicleId"] = True
        with self.assertRaisesRegex(ValueError, "Invalid NHTSA VehicleId"):
            self.decision()

    def test_untrustworthy_provenance_and_invalid_ratings_rejected(self):
        original = self.variant["source"]
        for url in ("", "https://nhtsa.gov.example.com/SafetyRatings/VehicleId/202",
                    NHTSA_URL + "/VehicleId/999"):
            with self.subTest(url=url):
                self.variant["source"] = url
                with self.assertRaises(ValueError):
                    self.decision()
        self.variant["source"] = original
        for invalid in (True, 0, 6, "5", 5.0):
            with self.subTest(rating=invalid):
                self.variant["ratings"]["overall"] = invalid
                with self.assertRaisesRegex(ValueError, "invalid rating"):
                    self.decision()

    def test_mapping_cannot_reuse_exact_rating_without_applicability(self):
        self.approve()
        self.epa["id"] = "epa-102"
        self.approve()
        with self.assertRaisesRegex(ValueError, "multiple exact associations"):
            self.decision()

    def test_old_nonempty_mapping_and_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported mapping version"):
            reconcile([self.epa], self.safety, {"epa-101": {"reviewed": True}})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mapping.json"
            path.write_text('{"version": 1, "version": 2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate JSON object key"):
                load_json(path)

    def approve_v2(self, classification=EXACT):
        self.approve(classification)
        self.mapping["version"] = 2
        self.mapping["associations"][0]["evidence"].update(
            reviewMethod="agent_reviewed", reviewedRatings=self.variant["ratings"].copy(),
            epaUrl="https://www.fueleconomy.gov/ws/rest/vehicle/101",
            listingUrl=self.variant["nativeIdentity"]["source"],
            epaAttributes={}, nhtsaAttributes={},
        )

    def test_v2_pins_values_even_when_categories_match(self):
        self.approve_v2()
        self.assertEqual(self.catalog()["safetyRatings"]["overall"], 5)
        self.variant["ratings"]["overall"] = 4
        with self.assertRaisesRegex(ValueError, "rating values changed"):
            self.catalog()

    def test_v2_checks_expanded_native_identity(self):
        self.approve_v2()
        self.variant["nativeDetailIdentity"] = {
            "ModelYear": 2023, "Make": "Toyota", "Model": "PRIUS PRIME",
            "VehicleDescription": self.variant["description"],
        }
        with self.assertRaisesRegex(ValueError, "conflicting native detail"):
            self.catalog()

    def test_v2_rejects_competing_variant_without_material_difference(self):
        self.approve_v2()
        second = copy.deepcopy(self.variant)
        second.update(vehicleId=203, source=NHTSA_URL + "/VehicleId/203")
        self.safety["records"].append(second)
        with self.assertRaisesRegex(ValueError, "competing NHTSA variant"):
            self.catalog()
        second["configuration"]["drivetrain"] = "FWD"
        self.assertEqual(self.catalog()["safetyRatings"]["overall"], 5)

    def test_v2_rejects_changed_evidence_url_and_contradictory_attributes(self):
        self.approve_v2()
        evidence = self.mapping["associations"][0]["evidence"]
        evidence["listingUrl"] += "?different-source=true"
        with self.assertRaisesRegex(ValueError, "source provenance changed"):
            self.catalog()
        evidence["listingUrl"] = self.variant["nativeIdentity"]["source"]
        evidence["nhtsaAttributes"]["body"] = "SUV"
        with self.assertRaisesRegex(ValueError, "conflicts with source body"):
            self.catalog()

    def test_v2_null_status_requires_positive_evidence(self):
        self.variant["ratings"] = dict.fromkeys(self.variant["ratings"])
        self.variant["rawRatings"] = dict.fromkeys(self.variant["ratings"], "Not Rated")
        self.variant["publicationStatus"] = "not_rated"
        self.approve_v2(NO_RATING)
        self.assertEqual(self.decision()["classification"], NO_RATING)
        self.variant["rawRatings"]["frontal"] = None
        with self.assertRaisesRegex(ValueError, "unrated status lacks explicit"):
            self.decision()

    def test_v2_requires_authoritative_scope_for_cross_configuration(self):
        self.approve_v2(APPLICABLE)
        with self.assertRaisesRegex(ValueError, "Invalid source URL"):
            self.decision()
        evidence = self.mapping["associations"][0]["evidence"]
        evidence["scopeUrl"] = "https://www.nhtsa.gov/example-scope"
        self.assertEqual(self.decision()["classification"], APPLICABLE)

    def test_v2_machine_only_review_cannot_publish(self):
        self.approve_v2()
        self.mapping["associations"][0]["evidence"]["reviewMethod"] = "machine_validated"
        with self.assertRaisesRegex(ValueError, "missing review method"):
            self.catalog()

    def test_repository_register_uses_supported_version(self):
        root = Path(__file__).resolve().parents[1]
        register = json.loads((root / "data/vehicle-reconciliation-mappings.v1.json").read_text())
        self.assertEqual(reconcile([], {"records": []}, register)[2]["coverage"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
