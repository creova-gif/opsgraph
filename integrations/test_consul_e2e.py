#!/usr/bin/env python3
"""
Fake-service E2E for the consul-core v1 contract (mirrors the Drive E2E
pattern): a real local HTTP server implements the contract surface so the
client and the `guardian --propose` CLI path are exercised over a socket,
not through mocks.
"""

import io
import json
import sys
import threading
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from integrations.consul import ConsulUnavailable, HTTPConsulClient
import opsgraph_cli

BASE_DIR = Path(__file__).resolve().parent.parent
TOKEN = "e2e-token"
CORE_VERSION = "1.0.0-e2e"


class _ConsulHandler(BaseHTTPRequestHandler):
    runs = {}
    requests_seen = 0

    def log_message(self, *args):  # keep test output clean
        pass

    def _send_json(self, status, body):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Consul-Core-Version", CORE_VERSION)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _problem(self, status, title):
        self._send_json(status, {
            "type": "about:blank",
            "title": title,
            "status": status,
            "detail": title,
        })

    def do_POST(self):
        if self.path != "/v1/agent-runs":
            self._problem(404, "not found")
            return
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._problem(401, "missing or invalid bearer token")
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        for field in ("skill", "inputs", "company_id", "idempotency_key"):
            if field not in body:
                self._problem(400, f"missing required field: {field}")
                return

        type(self).requests_seen += 1

        if body["skill"] == "flaky-skill":
            self._problem(503, "provider unavailable")
            return

        key = body["idempotency_key"]
        if key in type(self).runs:  # idempotent replay: original result
            self._send_json(200, type(self).runs[key])
            return

        result = {
            "run_id": f"run-e2e-{type(self).requests_seen}",
            "status": "completed",
            "output": {
                "proposal": f"remediate {body['inputs'].get('title', 'the item')}",
                "patch": {"action": "manual_review",
                          "target": body["inputs"].get("affected_file")},
                "rationale": "e2e fake consul",
            },
            "provider": "fake-consul",
            "usage": {"input_tokens": 12, "output_tokens": 8},
        }
        if body["skill"] != "missing-sim-flag":
            result["simulation"] = False
        type(self).runs[key] = result
        self._send_json(200, result)


class _FakeConsul:
    def __init__(self):
        self.server = HTTPServer(("127.0.0.1", 0), _ConsulHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        _ConsulHandler.runs = {}
        _ConsulHandler.requests_seen = 0
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}"

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


class TestConsulE2E(unittest.TestCase):
    def test_round_trip_over_real_socket(self):
        with _FakeConsul() as url:
            client = HTTPConsulClient(url, TOKEN)
            result = client.run_agent(
                "guardian-remediation",
                {"category": "STALE_REVIEW", "title": "InfoSec Policy",
                 "affected_file": "/g/InfoSec Policy.pdf"},
                "acme", "key-1",
            )
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.provider, "fake-consul")
        self.assertFalse(result.simulation)
        self.assertEqual(result.core_version, CORE_VERSION)
        self.assertIn("InfoSec Policy", result.output["proposal"])

    def test_bad_token_rejected(self):
        with _FakeConsul() as url:
            client = HTTPConsulClient(url, "wrong-token")
            with self.assertRaises(ConsulUnavailable):
                client.run_agent("guardian-remediation", {}, "acme", "k")

    def test_idempotent_replay_returns_original_run(self):
        with _FakeConsul() as url:
            client = HTTPConsulClient(url, TOKEN)
            first = client.run_agent("guardian-remediation", {}, "acme", "same-key")
            second = client.run_agent("guardian-remediation", {}, "acme", "same-key")
        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(_ConsulHandler.requests_seen, 2)  # wire hit, server deduped

    def test_missing_simulation_flag_rejected_over_wire(self):
        with _FakeConsul() as url:
            client = HTTPConsulClient(url, TOKEN)
            with self.assertRaises(ConsulUnavailable):
                client.run_agent("missing-sim-flag", {}, "acme", "k")

    def test_provider_5xx_raises_unavailable(self):
        with _FakeConsul() as url:
            client = HTTPConsulClient(url, TOKEN)
            with self.assertRaises(ConsulUnavailable):
                client.run_agent("flaky-skill", {}, "acme", "k")

    def test_cli_guardian_propose_against_live_fake(self):
        with _FakeConsul() as url:
            buf = io.StringIO()
            argv = ["opsgraph", "guardian",
                    str(BASE_DIR / "examples" / "seed-b2b-saas.json"),
                    str(BASE_DIR / "examples" / "sample-drive-inventory.json"),
                    "--propose", "--consul-url", url]
            with patch.object(sys, "argv", argv), \
                    patch.dict("os.environ", {"OPSGRAPH_CONSUL_TOKEN": TOKEN}), \
                    redirect_stdout(buf):
                opsgraph_cli.main()
            out = buf.getvalue()
        self.assertIn("Remediation proposals", out)
        self.assertIn("[real]", out)  # fake returns simulation: false
        self.assertGreater(_ConsulHandler.requests_seen, 0)

    def test_cli_falls_back_to_stub_on_server_down(self):
        buf = io.StringIO()
        argv = ["opsgraph", "guardian",
                str(BASE_DIR / "examples" / "seed-b2b-saas.json"),
                str(BASE_DIR / "examples" / "sample-drive-inventory.json"),
                "--propose", "--consul-url", "http://127.0.0.1:9"]
        with patch.object(sys, "argv", argv), redirect_stdout(buf):
            opsgraph_cli.main()
        self.assertIn("[simulation]", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
