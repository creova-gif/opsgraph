#!/usr/bin/env python3
"""
OpsGraph — Google Drive Inventory Source (v0.1)
Read-only adapter that inventories Google Workspace Drive metadata
(file names, folder structure, owners, timestamps, sizes) into the
normalized InventorySnapshot consumed by every downstream engine.

Auth modes:
  * OAuth installed-app flow (interactive concierge onboarding):
        --credentials client_secret.json --token token.json
  * Service account (domain-wide delegation for Workspace admins):
        --credentials service_account.json [--impersonate admin@domain]

The adapter never reads file contents and never writes — v1 policy.
Requires the optional 'drive' extra: pip install -e '.[drive]'
"""

from __future__ import annotations

import datetime
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from inventory.scanner import InventorySnapshot, WorkspaceFile, WorkspaceFolder, WorkspaceSource

try:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False

# Read-only metadata scope — the minimum privilege that satisfies the
# inventory contract. Never request a broader scope without revisiting
# the "read-only, never delete" v1 policy in README.md.
SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]

_FOLDER_MIME = "application/vnd.google-apps.folder"
_FIELDS = (
    "nextPageToken, files(id, name, mimeType, parents, createdTime,"
    " modifiedTime, owners(emailAddress,displayName), size, trashed)"
)
_CHANGE_FIELDS = (
    "nextPageToken, newStartPageToken,"
    " changes(fileId, removed, file(id, name, mimeType, parents, createdTime,"
    " modifiedTime, owners(emailAddress,displayName), size, trashed))"
)
_RETRYABLE_STATUSES = {403, 429}


