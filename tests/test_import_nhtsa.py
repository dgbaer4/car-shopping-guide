import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import unquote, urlparse

from tools.import_nhtsa import AcquisitionError, Client, acquire, retry_after


def vehicle(vid, description):
    return {"VehicleId": vid, "VehicleDescription": description}


def detail(vid, model, stars, description=None):
    descriptions = {5: "Camry AWD", 6: "Camry FWD", 7: "Camry Hybrid"}
    return {**vehicle(vid, description or descriptions[vid]), "ModelYear": 2024, "Make": "TOYOTA",
            "Model": model, "OverallRating": stars, "OverallSideCrashRating": "Not Rated"}


class ImportTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.cache = Path(temp.name)
        self.calls = []
        self.make_path = "/SafetyRatings/modelyear/2024/make/TOYOTA"
        self.responses = {
            "/SafetyRatings/modelyear/2024": [{"Make": "TOYOTA", "ModelYear": 2024}],
            self.make_path: [{"Make": "TOYOTA", "ModelYear": 2024, "Model": m}
                             for m in ("CAMRY", "CAMRY HYBRID", "EMPTY")],
            self.make_path + "/model/CAMRY": [vehicle(5, "Camry AWD"), vehicle(6, "Camry FWD"),
                                                     vehicle(5, " CAMRY  AWD ")],
            self.make_path + "/model/CAMRY%20HYBRID": [vehicle(7, "Camry Hybrid")],
            self.make_path + "/model/EMPTY": [],
            "/SafetyRatings/VehicleId/5": [detail(5, "CAMRY", "5")],
            "/SafetyRatings/VehicleId/6": [detail(6, "CAMRY", "Not Rated")],
            "/SafetyRatings/VehicleId/7": [],
        }

    def open(self, request, timeout):
        path = urlparse(request.full_url).path
        self.calls.append(path)
        value = self.responses[path]
        if isinstance(value, Exception):
            raise value
        payload = value if isinstance(value, dict) else {"Count": len(value), "Results": value}
        return io.BytesIO(json.dumps(payload).encode())

    def run_import(self, opener=None, **options):
        snapshots = []
        complete = acquire(Client(self.cache, interval=0, opener=opener or self.open, **options),
                           [2024], ["TOYOTA"], snapshots.append)
        return complete, snapshots[-1]

    def test_native_results_and_resume(self):
        complete, result = self.run_import()
        self.assertTrue(complete)
        first, second, third = result["records"]
        self.assertEqual(first["ratings"], {"overall": 5, "frontal": None,
                                           "side": None, "rollover": None})
        self.assertEqual(len(first["discovery"]), 2)
        self.assertEqual(second["status"], "unrated")
        self.assertEqual(third["status"], "detail_unavailable")
        self.assertEqual(len(result["unsupported"]), 2)
        self.assertEqual(self.calls.count("/SafetyRatings/VehicleId/5"), 1)
        self.calls.clear()
        self.assertEqual(self.run_import()[1]["records"], result["records"])
        self.assertEqual(self.calls, [])

    def test_permanent_failure_does_not_skip_siblings_and_can_resume(self):
        path = "/SafetyRatings/VehicleId/5"
        self.responses[path] = HTTPError(path, 400, "Bad request", {}, None)
        complete, result = self.run_import()
        self.assertFalse(complete)
        self.assertEqual(self.calls.count(path), 1)
        self.assertEqual(result["errors"][0]["status"], "permanent_failure")
        self.assertEqual([r["vehicleId"] for r in result["records"]], ["6", "7"])
        self.assertEqual(result["pendingVariants"][0]["vehicleId"], "5")
        self.assertEqual(len(result["pendingVariants"][0]["discovery"]), 2)
        self.responses[path] = [detail(5, "CAMRY", 4)]
        self.calls.clear()
        self.assertTrue(self.run_import()[0])
        self.assertEqual(self.calls, [path])

    def test_rate_limit_and_budget(self):
        def limited(request, timeout):
            raise HTTPError(request.full_url, 429, "Retry later", {"Retry-After": "60"}, None)

        client = Client(self.cache, seconds=5, opener=limited)
        with self.assertRaises(AcquisitionError) as raised:
            client.get("VehicleId/5", lambda r: r)
        self.assertEqual(raised.exception.http_status, 429)
        with self.assertRaises(AcquisitionError) as deferred:
            client.get("VehicleId/6", lambda r: r)
        self.assertEqual(deferred.exception.status, "deferred")
        self.assertEqual(client.counts["httpAttempts"], 1)
        self.assertEqual(retry_after("broken"), 0)

    def test_transient_retry_and_validation_failure(self):
        path = "/SafetyRatings/VehicleId/6"
        attempts = 0

        def flaky(request, timeout):
            nonlocal attempts
            if urlparse(request.full_url).path == path:
                attempts += 1
                if attempts < 3:
                    raise TimeoutError("timeout")
            return self.open(request, timeout)

        with patch("tools.import_nhtsa.time.sleep"):
            self.assertTrue(self.run_import(flaky)[0])
        self.assertEqual(attempts, 3)
        self.responses[path] = {"Count": 2, "Results": []}
        for entry in self.cache.rglob("*.json"):
            if "/VehicleId/6?" in json.loads(entry.read_text())["source"]:
                entry.unlink()
        complete, result = self.run_import()
        self.assertFalse(complete)
        self.assertEqual(result["errors"][0]["status"], "invalid_response")
        self.assertEqual(result["errors"][0]["attempts"], 1)

    def test_interrupt_keeps_checkpoint_and_cache(self):
        def interrupt(request, timeout):
            if request.full_url.endswith("/VehicleId/6?format=json"):
                raise KeyboardInterrupt
            return self.open(request, timeout)

        complete, result = self.run_import(interrupt)
        self.assertFalse(complete)
        self.assertFalse(result["coverage"]["discoveryFinished"])
        self.assertEqual([r["vehicleId"] for r in result["records"]], ["5"])
        self.calls.clear()
        self.assertTrue(self.run_import()[0])
        self.assertNotIn("/SafetyRatings/VehicleId/5", self.calls)


    def test_conflicting_native_labels_quarantine_the_id(self):
        self.responses[self.make_path + "/model/CAMRY%20HYBRID"].append(vehicle(5, "Camry AWD"))
        complete, result = self.run_import()
        self.assertFalse(complete)
        self.assertEqual({r["vehicleId"] for r in result["records"]}, {"6", "7"})
        error = result["errors"][0]
        self.assertEqual(error["status"], "identity_conflict")
        self.assertEqual(error["record"]["ratings"]["overall"], 5)
        self.assertEqual({d["model"] for d in error["discovery"]}, {"CAMRY", "CAMRY HYBRID"})
        self.assertEqual(result["coverage"]["byYearMake"][0]["records"], 2)
        self.assertEqual(result["coverage"]["byYearMake"][0]["status"], "partial")

    def test_detail_conflict_and_pending_listing_conflict_are_reported(self):
        wrong_year = detail(5, "CAMRY", "5")
        wrong_year["ModelYear"] = 2025
        self.responses["/SafetyRatings/VehicleId/5"] = [wrong_year]
        self.responses[self.make_path + "/model/CAMRY%20HYBRID"].append(vehicle(6, "Camry FWD"))
        self.responses["/SafetyRatings/VehicleId/6"] = {"Count": 0, "Results": [None]}
        complete, result = self.run_import()
        self.assertFalse(complete)
        self.assertEqual([r["vehicleId"] for r in result["records"]], ["7"])
        self.assertEqual([e["status"] for e in result["errors"]],
                         ["invalid_response", "identity_conflict", "identity_conflict"])
        self.assertEqual(result["errors"][1]["record"]["nativeDetailIdentity"]["ModelYear"], 2025)
        self.assertEqual(result["pendingVariants"][0]["vehicleId"], "6")

    def test_cache_expiration_and_forced_refresh(self):
        self.assertTrue(self.run_import()[0])
        self.calls.clear()
        detail_path = "/SafetyRatings/VehicleId/5"
        for entry in self.cache.rglob("*.json"):
            data = json.loads(entry.read_text())
            if urlparse(data["source"]).path == detail_path:
                data["accessed"] = "2000-01-01"
                data["fetchedAt"] = "2000-01-01T00:00:00+00:00"
                entry.write_text(json.dumps(data))
        self.responses[detail_path] = [detail(5, "CAMRY", "4")]
        complete, result = self.run_import()
        self.assertTrue(complete)
        self.assertEqual(self.calls, [detail_path])
        self.assertEqual(result["records"][0]["ratings"]["overall"], 4)
        self.assertEqual(result["coverage"]["requests"]["staleCacheEntries"], 1)
        self.assertEqual(result["coverage"]["requests"]["refreshedRecords"], 1)
        self.calls.clear()
        complete, result = self.run_import(force_refresh=True)
        self.assertTrue(complete)
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(result["coverage"]["requests"]["forcedRefreshes"], 8)
        self.assertEqual(result["coverage"]["requests"]["refreshedRecords"], 2)

    def test_reconciliation_contract_and_raw_publication(self):
        unknown = detail(5, "CAMRY", "Temporarily unavailable")
        no_rating = {**detail(6, "CAMRY", "Not Rated"),
                     "OverallFrontCrashRating": "Not Rated", "RolloverRating": "Not Rated"}
        self.responses["/SafetyRatings/VehicleId/5"] = [unknown]
        self.responses["/SafetyRatings/VehicleId/6"] = [no_rating]
        self.responses[self.make_path + "/model/CAMRY%20HYBRID"] = [
            vehicle(7, "Camry Hybrid PHEV SUV 40 kWh Battery FWD")]
        self.responses["/SafetyRatings/VehicleId/7"] = [
            detail(7, "CAMRY HYBRID", "5", "Camry Hybrid PHEV SUV 40 kWh Battery FWD")]
        complete, result = self.run_import()
        self.assertTrue(complete)
        self.assertEqual(result["schemaVersion"], "nhtsa-safety/1.1")
        self.assertEqual(result["scope"], result["coverage"]["scope"])
        unknown, explicit, structured = result["records"]
        self.assertEqual(unknown["publicationStatus"], "unknown")
        self.assertEqual(unknown["rawRatings"]["overall"], "Temporarily unavailable")
        self.assertNotIn("OverallFrontCrashRating", unknown["rawNativeRatings"])
        self.assertEqual(explicit["publicationStatus"], "not_rated")
        self.assertEqual(set(explicit["rawRatings"].values()), {"Not Rated"})
        self.assertEqual(structured["publicationStatus"], "published")
        self.assertEqual(structured["configuration"], {
            "power": "Plug-in hybrid", "drivetrain": "FWD", "body": "SUV",
            "trim": None, "battery": "40 kWh", "generation": None})
        self.assertEqual(structured["configurationEvidence"]["battery"]["source"],
                         structured["source"])
        identity = structured["nativeIdentity"]
        self.assertEqual(identity["make"], structured["make"])
        self.assertEqual(identity["year"], structured["year"])
        self.assertEqual(unquote(urlparse(identity["source"]).path),
                         "/SafetyRatings/modelyear/2024/make/TOYOTA/model/CAMRY HYBRID")


    def test_invalid_json_preserves_partial_records(self):
        def invalid(request, timeout):
            if request.full_url.endswith("/VehicleId/5?format=json"):
                return io.BytesIO(b'{"Count": 1, "Results": [{"OverallRating": NaN}]}')
            return self.open(request, timeout)

        complete, result = self.run_import(invalid)
        self.assertFalse(complete)
        self.assertEqual(result["errors"][0]["status"], "invalid_response")
        self.assertEqual([row["vehicleId"] for row in result["records"]], ["6", "7"])

    def test_failed_forced_refresh_keeps_prior_valid_cache(self):
        self.assertTrue(self.run_import()[0])
        path = "/SafetyRatings/VehicleId/5"
        self.responses[path] = HTTPError(path, 400, "Bad request", {}, None)
        complete, result = self.run_import(force_refresh=True)
        self.assertFalse(complete)
        self.assertEqual(result["pendingVariants"][0]["vehicleId"], "5")
        self.calls.clear()
        complete, result = self.run_import()
        self.assertTrue(complete)
        self.assertEqual(result["records"][0]["ratings"]["overall"], 5)
        self.assertEqual(self.calls, [])
