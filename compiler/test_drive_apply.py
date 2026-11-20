#!/usr/bin/env python3
"""
Unit tests for the Drive write adapter: plan_apply diffing, execute_apply
ordering/audit, idempotent re-plans, and the real GoogleDriveWriter request
path exercised against a fake Drive service (incl. 429 retry).
"""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from compiler.compiler import CompilationPlan
from compiler.drive_apply import (
    DriveTrashBackend,
    DriveWriteBackend,
    GoogleDriveWriter,
    MemoryDriveTrasher,
    MemoryDriveWriter,
    execute_apply,
    execute_reverse,
    plan_apply,
    plan_reverse,
)
from inventory.scanner import InventorySnapshot, WorkspaceFile, WorkspaceFolder


def _folder(fid, name, parent):
    return WorkspaceFolder(id=fid, name=name, parent=parent, path=f"/{name}")


def _file(fid, name, parent_id):
    return WorkspaceFile(
        id=fid, name=name, mime_type="text/markdown", parent_id=parent_id,
        path=f"/{name}", created_time="2026-01-01T00:00:00Z",
        modified_time="2026-01-01T00:00:00Z", owners=[], size_bytes=10,
    )


def _snapshot(folders=None, files=None):
    return InventorySnapshot(
        scan_metadata={"scanned_at": "2026-11-01T00:00:00Z", "platform": "google_drive"},
        folders=folders or [],
        files=files or [],
    )


def _plan():
    return CompilationPlan(
        company_name="Acme Cloud Inc",
        target_directory="drive:root",
        dry_run=True,
        folders_to_create=["00_Company_Control", "01_Governance", "99_Archive"],
        artifacts_to_compile=[
            {"id": "CO-002", "filename": "CO-002_ownership.md", "root_folder": "00_Company_Control"},
            {"id": "CO-011", "filename": "CO-011_board_deck.md", "root_folder": "01_Governance"},
        ],
        skipped_existing=[],
        total_actions=6,
    )


def _content(spec):
    return f"# {spec['item']['id']} template body"


class TestPlanApply(unittest.TestCase):
    def test_empty_drive_creates_everything(self):
        ap = plan_apply(_plan(), _snapshot())
        self.assertEqual(ap.folders_to_create, ["00_Company_Control", "01_Governance", "99_Archive"])
        self.assertEqual(len(ap.files_to_create), 2)
        self.assertEqual(ap.skipped, [])
        self.assertEqual(ap.total_actions, 5)

    def test_existing_root_and_artifact_skipped(self):
        snap = _snapshot(
            folders=[_folder("rootfld", "My Drive", None),
                     _folder("fld1", "00_Company_Control", "rootfld")],
            files=[_file("f1", "CO-002_ownership_v3.md", "fld1")],
        )
        ap = plan_apply(_plan(), snap)
        self.assertEqual(ap.folders_to_create, ["01_Governance", "99_Archive"])
        self.assertEqual([s["artifact_id"] for s in ap.skipped if s["kind"] == "file"], ["CO-002"])
        # CO-011's folder doesn't exist yet, so it is still planned
        self.assertEqual([s["artifact_id"] for s in ap.files_to_create], ["CO-011"])

    def test_co001_register_stays_local(self):
        plan = _plan()
        plan.artifacts_to_compile.append(
            {"id": "CO-001", "filename": "CO-001_Master_Document_Register.md",
             "root_folder": "00_Company_Control"}
        )
        ap = plan_apply(plan, _snapshot())
        self.assertEqual(len(ap.files_to_create), 2)  # CO-001 not planned for Drive
        self.assertEqual(
            [s["artifact_id"] for s in ap.skipped if s["kind"] == "file"], ["CO-001"]
        )

    def test_register_upload_planned_when_enabled(self):
        plan = _plan()
        plan.artifacts_to_compile.append(
            {"id": "CO-001", "filename": "CO-001_Master_Document_Register.md",
             "root_folder": "00_Company_Control"}
        )
        ap = plan_apply(plan, _snapshot(), include_register=True)
        reg = [s for s in ap.files_to_create if s["artifact_id"] == "CO-001"]
        self.assertEqual(
            {(s["content_key"], s["mime_type"]) for s in reg},
            {("register_csv", "text/csv"), ("register_json", "application/json")},
        )
        self.assertTrue(all(s["root_folder"] == "00_Company_Control" for s in reg))

    def test_existing_register_never_overwritten(self):
        plan = _plan()
        plan.artifacts_to_compile.append(
            {"id": "CO-001", "filename": "CO-001_Master_Document_Register.md",
             "root_folder": "00_Company_Control"}
        )
        snap = _snapshot(
            folders=[_folder("rootfld", "My Drive", None),
                     _folder("fld1", "00_Company_Control", "rootfld")],
            files=[_file("reg1", "CO-001_Master_Document_Register.csv", "fld1")],
        )
        ap = plan_apply(plan, snap, include_register=True)
        reg_skips = [s for s in ap.skipped if s["artifact_id"] == "CO-001"]
        self.assertEqual(len(reg_skips), 1)
        self.assertIn("never overwrites", reg_skips[0]["reason"])
        self.assertFalse(any(s["artifact_id"] == "CO-001" for s in ap.files_to_create))

    def test_nested_same_name_folder_does_not_count(self):
        # 00_Company_Control nested under another folder is not top-level
        snap = _snapshot(
            folders=[_folder("rootfld", "My Drive", None),
                     _folder("misc", "misc", "rootfld"),
                     _folder("deep", "00_Company_Control", "misc")],
        )
        ap = plan_apply(_plan(), snap)
        self.assertIn("00_Company_Control", ap.folders_to_create)


