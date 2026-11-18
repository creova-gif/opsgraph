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


if __name__ == "__main__":
    unittest.main()