class GoogleDriveSource:
    """`WorkspaceSource` backed by the Drive v3 files.list API."""

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        token_path: Optional[Path] = None,
        impersonate: Optional[str] = None,
        domain: str = "workspace",
        service: Any = None,
        retry_attempts: int = 5,
        backoff_base: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        # `service` injects a pre-built Drive API client (or a fake for tests);
        # when absent, google libs are required and credentials are used.
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
        self.domain = domain
        self._service = service
        self.retry_attempts = retry_attempts
        self.backoff_base = backoff_base
        self._sleep = sleep

    def _service_client(self):
        if self._service is None:
            self._service = build("drive", "v3", credentials=self._credentials())
        return self._service

    def scan(self) -> InventorySnapshot:
        service = self._service_client()
        # Capture the changes start token *before* listing so modifications
        # that occur mid-scan are still caught by the next incremental scan.
        start_token = self.get_start_page_token(service)
        items = self._list_all(service)
        snapshot = snapshot_from_drive_items(items, domain=self.domain)
        if start_token:
            snapshot.scan_metadata["drive_changes_token"] = start_token
        return snapshot

    def scan_delta(self, start_page_token: str) -> Tuple[InventorySnapshot, Optional[str]]:
        """Incremental scan via changes.list. Returns (delta snapshot, new token).

        The delta contains only changed/created items; removed items are
        surfaced in scan_metadata['removed_ids']. Merge onto a prior snapshot
        with `merge_delta`.
        """
        service = self._service_client()
        changed: List[Dict[str, Any]] = []
        removed_ids: List[str] = []
        new_token: Optional[str] = None
        page_token: Optional[str] = start_page_token

        while page_token:
            resp = self._execute_with_retry(
                service.changes().list(
                    pageToken=page_token,
                    spaces="drive",
                    fields=_CHANGE_FIELDS,
                    pageSize=1000,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    includeRemovedFromAllDrives=True,
                )
            )
            for change in resp.get("changes", []):
                file_obj = change.get("file") or {}
                if change.get("removed") or file_obj.get("trashed"):
                    removed_ids.append(change.get("fileId") or file_obj.get("id", ""))
                elif file_obj:
                    changed.append(file_obj)
            page_token = resp.get("nextPageToken")
            if not page_token:
                new_token = resp.get("newStartPageToken")

        delta = snapshot_from_drive_items(changed, domain=self.domain)
        delta.scan_metadata["removed_ids"] = [r for r in removed_ids if r]
        delta.scan_metadata["delta"] = True
        return delta, new_token

    def get_start_page_token(self, service: Any = None) -> Optional[str]:
        service = service or self._service_client()
        resp = self._execute_with_retry(
            service.changes().getStartPageToken(supportsAllDrives=True)
        )
        return resp.get("startPageToken")

    # -- auth -----------------------------------------------------------------

    def _credentials(self):
        if self._is_service_account(self.credentials_path):
            creds = service_account.Credentials.from_service_account_file(
                str(self.credentials_path), scopes=SCOPES
            )
            return creds.with_subject(self.impersonate) if self.impersonate else creds
        return self._oauth_credentials()

    @staticmethod
    def _is_service_account(path: Path) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("type") == "service_account"
        except (OSError, json.JSONDecodeError):
            return False

    def _oauth_credentials(self):
        creds = None
        if self.token_path and self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        if self.token_path:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    # -- listing ---------------------------------------------------------------

    def _list_all(self, service) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        page_token = None
        while True:
            resp = self._execute_with_retry(
                service.files().list(
                    q="trashed = false",
                    fields=_FIELDS,
                    pageSize=1000,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
            )
            items.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                return items

    def _execute_with_retry(self, request) -> Dict[str, Any]:
        """Execute an API request with exponential backoff on 403/429.

        Duck-typed on the googleapiclient HttpRequest interface so fake
        services can exercise the same path in tests.
        """
        last_err: Optional[BaseException] = None
        for attempt in range(self.retry_attempts):
            try:
                return request.execute()
            except Exception as err:  # googleapiclient.errors.HttpError
                status = getattr(getattr(err, "resp", None), "status", None)
                if status is None:
                    status = getattr(err, "status_code", None)
                if status not in _RETRYABLE_STATUSES or attempt == self.retry_attempts - 1:
                    raise
                last_err = err
                self._sleep(self.backoff_base * (2 ** attempt))
        raise last_err  # unreachable; keeps type-checkers honest


def snapshot_from_drive_items(
    items: List[Dict[str, Any]],
    domain: str = "workspace",
    scanned_at: Optional[str] = None,
) -> InventorySnapshot:
    """Map Drive files.list payloads to the normalized InventorySnapshot.

    Pure function — takes raw API dicts so it can be unit-tested without
    network or credentials.
    """
    folders: List[WorkspaceFolder] = []
    files: List[WorkspaceFile] = []
    folder_by_id: Dict[str, Dict[str, Any]] = {}

    for it in items:
        if it.get("mimeType") == _FOLDER_MIME:
            folder_by_id[it["id"]] = it

    def _folder_path(folder_id: Optional[str], depth: int = 0) -> str:
        if not folder_id or folder_id not in folder_by_id or depth > 32:
            return "/"
        folder = folder_by_id[folder_id]
        parents = folder.get("parents") or []
        parent_path = _folder_path(parents[0] if parents else None, depth + 1)
        return f"{parent_path.rstrip('/')}/{folder.get('name', '')}"

    for it in items:
        parents = it.get("parents") or []
        parent_id = parents[0] if parents else None
        if it.get("mimeType") == _FOLDER_MIME:
            folders.append(
                WorkspaceFolder(
                    id=it["id"],
                    name=it.get("name", ""),
                    parent=parent_id,
                    path=_folder_path(it["id"]),
                )
            )
        else:
            owners = [
                o.get("emailAddress") or o.get("displayName", "")
                for o in it.get("owners", [])
            ]
            files.append(
                WorkspaceFile(
                    id=it["id"],
                    name=it.get("name", ""),
                    mime_type=it.get("mimeType", "application/octet-stream"),
                    parent_id=parent_id,
                    path=f"{_folder_path(parent_id).rstrip('/')}/{it.get('name', '')}",
                    created_time=it.get("createdTime", ""),
                    modified_time=it.get("modifiedTime", ""),
                    owners=[o for o in owners if o],
                    size_bytes=int(it.get("size", 0) or 0),
                )
            )

    return InventorySnapshot(
        scan_metadata={
            "scanned_at": scanned_at
            or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "domain": domain,
            "platform": "google_drive",
            "total_files": len(files),
            "total_folders": len(folders),
        },
        folders=folders,
        files=files,
    )


def merge_delta(base: InventorySnapshot, delta: InventorySnapshot) -> InventorySnapshot:
    """Apply a changes.list delta onto a prior snapshot.

    Upserts changed files/folders by id and drops ids the delta reports as
    removed. `base` is left unmodified; the merged snapshot carries the
    delta's metadata (freshest scan time/token).
    """
    removed = set(delta.scan_metadata.get("removed_ids", []))
    changed_files = {f.id: f for f in delta.files}
    changed_folders = {f.id: f for f in delta.folders}

    files = [
        changed_files.get(f.id, f)
        for f in base.files
        if f.id not in removed
    ]
    folders = [
        changed_folders.get(f.id, f)
        for f in base.folders
        if f.id not in removed
    ]
    seen_files = {f.id for f in files}
    seen_folders = {f.id for f in folders}
    files.extend(f for f in delta.files if f.id not in seen_files)
    folders.extend(f for f in delta.folders if f.id not in seen_folders)

    # Delta items resolve paths only against other changed folders; re-resolve
    # every changed item's path against the *merged* folder map so a file
    # whose parent was untouched still lands under its real tree.
    folder_by_id = {f.id: f for f in folders}

    def _resolve_path(folder_id: Optional[str], depth: int = 0) -> str:
        if not folder_id or folder_id not in folder_by_id or depth > 32:
            return "/"
        folder = folder_by_id[folder_id]
        parent = _resolve_path(folder.parent, depth + 1)
        return f"{parent.rstrip('/')}/{folder.name}"

    for folder in folders:
        if folder.id in changed_folders:
            folder.path = _resolve_path(folder.id)
    for file in files:
        if file.id in changed_files:
            file.path = f"{_resolve_path(file.parent_id).rstrip('/')}/{file.name}"

    metadata = dict(delta.scan_metadata)
    metadata["total_files"] = len(files)
    metadata["total_folders"] = len(folders)
    metadata["merged_from_delta"] = True
    return InventorySnapshot(scan_metadata=metadata, folders=folders, files=files)
