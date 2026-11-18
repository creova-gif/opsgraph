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

# ---------------------------------------------------------------------------
# Fake-service E2E: exercises scan(), scan_delta(), retry, and merge_delta
# through the same duck-typed request path as the real googleapiclient.
# ---------------------------------------------------------------------------

class _FakeHttpError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.resp = type("Resp", (), {"status": status})()


class _FakeRequest:
    def __init__(self, responder):
        self._responder = responder

    def execute(self):
        return self._responder()


class _FakeFilesApi:
    def __init__(self, service):
        self._svc = service

    def list(self, **kwargs):
        return _FakeRequest(lambda: self._svc._files_list(kwargs))


class _FakeChangesApi:
    def __init__(self, service):
        self._svc = service

    def getStartPageToken(self, **kwargs):
        return _FakeRequest(lambda: self._svc._start_token(kwargs))

    def list(self, **kwargs):
        return _FakeRequest(lambda: self._svc._changes_list(kwargs))


class FakeDriveService:
    """Minimal in-memory Drive v3 service for E2E tests.

    - `items`: full files.list fixture (list of file dicts)
    - `changes`: changes.list fixture keyed by pageToken -> response dict
    - `failures`: list of HTTP statuses injected before the next success
    """

    def __init__(self, items, changes=None, start_token="tok-1", failures=None):
        self.items = items
        self.change_pages = changes or {}
        self.start_token = start_token
        self.failures = list(failures or [])
        self.files_calls = []
        self.changes_calls = []

    def _maybe_fail(self):
        if self.failures:
            raise _FakeHttpError(self.failures.pop(0))

    def files(self):
        return _FakeFilesApi(self)

    def changes(self):
        return _FakeChangesApi(self)

    def _files_list(self, params):
        self.files_calls.append(params)
        self._maybe_fail()
        page_size = params.get("pageSize", 1000)
        token = params.get("pageToken")
        start = int(token) if token else 0
        page = self.items[start:start + page_size]
        resp = {"files": page}
        nxt = start + page_size
        if nxt < len(self.items):
            resp["nextPageToken"] = str(nxt)
        return resp

    def _start_token(self, params):
        self._maybe_fail()
        return {"startPageToken": self.start_token}

    def _changes_list(self, params):
        self.changes_calls.append(params)
        self._maybe_fail()
        return self.change_pages.get(params["pageToken"], {"newStartPageToken": "tok-final"})


from inventory.drive_source import GoogleDriveSource, merge_delta


class TestDriveSourceE2E(unittest.TestCase):
    def _base_items(self):
        return [
            {"id": "fld1", "name": "00_Company_Control",
             "mimeType": "application/vnd.google-apps.folder", "parents": []},
            {"id": "f1", "name": "CO-001 register.csv", "mimeType": "text/csv",
             "parents": ["fld1"], "createdTime": "2026-01-01T00:00:00Z",
             "modifiedTime": "2026-02-01T00:00:00Z",
             "owners": [{"emailAddress": "ops@acme.io"}], "size": "100"},
        ]

    def test_full_scan_pagination_and_start_token(self):
        items = [{"id": f"f{i}", "name": f"doc{i}.gdoc",
                  "mimeType": "application/vnd.google-apps.document",
                  "parents": [], "modifiedTime": "2026-01-01T00:00:00Z"}
                 for i in range(5)]
        svc = FakeDriveService(items, start_token="tok-A")
        src = GoogleDriveSource(service=svc, domain="acme.io")
        # shrink page size by faking pagination via items count + pageSize=1000
        snap = src.scan()
        self.assertEqual(len(snap.files), 5)
        self.assertEqual(snap.scan_metadata["drive_changes_token"], "tok-A")
        self.assertEqual(len(svc.files_calls), 1)

    def test_incremental_delta_and_merge(self):
        svc = FakeDriveService(
            self._base_items(),
            start_token="tok-1",
            changes={
                "tok-1": {
                    "changes": [
                        {"fileId": "f1", "removed": False,
                         "file": {"id": "f1", "name": "CO-001 register v2.csv",
                                  "mimeType": "text/csv", "parents": ["fld1"],
                                  "modifiedTime": "2026-03-01T00:00:00Z"}},
                        {"fileId": "f-new", "removed": False,
                         "file": {"id": "f-new", "name": "New Policy.md",
                                  "mimeType": "text/markdown", "parents": ["fld1"],
                                  "modifiedTime": "2026-03-02T00:00:00Z"}},
                        {"fileId": "f-dead", "removed": True},
                    ],
                    "newStartPageToken": "tok-2",
                }
            },
        )
        src = GoogleDriveSource(service=svc, domain="acme.io")
        base = src.scan()

        delta, new_token = src.scan_delta("tok-1")
        self.assertEqual(new_token, "tok-2")
        self.assertIn("f-dead", delta.scan_metadata["removed_ids"])

        merged = merge_delta(base, delta)
        names = {f.name for f in merged.files}
        self.assertIn("CO-001 register v2.csv", names)  # updated
        self.assertIn("New Policy.md", names)           # created
        self.assertNotIn("f-dead", {f.id for f in merged.files})  # removed
        # updated file keeps real parent path via merged folder map
        f1 = next(f for f in merged.files if f.id == "f1")
        self.assertEqual(f1.path, "/00_Company_Control/CO-001 register v2.csv")

    def test_retry_on_429_then_success(self):
        svc = FakeDriveService(self._base_items(), failures=[429, 403])
        sleeps = []
        src = GoogleDriveSource(service=svc, backoff_base=0, sleep=sleeps.append)
        snap = src.scan()
        self.assertEqual(len(snap.files), 1)
        # two injected failures -> two sleeps (backoff_base=0 makes it instant)
        self.assertEqual(len(sleeps), 2)

    def test_retry_exhaustion_raises(self):
        svc = FakeDriveService(self._base_items(), failures=[429, 429, 429, 429, 429, 429])
        src = GoogleDriveSource(service=svc, backoff_base=0, sleep=lambda s: None)
        with self.assertRaises(_FakeHttpError):
            src.scan()




if __name__ == "__main__":
    unittest.main()
