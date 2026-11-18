#!/usr/bin/env python3
"""
Unit tests for OpsGraph Workspace Compiler.
Tests plan generation, dry-run mode, physical compilation, Master Document Register
instantiation, provenance metadata tags, and idempotency.
"""

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from compiler.compiler import WorkspaceCompiler
from inventory.scanner import WorkspaceScanner


class TestWorkspaceCompiler(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.compiler = WorkspaceCompiler()
        self.scanner = WorkspaceScanner()

        # Load Acme Cloud profile & sample drive inventory
        profile_path = self.base_dir / "examples" / "seed-b2b-saas.json"
        with open(profile_path, "r", encoding="utf-8") as f:
            self.profile = json.load(f)

        inventory_path = self.base_dir / "examples" / "sample-drive-inventory.json"
        self.inventory = self.scanner.load_snapshot(inventory_path)

        # Temporary workspace target directory
        self.temp_dir = tempfile.mkdtemp(prefix="opsgraph_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dry_run_plan(self):
        plan = self.compiler.plan(
            profile_data=self.profile,
            inventory=self.inventory,
            target_dir=self.temp_dir,
        )

        self.assertEqual(plan.company_name, "Acme Cloud Technologies, Inc.")
        self.assertEqual(len(plan.folders_to_create), 12)
        # 8 files are already present and current in the sample inventory
        self.assertEqual(len(plan.skipped_existing), 8)
        self.assertGreater(len(plan.artifacts_to_compile), 15)

    def test_physical_compilation(self):
        result = self.compiler.execute(
            profile_data=self.profile,
            inventory=self.inventory,
            target_dir=self.temp_dir,
            dry_run=False,
        )

        self.assertFalse(result.dry_run)
        target_path = Path(self.temp_dir)

        # 1. Check folder creation
        for fld in result.folders_created:
            self.assertTrue((target_path / fld).is_dir(), f"Folder {fld} should exist")

        # 2. Check Master Document Register CSV & JSON
        master_reg_csv = target_path / "00_Company_Control" / "CO-001_Master_Document_Register.csv"
        master_reg_json = target_path / "00_Company_Control" / "CO-001_Master_Document_Register.json"
        self.assertTrue(master_reg_csv.is_file(), "Master Document Register CSV must exist")
        self.assertTrue(master_reg_json.is_file(), "Master Document Register JSON must exist")

        with open(master_reg_csv, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            self.assertEqual(len(reader), 31)
            # Find Access Register entry
            es001_row = next(r for r in reader if r["Document_ID"] == "ES-001")
            self.assertEqual(es001_row["Title"], "Access Register")
            self.assertEqual(es001_row["Owner"], "CTO")
            self.assertEqual(es001_row["Criticality"], "HIGH")

        # 3. Check individual compiled artifact template with provenance header
        access_reg = target_path / "05_Engineering_Security" / "ES-001_Access_Register.md"
        self.assertTrue(access_reg.is_file(), "ES-001 Access Register template must exist")

        with open(access_reg, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("OPSGRAPH GOVERNED OPERATIONAL ARTIFACT", content)
            self.assertIn("Canonical Identifier : ES-001", content)
            self.assertIn("Accountable Owner    : CTO", content)
            self.assertIn("Acme Cloud Technologies, Inc.", content)
            self.assertIn("[FOUNDER_INPUT_REQUIRED:", content)

        # 4. Check audit log
        audit_log = target_path / "compiler_audit_log.json"
        self.assertTrue(audit_log.is_file(), "Audit log must exist")
        with open(audit_log, "r", encoding="utf-8") as f:
            log_data = json.load(f)
            self.assertEqual(log_data["company_name"], "Acme Cloud Technologies, Inc.")
            self.assertGreater(log_data["total_artifacts_compiled"], 15)

    def test_idempotent_recompilation(self):
        # Running compilation twice should not fail or corrupt existing files
        result1 = self.compiler.execute(
            profile_data=self.profile,
            inventory=self.inventory,
            target_dir=self.temp_dir,
            dry_run=False,
        )
        result2 = self.compiler.execute(
            profile_data=self.profile,
            inventory=self.inventory,
            target_dir=self.temp_dir,
            dry_run=False,
        )

        self.assertEqual(len(result1.folders_created), len(result2.folders_created))
        self.assertEqual(len(result1.artifacts_created), len(result2.artifacts_created))

    def test_register_versioning_and_provenance(self):
        target_path = Path(self.temp_dir)
        reg_json = target_path / "00_Company_Control" / "CO-001_Master_Document_Register.json"

        r1 = self.compiler.execute(
            profile_data=self.profile, inventory=self.inventory,
            target_dir=self.temp_dir, dry_run=False,
        )
        self.assertEqual(r1.register_version, 1)
        data1 = json.loads(reg_json.read_text())
        self.assertEqual(data1["register_version"], 1)
        self.assertEqual(data1["provenance"]["action"], "compile")
        self.assertEqual(data1["provenance"]["ruleset_version"], "0.3")
        self.assertIn("profile_sha256", data1["provenance"])
        self.assertEqual(len(data1["entries"]), 31)
        v1_rows = {r["Document_ID"]: r["Row_Version"] for r in data1["entries"]}

        # identical recompile: same content -> version holds
        r2 = self.compiler.execute(
            profile_data=self.profile, inventory=self.inventory,
            target_dir=self.temp_dir, dry_run=False,
        )
        self.assertEqual(r2.register_version, 1)
        data2 = json.loads(reg_json.read_text())
        self.assertEqual(data2["provenance"]["action"], "recompile")
        self.assertEqual(data2["provenance"]["rows_unchanged"], 31)

        # changed input -> register version bumps, changed rows bump
        profile2 = json.loads(json.dumps(self.profile))
        profile2["functions"][0]["owner"] = "CTO (Fractional)"  # Owner column changes
        r3 = self.compiler.execute(
            profile_data=profile2, inventory=self.inventory,
            target_dir=self.temp_dir, dry_run=False,
        )
        self.assertEqual(r3.register_version, 2)
        data3 = json.loads(reg_json.read_text())
        self.assertEqual(data3["provenance"]["previous_register_version"], 1)
        self.assertGreater(data3["provenance"]["rows_changed"] + data3["provenance"]["rows_added"], 0)
        v3_rows = {r["Document_ID"]: r["Row_Version"] for r in data3["entries"]}
        self.assertTrue(
            any(v3_rows[k] > v1_rows[k] for k in v1_rows if v3_rows.get(k) is not None),
            "at least one row version must bump on changed input",
        )


if __name__ == "__main__":
    unittest.main()
