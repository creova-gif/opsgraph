#!/usr/bin/env python3
"""
Unit tests for OpsGraph Guardian Monitoring Engine.
Tests unindexed file detection, unowned file alerts, policy staleness tracking,
version collision detection, and health score calculation.
"""

import datetime
import json
import unittest
from pathlib import Path

from guardian.guardian import CompanyGuardian
from inventory.scanner import WorkspaceScanner


class TestCompanyGuardian(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(__file__).resolve().parent.parent

        # Load Acme Cloud profile & sample drive inventory
        profile_path = self.base_dir / "examples" / "seed-b2b-saas.json"
        with open(profile_path, "r", encoding="utf-8") as f:
            self.profile = json.load(f)

        inventory_path = self.base_dir / "examples" / "sample-drive-inventory.json"
        self.scanner = WorkspaceScanner()
        self.inventory = self.scanner.load_snapshot(inventory_path)

        # Fixed reference time matching the scan metadata: 2026-10-20T18:00:00Z
        self.ref_time = datetime.datetime.fromisoformat("2026-10-20T18:00:00+00:00")
        self.guardian = CompanyGuardian(ref_time=self.ref_time)

    def test_guardian_drift_detection(self):
        digest = self.guardian.audit(
            profile_data=self.profile,
            inventory=self.inventory,
        )

        self.assertEqual(digest.company_name, "Acme Cloud Technologies, Inc.")
        self.assertGreater(digest.total_drift_events, 0)
        self.assertGreater(digest.high_severity_count, 0)

        # 1. Verify Unowned File detection (file-008 owned by former_contractor@acmecloud.io)
        unowned_events = [e for e in digest.events if e.category == "UNOWNED_FILE"]
        self.assertTrue(len(unowned_events) > 0, "Must detect contractor or unowned files")
        self.assertIn("former_contractor", unowned_events[0].description)

        # 2. Verify Duplicate Collision detection (Incident Record Template conflict)
        dup_events = [e for e in digest.events if e.category == "DUPLICATE_COLLISION"]
        self.assertTrue(len(dup_events) > 0, "Must detect duplicate collisions")
        self.assertEqual(dup_events[0].affected_artifact_id, "ES-002")

        # 3. Verify Stale Review detection (Vendor Register FN-001 last modified 2024)
        stale_events = [e for e in digest.events if e.category == "STALE_REVIEW" and e.affected_artifact_id == "FN-001"]
        self.assertTrue(len(stale_events) > 0, "Must flag FN-001 Vendor Register as stale review")

        # 4. Verify Misplaced File detection (files in /Old Backups & Shared)
        misplaced_events = [e for e in digest.events if e.category == "MISPLACED_FILE"]
        self.assertTrue(len(misplaced_events) > 0, "Must detect misplaced files in backup folders")

        # 5. Check Health Score calculation (100% minus penalties)
        self.assertGreater(digest.health_score, 0.0)
        self.assertLess(digest.health_score, 100.0)

        # 6. Check Action Queue matches events
        self.assertEqual(len(digest.action_queue), len(digest.events))


if __name__ == "__main__":
    unittest.main()