class TestExecuteApply(unittest.TestCase):
    def test_creates_in_order_and_audits(self):
        ap = plan_apply(_plan(), _snapshot(folders=[_folder("rootfld", "My Drive", None)]))
        backend = MemoryDriveWriter()
        result = execute_apply(ap, backend, _content, approver="Justin")

        self.assertEqual(result.folders_created, ap.folders_to_create)
        self.assertEqual(len(result.files_created), 2)
        self.assertEqual(result.approver, "Justin")

        kinds = [a["action"] for a in result.audit_log]
        self.assertEqual(kinds.count("create_folder"), 3)
        self.assertEqual(kinds.count("create_file"), 2)

        # files land inside their root folder's new Drive ID
        fld_ids = {c["name"]: c["id"] for c in backend.created if c["kind"] == "folder"}
        for spec, created in zip(ap.files_to_create,
                                 [c for c in backend.created if c["kind"] == "file"]):
            self.assertEqual(created["parent_id"], fld_ids[spec["root_folder"]])
            self.assertIn(spec["artifact_id"], created["content"])

    def test_idempotent_second_apply(self):
        snap = _snapshot(folders=[_folder("rootfld", "My Drive", None)])
        backend = MemoryDriveWriter()
        execute_apply(plan_apply(_plan(), snap), backend, _content, approver="Justin")

        # Rebuild the observed state after the first apply
        new_folders = [_folder("rootfld", "My Drive", None)]
        new_files = []
        for c in backend.created:
            if c["kind"] == "folder":
                new_folders.append(_folder(c["id"], c["name"], "rootfld"))
            else:
                new_files.append(_file(c["id"], c["name"], c["parent_id"]))
        snap2 = _snapshot(folders=new_folders, files=new_files)

        ap2 = plan_apply(_plan(), snap2)
        self.assertEqual(ap2.total_actions, 0)
        self.assertEqual(len(ap2.skipped), 5)

    def test_backend_has_no_destructive_surface(self):
        backend = MemoryDriveWriter()
        self.assertIsInstance(backend, DriveWriteBackend)
        for attr in ("delete", "remove", "move", "rename", "update", "trash"):
            self.assertFalse(hasattr(backend, attr), f"backend unexpectedly exposes {attr}")


class _FakeRequest:
    def __init__(self, fn):
        self._fn = fn

    def execute(self):
        return self._fn()


class _FakeHttpError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.resp = type("Resp", (), {"status": status})()


class _FakeWriteFilesApi:
    def __init__(self, service):
        self._svc = service

    def create(self, **kwargs):
        return _FakeRequest(lambda: self._svc._files_create(kwargs))


class FakeWriteService:
    """Minimal files.create stub recording bodies and injecting failures."""

    def __init__(self, failures=None):
        self.failures = list(failures or [])
        self.create_calls = []
        self._counter = 0

    def files(self):
        return _FakeWriteFilesApi(self)

    def _files_create(self, params):
        self.create_calls.append(params)
        if self.failures:
            raise _FakeHttpError(self.failures.pop(0))
        self._counter += 1
        return {"id": f"new-{self._counter}"}


