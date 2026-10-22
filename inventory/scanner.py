#!/usr/bin/env python3
"""
Company OS — Workspace Inventory Scanner (v0.1)
Read-only metadata scanner for Google Workspace / Local Drive.
Inventories file names, folder structures, modification dates, and owners
without reading sensitive document bodies unnecessarily.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class WorkspaceFile:
    id: str
    name: str
    mime_type: str
    parent_id: Optional[str]
    path: str
    created_time: str
    modified_time: str
    owners: List[str]
    size_bytes: int


@dataclass
class WorkspaceFolder:
    id: str
    name: str
    parent: Optional[str]
    path: str


@dataclass
class InventorySnapshot:
    scan_metadata: Dict[str, Any]
    folders: List[WorkspaceFolder]
    files: List[WorkspaceFile]


class WorkspaceScanner:
    """Scanner capable of indexing local simulated drives or loading existing snapshots."""

    def load_snapshot(self, snapshot_path: Path) -> InventorySnapshot:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        folders = [
            WorkspaceFolder(
                id=f.get("id", ""),
                name=f.get("name", ""),
                parent=f.get("parent"),
                path=f.get("path", ""),
            )
            for f in data.get("folders", [])
        ]

        files = [
            WorkspaceFile(
                id=f.get("id", ""),
                name=f.get("name", ""),
                mime_type=f.get("mime_type", "application/octet-stream"),
                parent_id=f.get("parent_id"),
                path=f.get("path", ""),
                created_time=f.get("created_time", ""),
                modified_time=f.get("modified_time", ""),
                owners=f.get("owners", []),
                size_bytes=f.get("size_bytes", 0),
            )
            for f in data.get("files", [])
        ]

        metadata = data.get("scan_metadata", {})
        metadata["total_files"] = len(files)
        metadata["total_folders"] = len(folders)

        return InventorySnapshot(
            scan_metadata=metadata,
            folders=folders,
            files=files,
        )

    def scan_local_directory(self, root_dir: Path, domain: str = "local") -> InventorySnapshot:
        """Scan a local directory tree simulating a Google Drive."""
        root_path = root_dir.resolve()
        folders: List[WorkspaceFolder] = []
        files: List[WorkspaceFile] = []

        folder_id_map: Dict[str, str] = {str(root_path): "fld-root"}
        folders.append(
            WorkspaceFolder(
                id="fld-root",
                name=root_path.name or "Root",
                parent=None,
                path="/",
            )
        )

        counter = 1
        for current_root, dirnames, filenames in os.walk(root_path):
            current_path = Path(current_root)
            curr_fld_id = folder_id_map.get(str(current_path), "fld-unknown")

            # Map subdirectories
            for d in dirnames:
                dir_full = current_path / d
                rel_path = "/" + str(dir_full.relative_to(root_path))
                fld_id = f"fld-{counter:03d}"
                counter += 1
                folder_id_map[str(dir_full)] = fld_id
                folders.append(
                    WorkspaceFolder(
                        id=fld_id,
                        name=d,
                        parent=curr_fld_id,
                        path=rel_path,
                    )
                )

            # Map files
            for f in filenames:
                if f.startswith("."):
                    continue
                file_full = current_path / f
                rel_path = "/" + str(file_full.relative_to(root_path))
                stat = file_full.stat()
                c_time = datetime.datetime.fromtimestamp(stat.st_ctime, tz=datetime.timezone.utc).isoformat()
                m_time = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).isoformat()

                files.append(
                    WorkspaceFile(
                        id=f"file-{len(files)+1:03d}",
                        name=f,
                        mime_type=self._guess_mime(f),
                        parent_id=curr_fld_id,
                        path=rel_path,
                        created_time=c_time,
                        modified_time=m_time,
                        owners=[f"owner@{domain}"],
                        size_bytes=stat.st_size,
                    )
                )

        metadata = {
            "scanned_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "domain": domain,
            "platform": "local_simulated_drive",
            "root_path": str(root_path),
            "total_files": len(files),
            "total_folders": len(folders),
        }

        return InventorySnapshot(
            scan_metadata=metadata,
            folders=folders,
            files=files,
        )

    def _guess_mime(self, filename: str) -> str:
        fn = filename.lower()
        if fn.endswith((".gdoc", ".docx", ".doc")):
            return "application/vnd.google-apps.document"
        if fn.endswith((".gsheet", ".xlsx", ".csv")):
            return "application/vnd.google-apps.spreadsheet"
        if fn.endswith((".gslides", ".pptx", ".ppt")):
            return "application/vnd.google-apps.presentation"
        if fn.endswith(".pdf"):
            return "application/pdf"
        if fn.endswith(".json"):
            return "application/json"
        if fn.endswith((".yaml", ".yml")):
            return "application/x-yaml"
        return "application/octet-stream"


def main():
    parser = argparse.ArgumentParser(description="Company OS Workspace Inventory Scanner")
    parser.add_argument("--snapshot", help="Path to existing JSON inventory snapshot")
    parser.add_argument("--local", help="Path to local folder simulating drive to index")
    parser.add_argument("--output", help="Optional output JSON path")

    args = parser.parse_args()

    scanner = WorkspaceScanner()
    if args.snapshot:
        snap_path = Path(args.snapshot)
        if not snap_path.exists():
            sys.stderr.write(f"Snapshot not found: {snap_path}\n")
            sys.exit(1)
        snapshot = scanner.load_snapshot(snap_path)
    elif args.local:
        loc_path = Path(args.local)
        if not loc_path.exists():
            sys.stderr.write(f"Directory not found: {loc_path}\n")
            sys.exit(1)
        snapshot = scanner.scan_local_directory(loc_path)
    else:
        # Default to sample snapshot
        default_snap = Path(__file__).resolve().parent.parent / "examples" / "sample-drive-inventory.json"
        snapshot = scanner.load_snapshot(default_snap)

    data = asdict(snapshot)
    formatted = json.dumps(data, indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(formatted)
        print(f"Inventory saved to {out_path} ({len(snapshot.files)} files, {len(snapshot.folders)} folders)")
    else:
        print(f"Scanned {len(snapshot.files)} files and {len(snapshot.folders)} folders.")
        for f in snapshot.files[:5]:
            print(f"  - [{f.id}] {f.name} ({f.path}) - Modified: {f.modified_time}")
        if len(snapshot.files) > 5:
            print(f"  ... and {len(snapshot.files) - 5} more.")


if __name__ == "__main__":
    main()
