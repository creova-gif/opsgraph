#!/usr/bin/env python3
"""
OpsGraph — Google Drive Write Adapter (Phase 2)
Applies an approved CompilationPlan to a real Google Drive: canonical
taxonomy folders plus governed artifact documents.

Safety contract:
  * Create-only by design — the DriveWriteBackend protocol exposes no
    delete, move, rename, or update methods, so an apply can never
    destroy or relocate existing customer files.
  * Idempotent — folders and artifacts already present in the scanned
    snapshot are skipped, never duplicated.
  * Audited — every action records kind, target, parent, new Drive ID,
    approver, and timestamp into the run payload.
  * Approval-gated — the CLI only passes artifacts whose IDs appear in
    the effective approval ledger when governance requires it.

Requires the optional 'drive' extra: pip install -e '.[drive]'
"""

from __future__ import annotations

import datetime
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compiler.compiler import CompilationPlan
from inventory.drive_source import execute_with_retry, load_drive_credentials
from inventory.scanner import InventorySnapshot

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaInMemoryUpload

    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False

# Files-only write scope — least privilege for folder/doc creation.
# Never request the broad 'drive' scope without revisiting README policy.
WRITE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

_FOLDER_MIME = "application/vnd.google-apps.folder"
_ARTIFACT_MIME = "text/markdown"


@runtime_checkable
class DriveWriteBackend(Protocol):
    """Create-only write surface for a Drive-like store.

    Deliberately minimal: no read, delete, move, or update. Implementations
    return the new object's Drive ID.
    """

    def create_folder(self, name: str, parent_id: str) -> str:
        ...

    def create_file(self, name: str, parent_id: str, content: str, mime_type: str) -> str:
        ...


@dataclass
class ApplyPlan:
    company_name: str
    root_parent_id: str
    root_folder_ids: Dict[str, str]            # existing taxonomy root name -> Drive ID
    folders_to_create: List[str]
    files_to_create: List[Dict[str, Any]]      # {name, artifact_id, root_folder}
    skipped: List[Dict[str, str]]              # {kind, name, artifact_id, reason}
    total_actions: int


@dataclass
class ApplyResult:
    company_name: str
    executed_at: str
    approver: str
    folders_created: List[str]
    files_created: List[str]
    audit_log: List[Dict[str, Any]]


def plan_apply(
    plan: CompilationPlan,
    snapshot: InventorySnapshot,
    root_parent_id: str = "root",
) -> ApplyPlan:
    """Diff a CompilationPlan against the observed Drive state.

    A taxonomy root folder counts as existing only at Drive top level.
    An artifact counts as existing when a file named '<ID>_*' already
    lives in its canonical root folder — idempotent by register ID.
    """
    folder_map = {f.id: f for f in snapshot.folders}
    root_node = next((f for f in snapshot.folders if f.parent is None), None)

    existing_roots: Dict[str, str] = {}
    for f in snapshot.folders:
        if root_node is not None:
            if f.parent == root_node.id:
                existing_roots.setdefault(f.name, f.id)
        elif f.parent is None:
            existing_roots.setdefault(f.name, f.id)

    parent_name: Dict[str, str] = {f.id: f.name for f in snapshot.folders}

    folders_to_create: List[str] = []
    skipped: List[Dict[str, str]] = []

    for fld in plan.folders_to_create:
        if fld in existing_roots:
            skipped.append({
                "kind": "folder", "name": fld, "artifact_id": "",
                "reason": f"already exists at Drive root (id {existing_roots[fld]})",
            })
        else:
            folders_to_create.append(fld)

    files_to_create: List[Dict[str, Any]] = []
    for item in plan.artifacts_to_compile:
        art_id = item["id"]
        if art_id == "CO-001":
            # The Master Document Register is a CSV/JSON compile output, not a
            # markdown template — it stays a local compile artifact for now.
            skipped.append({
                "kind": "file", "name": item["filename"], "artifact_id": art_id,
                "reason": "register is produced by local compile; Drive upload deferred",
            })
            continue
        root_folder = item["root_folder"]
        folder_id = existing_roots.get(root_folder)
        if folder_id is not None:
            existing = next(
                (
                    f for f in snapshot.files
                    if f.parent_id == folder_id and f.name.startswith(f"{art_id}_")
                ),
                None,
            )
            if existing is not None:
                skipped.append({
                    "kind": "file", "name": existing.name, "artifact_id": art_id,
                    "reason": f"artifact {art_id} already present in {root_folder} (id {existing.id})",
                })
                continue
        files_to_create.append({
            "name": item["filename"],
            "artifact_id": art_id,
            "root_folder": root_folder,
            "item": item,
        })

    return ApplyPlan(
        company_name=plan.company_name,
        root_parent_id=root_parent_id,
        root_folder_ids=existing_roots,
        folders_to_create=folders_to_create,
        files_to_create=files_to_create,
        skipped=skipped,
        total_actions=len(folders_to_create) + len(files_to_create),
    )


