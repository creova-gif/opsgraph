#!/usr/bin/env python3
"""Tests for the deterministic Ask Company answerer."""

import json
import unittest
from pathlib import Path

from inventory.scanner import WorkspaceScanner
from qa.answerer import CompanyAnswerer


class TestCompanyAnswerer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Path(__file__).resolve().parent.parent
        with open(base / "examples" / "seed-b2b-saas.json", encoding="utf-8") as f:
            cls.profile = json.load(f)
        cls.inventory = WorkspaceScanner().load_snapshot(
            base / "examples" / "sample-drive-inventory.json"
        )
        cls.answerer = CompanyAnswerer()

    def ask(self, q):
        return self.answerer.ask(q, self.profile, self.inventory)

    def test_score_question(self):
        a = self.ask("what is our readiness score?")
        self.assertEqual(a.intent, "score")
        self.assertIn("%", a.text)
        self.assertIn("missing", a.text)
        self.assertTrue(a.citations)

    def test_missing_question(self):
        a = self.ask("which artifacts are missing?")
        self.assertEqual(a.intent, "missing")
        self.assertIn("missing artifact", a.text)
        self.assertTrue(a.citations)

    def test_stale_question(self):
        a = self.ask("is anything stale or overdue for review?")
        self.assertEqual(a.intent, "stale")

    def test_blockers_question(self):
        a = self.ask("what is blocking our next deal?")
        self.assertEqual(a.intent, "blockers")
        self.assertTrue(a.citations)

    def test_drift_question(self):
        a = self.ask("what did the guardian find? any drift?")
        self.assertEqual(a.intent, "drift")

    def test_artifact_lookup_by_name(self):
        a = self.ask("do we have a master document register?")
        self.assertEqual(a.intent, "artifact")
        self.assertIn("Master Document Register", a.text)
        self.assertIn("Status:", a.text)

    def test_artifact_lookup_by_id(self):
        # CO-001 is a real artifact ID in the seeded ruleset
        a = self.ask("what's the status of CO-001?")
        self.assertEqual(a.intent, "artifact")
        self.assertIn("CO-001", a.text)

    def test_owner_question(self):
        a = self.ask("who owns the master document register?")
        self.assertEqual(a.intent, "owner")
        self.assertIn("owns", a.text)
        self.assertTrue(a.citations)

    def test_fallback_is_honest(self):
        a = self.ask("what is the meaning of life?")
        self.assertEqual(a.intent, "fallback")
        self.assertEqual(a.confidence, "low")
        self.assertIn("deterministic", a.text)

    def test_source_marked_deterministic(self):
        for q in (
            "readiness score",
            "what is missing",
            "who owns the policy register",
        ):
            self.assertEqual(self.ask(q).source, "deterministic")


if __name__ == "__main__":
    unittest.main()
