#!/usr/bin/env python3
"""
Unit tests for OpsGraph Interactive Dashboard Generator.
Verifies HTML compilation, metric data injection, and output integrity.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from dashboard.generator import DashboardGenerator
from inventory.scanner import WorkspaceScanner


class TestDashboardGenerator(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.generator = DashboardGenerator()
        self.scanner = WorkspaceScanner()

        # Load Acme Cloud profile & sample drive inventory
        profile_path = self.base_dir / "examples" / "seed-b2b-saas.json"
        with open(profile_path, "r", encoding="utf-8") as f:
            self.profile = json.load(f)

        inventory_path = self.base_dir / "examples" / "sample-drive-inventory.json"
        self.inventory = self.scanner.load_snapshot(inventory_path)

        self.temp_dir = tempfile.mkdtemp(prefix="opsgraph_dashboard_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dashboard_html_generation(self):
        output_file = Path(self.temp_dir) / "test_dashboard.html"
        html = self.generator.generate(
            profile_data=self.profile,
            inventory=self.inventory,
            output_path=output_file,
        )

        self.assertTrue(output_file.is_file(), "Dashboard HTML file must be created")
        self.assertGreater(len(html), 5000, "Dashboard HTML must be substantial")

        # Verify key UI components in rendered HTML
        self.assertIn("Acme Cloud Technologies, Inc.", html)
        self.assertIn("OpsGraph", html)
        self.assertIn("numeral", html)  # readiness numeral (no donut chart — banned)
        self.assertIn("29.9", html)  # readiness score
        self.assertIn("[CRITICAL DRIFT]", html)  # <40 -> critical state tag
        self.assertIn("Immediate blockers", html)
        self.assertIn("Gap matrix", html)
        self.assertIn("Guardian drift feed", html)
        self.assertIn("GAP_DATA", html)
        self.assertIn("GUARDIAN_DATA", html)
        # brand tokens shipped
        self.assertIn("--paper: #F7F5F0", html)
        self.assertIn("--spec: #1F3FA0", html)


if __name__ == "__main__":
    unittest.main()
