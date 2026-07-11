import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import http_utils


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP {self.status_code}", response=self
            )

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def request(self, method, url, **kwargs):
        response = self.responses[self.calls]
        self.calls += 1
        return response


class RetryTests(unittest.TestCase):
    def test_retries_temporary_server_error(self):
        session = FakeSession([FakeResponse(503), FakeResponse(200, {"ok": True})])
        with patch.object(http_utils.settings, "api_retry_attempts", 3), patch.object(
            http_utils.settings, "api_retry_backoff", 0
        ), patch("http_utils.time.sleep"):
            result = http_utils.request_json(session, "GET", "https://example.test", operation="test")
        self.assertEqual({"ok": True}, result)
        self.assertEqual(2, session.calls)

    def test_does_not_retry_permanent_client_error(self):
        session = FakeSession([FakeResponse(400), FakeResponse(200)])
        with patch.object(http_utils.settings, "api_retry_attempts", 3):
            with self.assertRaises(requests.HTTPError):
                http_utils.request_json(session, "GET", "https://example.test", operation="test")
        self.assertEqual(1, session.calls)


if __name__ == "__main__":
    unittest.main()
