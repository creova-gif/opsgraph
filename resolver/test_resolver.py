#!/usr/bin/env python3
"""
Unit tests for OpsGraph State Resolver Engine.
Tests deterministic condition evaluation, topological sorting, and owner mapping.
"""

import json
import unittest
from pathlib import Path

from resolver import StateResolver


class TestStateResolver(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.rules_path = self.base_dir / "rules" / "core-artifacts.json"
        self.resolver = StateResolver(rules_path=self.rules_path)

    def test_seed_b2b_saas_resolution(self):
        profile_path = self.base_dir / "examples" / "seed-b2b-saas.json"
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)

        report = self.resolver.resolve(profile)
        self.assertEqual(report.total_evaluated, 31)
        self.assertEqual(report.stage, "seed")
        self.assertEqual(report.employee_count, 14)
        
        # In Seed B2B SaaS with enterprise + soc2 triggers, critical security and governance are elevated
        self.assertEqual(report.required_count, 20)
        self.assertEqual(report.recommended_count, 10)
        self.assertEqual(report.optional_count, 1)

        # Check that ES-001 (Access Register) is required due to enterprise_sales and soc2_iso
        es001 = next(a for a in report.artifacts if a.id == "ES-001")
        self.assertEqual(es001.level, "required")
        self.assertIn("Matched trigger(s)", es001.reason)
        self.assertEqual(es001.resolved_owner, "CTO")

        # Check topological sort: CO-003 (Company Profile) has no dependencies and must precede CO-001
        self.assertIn("CO-003", report.compilation_order)
        self.assertIn("CO-001", report.compilation_order)
        self.assertLess(
            report.compilation_order.index("CO-003"),
            report.compilation_order.index("CO-001"),
        )

    def test_preseed_bootstrap_resolution(self):
        profile_path = self.base_dir / "examples" / "preseed-bootstrap.json"
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)

        report = self.resolver.resolve(profile)
        self.assertEqual(report.total_evaluated, 31)
        self.assertEqual(report.stage, "pre_seed")
        self.assertEqual(report.employee_count, 3)

        # In pre-seed with only fundraise trigger, FN-004 (Data Room Index) is elevated to required
        fn004 = next(a for a in report.artifacts if a.id == "FN-004")
        self.assertEqual(fn004.level, "required")
        self.assertIn("fundraise_data_room", fn004.reason)

        # Training Register (PE-005) remains optional since no SOC2/audit trigger
        pe005 = next(a for a in report.artifacts if a.id == "PE-005")
        self.assertEqual(pe005.level, "optional")

    def test_series_a_rapid_hiring_resolution(self):
        profile_path = self.base_dir / "examples" / "series-a-rapid-hiring.json"
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)

        report = self.resolver.resolve(profile)
        self.assertEqual(report.total_evaluated, 31)
        self.assertEqual(report.stage, "series_a")
        self.assertEqual(report.employee_count, 38)

        # Hiring Checklist PE-001 is required
        pe001 = next(a for a in report.artifacts if a.id == "PE-001")
        self.assertEqual(pe001.level, "required")

        # Approval Matrix FN-002 is elevated because employee_count 38 >= 15
        fn002 = next(a for a in report.artifacts if a.id == "FN-002")
        self.assertEqual(fn002.level, "required")
        self.assertIn("Headcount 38 >= 15", fn002.reason)

        # Monthly Operating Review GV-004 is elevated because employee_count 38 >= 20
        gv004 = next(a for a in report.artifacts if a.id == "GV-004")
        self.assertEqual(gv004.level, "required")
        self.assertIn("Headcount 38 >= 20", gv004.reason)

    def test_first_match_override_precedence(self):
        """When multiple overrides match, the first wins and the rest are
        surfaced as ignored conflicts in the reason."""
        import tempfile

        rules = {
            "taxonomy_roots": {"00": "Company Control"},
            "artifacts": [{
                "id": "T-001",
                "name": "Test Artifact",
                "root": "00",
                "type": "record",
                "criticality": "high",
                "owner_role": "founder",
                "review_cadence_days": 90,
                "requirement": {
                    "default": "recommended",
                    "overrides": [
                        {"when": {"stage_gte": "seed"}, "level": "optional"},
                        {"when": {"employees_gte": 1}, "level": "required"},
                    ],
                },
            }],
        }
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(rules, f)
            rules_path = Path(f.name)

        resolver = StateResolver(rules_path=rules_path)
        report = resolver.resolve({
            "company": {"legal_name": "Test Co"},
            "stage": {"funding_stage": "seed", "employee_count": 10},
            "triggers": [],
            "functions": [],
        })
        art = report.artifacts[0]
        self.assertEqual(art.level, "optional")  # first override wins
        self.assertIn("Override applied", art.reason)
        self.assertIn("ignored by first-match precedence", art.reason)
        self.assertIn("required", art.reason)  # the losing level is still visible

    def test_determinism_across_runs(self):
        profile_path = self.base_dir / "examples" / "seed-b2b-saas.json"
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)

        run1 = self.resolver.resolve(profile)
        run2 = self.resolver.resolve(profile)

        self.assertEqual(run1.compilation_order, run2.compilation_order)
        self.assertEqual(run1.required_count, run2.required_count)
        self.assertEqual(
            [a.reason for a in run1.artifacts],
            [a.reason for a in run2.artifacts],
        )


if __name__ == "__main__":
    unittest.main()
