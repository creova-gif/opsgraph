#!/usr/bin/env python3
"""
Company OS — Google Drive Inventory Source (v0.1)
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
from pathlib import Path
from typing import Any, Dict, List, Optional

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


class GoogleDriveSource:
    """`WorkspaceSource` backed by the Drive v3 files.list API."""

    def __init__(
        self,
        credentials_path: Path,
        token_path: Optional[Path] = None,
        impersonate: Optional[str] = None,
        domain: str = "workspace",
    ):
        if not _GOOGLE_AVAILABLE:
            raise RuntimeError(
                "Google API libraries not installed. Run: pip install -e '.[drive]'"
            )
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path) if token_path else None
        self.impersonate = impersonate
        self.domain = domain

    def scan(self) -> InventorySnapshot:
        service = build("drive", "v3", credentials=self._credentials())
        items = self._list_all(service)
        return snapshot_from_drive_items(items, domain=self.domain)

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
            resp = (
                service.files()
                .list(
                    q="trashed = false",
                    fields=_FIELDS,
                    pageSize=1000,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            items.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                return items


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
