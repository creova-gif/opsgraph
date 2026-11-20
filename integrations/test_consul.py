#!/usr/bin/env python3
"""
Unit tests for the consul-core v1 client seam (integrations/consul.py).
Covers the deterministic stub, the HTTP client's request/response mapping,
and the ConsulUnavailable error path.
"""

import io
import json
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from guardian.guardian import CompanyGuardian
from integrations.consul import (
    ConsulUnavailable,
    HTTPConsulClient,
    StubConsulClient,
)
from inventory.scanner import WorkspaceScanner


def _event(category, **overrides):
    event = {
        "event_id": "DRIFT-001",
        "severity": "MEDIUM",
        "category": category,
        "title": "test event",
        "description": "test description",
        "affected_file": "/drive/some folder/Doc.pdf",
        "affected_artifact_id": None,
        "assigned_owner": "COO / Founder",
        "remediation_proposal": "baseline proposal",
    }
    event.update(overrides)
    return event


class _FakeResponse:
    def __init__(self, payload, headers=None):
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))
        self.headers = headers or {}

    def read(self):
        return self._buf.getvalue()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestStubConsulClient(unittest.TestCase):
    def setUp(self):
        self.client = StubConsulClient()

    def test_marks_output_as_simulation(self):
        result = self.client.run_agent(
            "guardian-remediation", _event("MISPLACED_FILE"), "acme", "k1"
        )
        self.assertTrue(result.simulation)
        self.assertEqual(result.provider, "simulation")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.run_id, "stub-k1")

    def test_deterministic_output(self):
        inputs = _event("UNINDEXED_FILE")
        first = self.client.run_agent("guardian-remediation", inputs, "acme", "k1")
        second = self.client.run_agent("guardian-remediation", inputs, "acme", "k1")
        self.assertEqual(first, second)

    def test_proposal_per_event_category(self):
        for category in (
            "MISPLACED_FILE", "UNINDEXED_FILE", "STALE_REVIEW",
            "UNOWNED_FILE", "DUPLICATE_COLLISION",
        ):
            result = self.client.run_agent(
                "guardian-remediation", _event(category), "acme", f"k-{category}"
            )
            self.assertTrue(result.output["proposal"], f"empty proposal for {category}")
            self.assertIn("/drive/some folder/Doc.pdf", result.output["proposal"])
            self.assertEqual(result.output["patch"]["target"], "/drive/some folder/Doc.pdf")
            self.assertTrue(result.output["rationale"])

    def test_unknown_category_gets_manual_review(self):
        result = self.client.run_agent(
            "guardian-remediation", _event("SOMETHING_NEW"), "acme", "k9"
        )
        self.assertIn("manual review", result.output["proposal"])
        self.assertEqual(result.output["patch"]["action"], "manual_review")

    def test_covers_every_real_guardian_category(self):
        base_dir = Path(__file__).resolve().parent.parent
        with open(base_dir / "examples" / "seed-b2b-saas.json", "r", encoding="utf-8") as f:
            profile = json.load(f)
        inventory = WorkspaceScanner().load_snapshot(
            base_dir / "examples" / "sample-drive-inventory.json"
        )
        digest = CompanyGuardian().audit(profile_data=profile, inventory=inventory)
        self.assertGreater(digest.total_drift_events, 0)
        for event in digest.events:
            result = self.client.run_agent(
                "guardian-remediation",
                {k: getattr(event, k) for k in event.__dataclass_fields__},
                "acme",
                event.event_id,
            )
            self.assertTrue(
                result.output["proposal"], f"empty proposal for {event.category}"
            )


