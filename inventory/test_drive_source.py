#!/usr/bin/env python3
"""
Unit tests for the Google Drive inventory source mapping layer.
snapshot_from_drive_items is a pure function — no network or credentials needed.
"""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from inventory.drive_source import snapshot_from_drive_items
from inventory.scanner import LocalDirectorySource, SnapshotSource, WorkspaceSource


class TestDrivePayloadMapping(unittest.TestCase):
    def _payload(self):
        return [
            {
                "id": "fld1", "name": "00_Company_Control",
                "mimeType": "application/vnd.google-apps.folder",
                "parents": ["rootfld"],
            },
            {
                "id": "rootfld", "name": "My Drive",
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [],
            },
            {
                "id": "f1", "name": "CO-001_Master_Document_Register.csv",
                "mimeType": "text/csv", "parents": ["fld1"],
                "createdTime": "2026-01-01T00:00:00.000Z",
                "modifiedTime": "2026-10-01T09:00:00.000Z",
                "owners": [{"emailAddress": "coo@acme.io", "displayName": "Ops"}],
                "size": "2048",
            },
            {
                "id": "f2", "name": "risk notes.gdoc",
                "mimeType": "application/vnd.google-apps.document",
                "parents": ["fld1"],
                "createdTime": "2026-02-01T00:00:00.000Z",
                "modifiedTime": "2026-09-01T00:00:00.000Z",
                "owners": [{"displayName": "Contractor"}],  # no emailAddress
                # no "size" key (Google-native files have no size)
            },
        ]

    def test_snapshot_shape_and_paths(self):
        snap = snapshot_from_drive_items(self._payload(), domain="acme.io")
        self.assertEqual(snap.scan_metadata["platform"], "google_drive")
        self.assertEqual(snap.scan_metadata["domain"], "acme.io")
        self.assertEqual(len(snap.folders), 2)
        self.assertEqual(len(snap.files), 2)

        f1 = next(f for f in snap.files if f.id == "f1")
        self.assertEqual(f1.path, "/My Drive/00_Company_Control/CO-001_Master_Document_Register.csv")
        self.assertEqual(f1.owners, ["coo@acme.io"])
        self.assertEqual(f1.size_bytes, 2048)

        f2 = next(f for f in snap.files if f.id == "f2")
        self.assertEqual(f2.owners, ["Contractor"])  # falls back to displayName
        self.assertEqual(f2.size_bytes, 0)  # absent size tolerated

    def test_folder_path_resolution(self):
        snap = snapshot_from_drive_items(self._payload())
        fld = next(f for f in snap.folders if f.id == "fld1")
        self.assertEqual(fld.path, "/My Drive/00_Company_Control")


class TestWorkspaceSourceContract(unittest.TestCase):
    def test_local_and_snapshot_sources_satisfy_protocol(self):
        self.assertIsInstance(LocalDirectorySource(Path(".")), WorkspaceSource)
        self.assertIsInstance(SnapshotSource(Path("x.json")), WorkspaceSource)


if __name__ == "__main__":
    unittest.main()
