#!/usr/bin/env python3
"""
Unit tests for Company OS Gap Analysis Engine.
Verifies gap detection, staleness calculation, duplicate collision detection,
domain score rollups, and overall Company Infrastructure Score calculation.
"""

import datetime
import json
import unittest
from pathlib import Path

from gap_engine import GapAnalyzer
from inventory import WorkspaceScanner
from resolver import StateResolver


class TestGapEngine(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.rules_path = self.base_dir / "rules" / "core-artifacts.json"
        self.resolver = StateResolver(rules_path=self.rules_path)
        self.scanner = WorkspaceScanner()

        # Load Acme Cloud profile & sample drive inventory
        profile_path = self.base_dir / "examples" / "seed-b2b-saas.json"
        with open(profile_path, "r", encoding="utf-8") as f:
            self.profile = json.load(f)

        inventory_path = self.base_dir / "examples" / "sample-drive-inventory.json"
        self.inventory = self.scanner.load_snapshot(inventory_path)

        # Fixed reference time matching the scan metadata: 2026-10-20T18:00:00Z
        self.ref_time = datetime.datetime.fromisoformat("2026-10-20T18:00:00+00:00")
        self.analyzer = GapAnalyzer(ref_time=self.ref_time)

    def test_acme_cloud_gap_analysis(self):
        resolution = self.resolver.resolve(self.profile)
        gap_report = self.analyzer.analyze(resolution, self.inventory)

        self.assertEqual(gap_report.company_name, "Acme Cloud Technologies, Inc.")
        # Baseline score should be in the ~25-35% range for this unorganized seed startup
        self.assertGreater(gap_report.infrastructure_score, 20.0)
        self.assertLess(gap_report.infrastructure_score, 45.0)

        # Check that Master Document Register (CO-001) is detected as MISSING
        co001 = next(item for item in gap_report.items if item.artifact_id == "CO-001")
        self.assertEqual(co001.status, "MISSING")
        self.assertEqual(co001.criticality, "high")
        self.assertEqual(co001.level, "required")

        # Check that Incident Record (ES-002) is detected as DUPLICATE_COLLISION (two copies in Drive)
        es002 = next(item for item in gap_report.items if item.artifact_id == "ES-002")
        self.assertEqual(es002.status, "DUPLICATE_COLLISION")
        self.assertEqual(len(es002.matched_files), 2)

        # Check that Vendor Register (FN-001) is detected as PRESENT_STALE (last modified 2024, cadence 90d)
        fn001 = next(item for item in gap_report.items if item.artifact_id == "FN-001")
        self.assertEqual(fn001.status, "PRESENT_STALE")
        self.assertGreater(fn001.days_stale, 700)

        # Check that Onboarding Checklist (PE-002) is PRESENT_CURRENT
        pe002 = next(item for item in gap_report.items if item.artifact_id == "PE-002")
        self.assertEqual(pe002.status, "PRESENT_CURRENT")

        # Check domain scores exist for all primary roots
        domain_roots = {d.root_id for d in gap_report.domain_scores}
        self.assertIn("00", domain_roots)
        self.assertIn("01", domain_roots)
        self.assertIn("02", domain_roots)
        self.assertIn("03", domain_roots)
        self.assertIn("05", domain_roots)
        self.assertIn("06", domain_roots)

    def test_immediate_blockers_isolated(self):
        resolution = self.resolver.resolve(self.profile)
        gap_report = self.analyzer.analyze(resolution, self.inventory)

        # Blockers must be high-criticality, required, and not present-current
        for blocker in gap_report.immediate_blockers:
            self.assertEqual(blocker.criticality, "high")
            self.assertEqual(blocker.level, "required")
            self.assertIn(blocker.status, ("MISSING", "PRESENT_STALE", "DUPLICATE_COLLISION"))


if __name__ == "__main__":
    unittest.main()
