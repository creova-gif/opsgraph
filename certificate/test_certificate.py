#!/usr/bin/env python3
"""Tests for the readiness certificate generator."""

import json
import unittest
from pathlib import Path

from certificate.generator import CertificateGenerator
from inventory.scanner import WorkspaceScanner


class TestCertificateGenerator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Path(__file__).resolve().parent.parent
        with open(base / "examples" / "seed-b2b-saas.json", encoding="utf-8") as f:
            cls.profile = json.load(f)
        cls.inventory = WorkspaceScanner().load_snapshot(
            base / "examples" / "sample-drive-inventory.json"
        )
        cls.html = CertificateGenerator().generate(cls.profile, cls.inventory)

    def test_real_data_rendered(self):
        self.assertIn("Acme Cloud Technologies, Inc.", self.html)
        self.assertIn("29.9", self.html)  # real score
        self.assertIn("[CRITICAL DRIFT]", self.html)  # <40 state
        self.assertIn("acmecloud.io", self.html)
        self.assertIn("opsgraph-seed@", self.html)  # real ruleset version

    def test_cert_number_derived_from_company_and_date(self):
        self.assertIn("OG-", self.html)
        self.assertIn("REV B", self.html)

    def test_honesty_attestation_verbatim(self):
        self.assertIn("certifies a measurement, not compliance", self.html)
        self.assertIn("[SIMULATION]", self.html)

    def test_approver_field(self):
        html = CertificateGenerator().generate(
            self.profile, self.inventory,
            approver="j.mafie@acme", run_ref="run #7",
        )
        self.assertIn("j.mafie@acme", html)
        self.assertIn("run #7", html)

    def test_marker_position_matches_score(self):
        self.assertIn("left:29.9%", self.html)


if __name__ == "__main__":
    unittest.main()