class TestHTTPConsulClient(unittest.TestCase):
    def test_posts_contract_request(self):
        payload = {
            "run_id": "run-42",
            "status": "completed",
            "output": {"proposal": "do the thing"},
            "provider": "gemini-2.0-flash",
            "simulation": False,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)) as mock_open:
            client = HTTPConsulClient("https://consul.example.com/", "tok-123")
            result = client.run_agent(
                "guardian-remediation", _event("STALE_REVIEW"), "acme", "k7"
            )

        req = mock_open.call_args[0][0]
        self.assertEqual(req.full_url, "https://consul.example.com/v1/agent-runs")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Authorization"), "Bearer tok-123")
        self.assertEqual(req.get_header("Content-type"), "application/json")
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["skill"], "guardian-remediation")
        self.assertEqual(body["company_id"], "acme")
        self.assertEqual(body["idempotency_key"], "k7")
        self.assertEqual(body["inputs"]["category"], "STALE_REVIEW")

        self.assertEqual(result.run_id, "run-42")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.output["proposal"], "do the thing")
        self.assertEqual(result.provider, "gemini-2.0-flash")
        self.assertFalse(result.simulation)
        self.assertEqual(result.usage["input_tokens"], 10)

    def test_url_error_raises_consul_unavailable(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            client = HTTPConsulClient("http://localhost:9", "tok")
            with self.assertRaises(ConsulUnavailable):
                client.run_agent("guardian-remediation", {}, "acme", "k1")

    def test_http_error_raises_consul_unavailable(self):
        err = urllib.error.HTTPError(
            "http://x/v1/agent-runs", 503, "unavailable", {}, None
        )
        with patch("urllib.request.urlopen", side_effect=err):
            client = HTTPConsulClient("http://localhost:9", "tok")
            with self.assertRaises(ConsulUnavailable):
                client.run_agent("guardian-remediation", {}, "acme", "k1")

    def test_timeout_passed_to_urlopen(self):
        payload = {"run_id": "r1", "status": "completed", "output": {},
                   "provider": "p", "simulation": False}
        with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)) as mock_open:
            HTTPConsulClient("http://x", "tok", timeout=12.5).run_agent(
                "guardian-remediation", {}, "acme", "k1"
            )
        self.assertEqual(mock_open.call_args.kwargs["timeout"], 12.5)

    def test_missing_simulation_field_is_rejected(self):
        # contract requires an explicit simulation flag; absent must not
        # silently read as False or canned output could pass as real work
        payload = {"run_id": "r1", "status": "completed", "output": {},
                   "provider": "gemini-2.0-flash"}
        with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)):
            client = HTTPConsulClient("http://x", "tok")
            with self.assertRaises(ConsulUnavailable):
                client.run_agent("guardian-remediation", {}, "acme", "k1")

    def test_core_version_header_captured(self):
        payload = {"run_id": "r1", "status": "completed", "output": {},
                   "provider": "p", "simulation": False}
        resp = _FakeResponse(payload, headers={"X-Consul-Core-Version": "1.4.0"})
        with patch("urllib.request.urlopen", return_value=resp):
            result = HTTPConsulClient("http://x", "tok").run_agent(
                "guardian-remediation", {}, "acme", "k1"
            )
        self.assertEqual(result.core_version, "1.4.0")

    def test_policy_forwarded_when_set(self):
        payload = {"run_id": "r1", "status": "completed", "output": {},
                   "provider": "p", "simulation": False}
        with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)) as mock_open:
            HTTPConsulClient("http://x", "tok").run_agent(
                "guardian-remediation", {}, "acme", "k1",
                policy={"max_tokens": 2000, "timeout_seconds": 60},
            )
        body = json.loads(mock_open.call_args[0][0].data.decode("utf-8"))
        self.assertEqual(body["policy"]["max_tokens"], 2000)

    def test_policy_omitted_when_none(self):
        payload = {"run_id": "r1", "status": "completed", "output": {},
                   "provider": "p", "simulation": False}
        with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)) as mock_open:
            HTTPConsulClient("http://x", "tok").run_agent(
                "guardian-remediation", {}, "acme", "k1"
            )
        body = json.loads(mock_open.call_args[0][0].data.decode("utf-8"))
        self.assertNotIn("policy", body)


if __name__ == "__main__":
    unittest.main()