class TestGoogleDriveWriter(unittest.TestCase):
    def test_create_folder_and_file_requests(self):
        svc = FakeWriteService()
        writer = GoogleDriveWriter(service=svc)
        fid = writer.create_folder("00_Company_Control", "root")
        self.assertEqual(fid, "new-1")
        body = svc.create_calls[0]["body"]
        self.assertEqual(body["mimeType"], "application/vnd.google-apps.folder")
        self.assertEqual(body["parents"], ["root"])

        # writer used without google libs still needs media upload for files;
        # injected fake service path only requires the request object, but
        # create_file builds a MediaInMemoryUpload — skip if libs missing.
        try:
            doc_id = writer.create_file("CO-002.md", fid, "# body", "text/markdown")
        except NameError:
            self.skipTest("googleapiclient not installed")
        self.assertEqual(doc_id, "new-2")
        fbody = svc.create_calls[1]["body"]
        self.assertEqual(fbody["mimeType"], "text/markdown")

    def test_retry_on_429_then_success(self):
        svc = FakeWriteService(failures=[429])
        sleeps = []
        writer = GoogleDriveWriter(service=svc, backoff_base=0, sleep=sleeps.append)
        writer.create_folder("x", "root")
        self.assertEqual(len(sleeps), 1)
        self.assertEqual(len(svc.create_calls), 2)

    def test_create_only_even_when_asked(self):
        writer = GoogleDriveWriter(service=FakeWriteService())
        for attr in ("delete", "trash", "update", "copy"):
            self.assertFalse(hasattr(writer, attr))


def _apply_run(audit_log, run_id=7, company_id="acme-io"):
    return {
        "id": run_id,
        "run_type": "apply",
        "company_id": company_id,
        "payload": {"company_name": "Acme", "audit_log": audit_log},
    }


class TestPlanReverse(unittest.TestCase):
    def test_extracts_create_ids_files_then_folders(self):
        run = _apply_run([
            {"action": "create_folder", "name": "00_Admin", "new_id": "fld-1"},
            {"action": "create_file", "name": "HR-014_Offer.md", "artifact_id": "HR-014", "new_id": "f-9"},
            {"action": "create_file", "name": "CO-001_Master_Document_Register.csv", "new_id": "f-10"},
            {"action": "skip", "name": "old.doc", "reason": "exists"},
        ])
        plan = plan_reverse(run)
        self.assertEqual(plan.run_id, 7)
        self.assertEqual(plan.company_name, "Acme")
        self.assertEqual([f["new_id"] for f in plan.files_to_trash], ["f-9", "f-10"])
        self.assertEqual([f["new_id"] for f in plan.folders_to_trash], ["fld-1"])
        self.assertEqual(plan.skipped_entries, 1)
        self.assertEqual(plan.total_actions, 3)

    def test_empty_audit_log_plans_nothing(self):
        plan = plan_reverse(_apply_run([]))
        self.assertEqual(plan.total_actions, 0)
        self.assertEqual(plan.files_to_trash, [])
        self.assertEqual(plan.folders_to_trash, [])

    def test_ignores_non_create_actions(self):
        plan = plan_reverse(_apply_run([
            {"action": "skip", "name": "x"},
            {"action": "note", "name": "y"},
        ]))
        self.assertEqual(plan.total_actions, 0)
        self.assertEqual(plan.skipped_entries, 1)


class TestExecuteReverse(unittest.TestCase):
    def _run(self):
        return _apply_run([
            {"action": "create_folder", "name": "00_Admin", "new_id": "fld-1"},
            {"action": "create_folder", "name": "20_People", "new_id": "fld-2"},
            {"action": "create_file", "name": "HR-014_Offer.md", "artifact_id": "HR-014", "new_id": "f-9"},
            {"action": "create_file", "name": "LG-007_NDA.md", "artifact_id": "LG-007", "new_id": "f-10"},
        ])

    def test_trashes_files_before_folders(self):
        plan = plan_reverse(self._run())
        trasher = MemoryDriveTrasher()
        result = execute_reverse(plan, trasher, approver="j.mafie")
        self.assertEqual(trasher.trashed, ["f-9", "f-10", "fld-1", "fld-2"])
        self.assertEqual(len(result.trashed), 4)
        self.assertEqual(result.failed, [])
        self.assertEqual(result.approver, "j.mafie")
        self.assertEqual(result.run_id, 7)

    def test_per_item_failure_does_not_halt_pass(self):
        plan = plan_reverse(self._run())
        trasher = MemoryDriveTrasher(fail_ids=["f-10"])
        result = execute_reverse(plan, trasher, approver="j.mafie")
        self.assertEqual(trasher.trashed, ["f-9", "fld-1", "fld-2"])
        self.assertEqual(len(result.trashed), 3)
        self.assertEqual(len(result.failed), 1)
        self.assertEqual(result.failed[0]["new_id"], "f-10")
        # audit log records both outcomes — the before/after trail
        self.assertEqual(len(result.audit_log), 4)
        results = {e["new_id"]: e["result"] for e in result.audit_log}
        self.assertEqual(results["f-10"], "failed")
        self.assertEqual(results["f-9"], "trashed")

    def test_trash_only_protocol(self):
        trasher = MemoryDriveTrasher()
        for attr in ("create_folder", "create_file", "delete", "update"):
            self.assertFalse(hasattr(trasher, attr))


if __name__ == "__main__":
    unittest.main()
