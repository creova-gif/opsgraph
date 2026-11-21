#!/usr/bin/env python3
"""
Unit tests for the OpsGraph SQLite ProfileStore.
Covers schema validation, versioned saves, retrieval, listing, and key derivation.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dataclasses import asdict
from types import SimpleNamespace

import opsgraph_cli
from inventory.scanner import SnapshotSource, snapshot_from_data
from store.store import ProfileStore, company_id_for


def _valid_profile():
    return json.loads((BASE_DIR / "examples" / "seed-b2b-saas.json").read_text())


class TestProfileStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="opsgraph_store_"))
        self.store = ProfileStore(self.temp_dir / "test.db")

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_company_id_slugification(self):
        profile = _valid_profile()
        cid = company_id_for(profile)
        # domain acmecloud.io -> acmecloud-io
        self.assertEqual(cid, "acmecloud-io")

        name_only = {"company": {"legal_name": "Acme Cloud Technologies, Inc."}}
        self.assertEqual(company_id_for(name_only), "acme-cloud-technologies-inc")

    def test_save_and_get_versioned(self):
        profile = _valid_profile()
        cid, v1 = self.store.save_profile(profile)
        self.assertEqual((cid, v1), ("acmecloud-io", 1))

        profile["stage"]["employee_count"] = 42
        cid2, v2 = self.store.save_profile(profile)
        self.assertEqual((cid2, v2), ("acmecloud-io", 2))

        latest = self.store.get_profile(cid)
        self.assertEqual(latest["stage"]["employee_count"], 42)

        old = self.store.get_profile(cid, version=1)
        self.assertNotEqual(old["stage"]["employee_count"], 42)

        versions = self.store.list_versions(cid)
        self.assertEqual([v["version"] for v in versions], [1, 2])

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get_profile("nope"))
        self.assertIsNone(self.store.get_profile("acmecloud-io", version=99))

    def test_list_companies(self):
        self.store.save_profile(_valid_profile())
        companies = self.store.list_companies()
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0]["company_id"], "acmecloud-io")
        self.assertEqual(companies[0]["latest_version"], 1)

    def test_schema_validation_rejects_bad_profile(self):
        with self.assertRaises(ValueError):
            self.store.save_profile({"company": {"legal_name": "Missing everything else"}})
        self.assertEqual(self.store.list_companies(), [])

    def test_governed_profile_validates_and_saves(self):
        profile = _valid_profile()
        profile["governance"] = {"require_compile_approval": True}
        cid, version = self.store.save_profile(profile)
        self.assertEqual((cid, version), ("acmecloud-io", 1))
        self.assertTrue(self.store.get_profile(cid)["governance"]["require_compile_approval"])

    def test_governance_flag_must_be_boolean(self):
        profile = _valid_profile()
        profile["governance"] = {"require_compile_approval": "yes"}
        with self.assertRaises(ValueError):
            self.store.save_profile(profile)


class TestRunHistory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="opsgraph_runs_"))
        self.store = ProfileStore(self.temp_dir / "test.db")
        cid, _ = self.store.save_profile(_valid_profile())
        self.cid = cid

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_list_runs(self):
        r1 = self.store.save_run(self.cid, "gap", {"score": 29.9}, "score=29.9%")
        r2 = self.store.save_run(self.cid, "guardian", {"health": 88.0}, "health=88%")
        self.assertEqual((r1, r2), (1, 2))

        runs = self.store.list_runs(company_id=self.cid)
        self.assertEqual([r["run_type"] for r in runs], ["guardian", "gap"])  # newest first

        only_gap = self.store.list_runs(run_type="gap")
        self.assertEqual(len(only_gap), 1)
        self.assertEqual(only_gap[0]["summary"], "score=29.9%")

        run = self.store.get_run(r1)
        self.assertEqual(run["payload"]["score"], 29.9)
        self.assertIsNone(self.store.get_run(999))

    def test_latest_runs_by_type(self):
        self.store.save_run(self.cid, "gap", {"score": 20}, "score=20%")
        self.store.save_run(self.cid, "scan", {"files": 10}, "files=10")
        gap2 = self.store.save_run(self.cid, "gap", {"score": 30}, "score=30%")

        latest = self.store.latest_runs_by_type(self.cid)
        self.assertEqual(set(latest), {"gap", "scan"})
        self.assertEqual(latest["gap"]["id"], gap2)
        self.assertEqual(latest["gap"]["summary"], "score=30%")
        self.assertEqual(latest["scan"]["summary"], "files=10")

    def test_latest_runs_by_type_empty(self):
        self.assertEqual(self.store.latest_runs_by_type(self.cid), {})

    def test_run_requires_existing_company(self):
        with self.assertRaises(ValueError):
            self.store.save_run("ghost-co", "gap", {})

    def test_run_type_validated(self):
        with self.assertRaises(ValueError):
            self.store.save_run(self.cid, "warp-drive", {})


class TestApprovals(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="opsgraph_approvals_"))
        self.store = ProfileStore(self.temp_dir / "test.db")
        cid, _ = self.store.save_profile(_valid_profile())
        self.cid = cid

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_and_effective_approvals(self):
        d1 = self.store.record_decision(self.cid, "ES-001", "approved", "Founder")
        d2 = self.store.record_decision(self.cid, "CO-001", "approved", "Founder", "ship it")
        self.assertEqual((d1, d2), (1, 2))
        self.assertEqual(self.store.approved_artifact_ids(self.cid), {"ES-001", "CO-001"})

    def test_latest_decision_wins(self):
        self.store.record_decision(self.cid, "ES-001", "approved", "Founder")
        self.store.record_decision(self.cid, "ES-001", "rejected", "Security Lead")
        self.assertNotIn("ES-001", self.store.approved_artifact_ids(self.cid))

        self.store.record_decision(self.cid, "ES-001", "approved", "Security Lead")
        self.assertIn("ES-001", self.store.approved_artifact_ids(self.cid))

    def test_wildcard_approval(self):
        self.store.record_decision(self.cid, "*", "approved", "Founder")
        self.assertEqual(self.store.approved_artifact_ids(self.cid), {"*"})

    def test_decision_requires_existing_company(self):
        with self.assertRaises(ValueError):
            self.store.record_decision("ghost-co", "ES-001", "approved", "Founder")

    def test_decision_validated(self):
        with self.assertRaises(ValueError):
            self.store.record_decision(self.cid, "ES-001", "maybe", "Founder")

    def test_list_decisions_newest_first(self):
        self.store.record_decision(self.cid, "ES-001", "approved", "Founder")
        self.store.record_decision(self.cid, "CO-001", "rejected", "Security Lead", "needs legal review")
        decisions = self.store.list_decisions(self.cid)
        self.assertEqual([d["artifact_id"] for d in decisions], ["CO-001", "ES-001"])
        self.assertEqual(decisions[0]["decision"], "rejected")
        self.assertEqual(decisions[0]["approver"], "Security Lead")
        self.assertEqual(decisions[0]["note"], "needs legal review")


class TestStoreBackedInputs(unittest.TestCase):
    """--company-id commands resolve saved profile + latest recorded scan."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="opsgraph_inputs_"))
        self.db = self.temp_dir / "test.db"
        self.store = ProfileStore(self.db)
        self.cid, _ = self.store.save_profile(_valid_profile())

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _record_scan(self):
        snapshot = SnapshotSource(BASE_DIR / "examples" / "sample-drive-inventory.json").scan()
        return self.store.save_run(self.cid, "scan", asdict(snapshot), "files recorded")

    def test_snapshot_from_data_roundtrip(self):
        snapshot = SnapshotSource(BASE_DIR / "examples" / "sample-drive-inventory.json").scan()
        rebuilt = snapshot_from_data(asdict(snapshot))
        self.assertEqual(len(rebuilt.files), len(snapshot.files))
        self.assertEqual(len(rebuilt.folders), len(snapshot.folders))
        self.assertEqual(rebuilt.scan_metadata["total_files"], len(snapshot.files))
        self.assertEqual(rebuilt.files[0].name, snapshot.files[0].name)

    def test_load_profile_snapshot_from_store(self):
        self._record_scan()
        args = SimpleNamespace(
            company_id=self.cid, db=str(self.db), profile=None, inventory=None)
        profile_data, snapshot = opsgraph_cli._load_profile_snapshot(args)
        self.assertEqual(profile_data["company"]["legal_name"],
                         "Acme Cloud Technologies, Inc.")
        self.assertGreater(len(snapshot.files), 0)

    def test_store_path_errors_exit_cleanly(self):
        with self.assertRaises(SystemExit):  # unknown company
            opsgraph_cli._load_profile_snapshot(
                SimpleNamespace(company_id="ghost-co", db=str(self.db),
                                profile=None, inventory=None))
        with self.assertRaises(SystemExit):  # known company, no recorded scan
            opsgraph_cli._load_profile_snapshot(
                SimpleNamespace(company_id=self.cid, db=str(self.db),
                                profile=None, inventory=None))
        with self.assertRaises(SystemExit):  # neither company nor files
            opsgraph_cli._load_profile_snapshot(
                SimpleNamespace(company_id=None, db=str(self.db),
                                profile=None, inventory=None))


if __name__ == "__main__":
    unittest.main()