def execute_apply(
    apply_plan: ApplyPlan,
    backend: DriveWriteBackend,
    content_fn: Callable[[Dict[str, Any]], str],
    approver: str,
    artifact_mime: str = _ARTIFACT_MIME,
) -> ApplyResult:
    """Execute an ApplyPlan through a create-only backend.

    Every create is recorded in the audit log alongside the skips
    computed at plan time — the before/after trail for the compile run.
    """
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    folder_ids = dict(apply_plan.root_folder_ids)
    audit: List[Dict[str, Any]] = []
    folders_created: List[str] = []
    files_created: List[str] = []

    for name in apply_plan.folders_to_create:
        new_id = backend.create_folder(name, apply_plan.root_parent_id)
        folder_ids[name] = new_id
        folders_created.append(name)
        audit.append({
            "action": "create_folder", "name": name,
            "parent_id": apply_plan.root_parent_id, "new_id": new_id,
        })

    for spec in apply_plan.files_to_create:
        parent_id = folder_ids[spec["root_folder"]]
        content = content_fn(spec["item"])
        new_id = backend.create_file(spec["name"], parent_id, content, artifact_mime)
        files_created.append(spec["name"])
        audit.append({
            "action": "create_file", "name": spec["name"],
            "artifact_id": spec["artifact_id"], "parent_id": parent_id,
            "new_id": new_id, "mime_type": artifact_mime,
        })

    for entry in apply_plan.skipped:
        audit.append({"action": "skip", **entry})

    return ApplyResult(
        company_name=apply_plan.company_name,
        executed_at=now_iso,
        approver=approver,
        folders_created=folders_created,
        files_created=files_created,
        audit_log=audit,
    )


class GoogleDriveWriter:
    """`DriveWriteBackend` backed by the Drive v3 files.create API."""

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        token_path: Optional[Path] = None,
        impersonate: Optional[str] = None,
        service: Any = None,
        retry_attempts: int = 5,
        backoff_base: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if service is None:
            if not _GOOGLE_AVAILABLE:
                raise RuntimeError(
                    "Google API libraries not installed. Run: pip install -e '.[drive]'"
                )
            if credentials_path is None:
                raise ValueError("credentials_path is required when no service is injected")
        self.credentials_path = Path(credentials_path) if credentials_path else None
        self.token_path = Path(token_path) if token_path else None
        self.impersonate = impersonate
        self._service = service
        self.retry_attempts = retry_attempts
        self.backoff_base = backoff_base
        self._sleep = sleep

    def _service_client(self):
        if self._service is None:
            self._service = build(
                "drive", "v3",
                credentials=load_drive_credentials(
                    self.credentials_path, self.token_path,
                    self.impersonate, WRITE_SCOPES,
                ),
            )
        return self._service

    def create_folder(self, name: str, parent_id: str) -> str:
        resp = execute_with_retry(
            self._service_client().files().create(
                body={
                    "name": name,
                    "mimeType": _FOLDER_MIME,
                    "parents": [parent_id],
                },
                fields="id",
                supportsAllDrives=True,
            ),
            self.retry_attempts, self.backoff_base, self._sleep,
        )
        return resp["id"]

    def create_file(self, name: str, parent_id: str, content: str, mime_type: str) -> str:
        media = MediaInMemoryUpload(
            content.encode("utf-8"), mimetype=mime_type, resumable=False
        )
        resp = execute_with_retry(
            self._service_client().files().create(
                body={
                    "name": name,
                    "mimeType": mime_type,
                    "parents": [parent_id],
                },
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            ),
            self.retry_attempts, self.backoff_base, self._sleep,
        )
        return resp["id"]


class MemoryDriveWriter:
    """In-memory `DriveWriteBackend` for tests, demos, and dry-run proof."""

    def __init__(self):
        self.created: List[Dict[str, Any]] = []
        self._counter = 0

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    def create_folder(self, name: str, parent_id: str) -> str:
        new_id = self._next_id("fld")
        self.created.append({"kind": "folder", "id": new_id, "name": name, "parent_id": parent_id})
        return new_id

    def create_file(self, name: str, parent_id: str, content: str, mime_type: str) -> str:
        new_id = self._next_id("file")
        self.created.append({
            "kind": "file", "id": new_id, "name": name,
            "parent_id": parent_id, "mime_type": mime_type, "content": content,
        })
        return new_id
