import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlparse

from tools.import_nhtsa import AcquisitionError, Client, acquire, retry_after


def vehicle(vid, description):
    return {"VehicleId": vid, "VehicleDescription": description}


def detail(vid, model, stars):
    return {**vehicle(vid, model), "ModelYear": 2024, "Make": "TOYOTA",
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
            self.make_path + "/model/CAMRY": [vehicle(5, "Camry AWD"), vehicle(6, "Camry FWD")],
            self.make_path + "/model/CAMRY%20HYBRID": [vehicle(5, "Another source label"),
                                                      vehicle(7, "Camry Hybrid")],
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

    def run_import(self, opener=None):
        snapshots = []
        complete = acquire(Client(self.cache, interval=0, opener=opener or self.open),
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
