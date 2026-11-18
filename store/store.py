#!/usr/bin/env python3
"""
OpsGraph — Local Persistence Store (SQLite, WAL)
Single-tenant local persistence for versioned company profiles and, later,
scans / gap reports / compile runs. Stdlib sqlite3 only — no ORM, no deps.
Profiles are validated against schema/company-profile.schema.json on save
and immutable once written (each save creates a new version).
"""

from __future__ import annotations

import datetime
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from store.validate import validate

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "company-profile.schema.json"
DEFAULT_DB_PATH = Path(".opsgraph") / "opsgraph.db"

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    company_id TEXT PRIMARY KEY,
    legal_name TEXT NOT NULL,
    domain TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_versions (
    company_id TEXT NOT NULL REFERENCES companies(company_id),
    version INTEGER NOT NULL,
    payload TEXT NOT NULL,
    schema_id TEXT,
    saved_at TEXT NOT NULL,
    PRIMARY KEY (company_id, version)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(company_id),
    run_type TEXT NOT NULL,
    summary TEXT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_company ON runs(company_id, run_type, created_at);
"""

RUN_TYPES = {"scan", "resolve", "gap", "compile", "guardian"}


def company_id_for(profile: Dict[str, Any]) -> str:
    """Stable company key: workspace domain when present, else slugged legal name."""
    domain = (profile.get("workspace") or {}).get("domain")
    if domain:
        return re.sub(r"[^a-z0-9]+", "-", domain.lower()).strip("-")
    name = (profile.get("company") or {}).get("legal_name") or "unnamed"
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "unnamed"


class ProfileStore:
    """Versioned, schema-validated company profile persistence."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH, schema_path: Path = SCHEMA_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.executescript(_SCHEMA)

    def save_profile(self, profile: Dict[str, Any]) -> tuple:
        """Validate and persist a new profile version. Returns (company_id, version)."""
        errors = validate(profile, self.schema)
        if errors:
            raise ValueError("Profile failed schema validation: " + "; ".join(errors))

        company_id = company_id_for(profile)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        legal_name = (profile.get("company") or {}).get("legal_name", "")
        domain = (profile.get("workspace") or {}).get("domain")

        with self.conn:
            self.conn.execute(
                "INSERT INTO companies (company_id, legal_name, domain, created_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(company_id) DO UPDATE SET legal_name=excluded.legal_name, domain=excluded.domain",
                (company_id, legal_name, domain, now),
            )
            next_version = (
                self.conn.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 FROM profile_versions WHERE company_id = ?",
                    (company_id,),
                ).fetchone()[0]
            )
            self.conn.execute(
                "INSERT INTO profile_versions (company_id, version, payload, schema_id, saved_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (company_id, next_version, json.dumps(profile, sort_keys=True), self.schema.get("$id"), now),
            )
        return company_id, next_version

    def get_profile(self, company_id: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        if version is None:
            row = self.conn.execute(
                "SELECT payload FROM profile_versions WHERE company_id = ? ORDER BY version DESC LIMIT 1",
                (company_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT payload FROM profile_versions WHERE company_id = ? AND version = ?",
                (company_id, version),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list_companies(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT c.company_id, c.legal_name, c.domain, c.created_at, MAX(v.version) "
            "FROM companies c JOIN profile_versions v ON v.company_id = c.company_id "
            "GROUP BY c.company_id ORDER BY c.company_id"
        ).fetchall()
        return [
            {"company_id": r[0], "legal_name": r[1], "domain": r[2], "created_at": r[3], "latest_version": r[4]}
            for r in rows
        ]

    def list_versions(self, company_id: str) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT version, saved_at, schema_id FROM profile_versions WHERE company_id = ? ORDER BY version",
            (company_id,),
        ).fetchall()
        return [{"version": r[0], "saved_at": r[1], "schema_id": r[2]} for r in rows]

    def save_run(
        self,
        company_id: str,
        run_type: str,
        payload: Dict[str, Any],
        summary: str = "",
    ) -> int:
        """Persist an engine run (scan/gap/compile/guardian) for a company.

        The company must already exist — runs always hang off a versioned
        profile so history is anchored to a known entity.
        """
        if run_type not in RUN_TYPES:
            raise ValueError(f"unknown run_type '{run_type}' (expected one of {sorted(RUN_TYPES)})")
        exists = self.conn.execute(
            "SELECT 1 FROM companies WHERE company_id = ?", (company_id,)
        ).fetchone()
        if not exists:
            raise ValueError(f"no company '{company_id}' in store — save a profile first")
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO runs (company_id, run_type, summary, payload, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    company_id,
                    run_type,
                    summary,
                    json.dumps(payload, sort_keys=True, default=str),
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                ),
            )
        return cur.lastrowid

    def list_runs(
        self,
        company_id: Optional[str] = None,
        run_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        q = "SELECT id, company_id, run_type, summary, created_at FROM runs"
        clauses, params = [], []
        if company_id:
            clauses.append("company_id = ?")
            params.append(company_id)
        if run_type:
            clauses.append("run_type = ?")
            params.append(run_type)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(q, params).fetchall()
        return [
            {"id": r[0], "company_id": r[1], "run_type": r[2], "summary": r[3], "created_at": r[4]}
            for r in rows
        ]

    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT id, company_id, run_type, summary, payload, created_at FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0], "company_id": row[1], "run_type": row[2],
            "summary": row[3], "payload": json.loads(row[4]), "created_at": row[5],
        }

    def close(self) -> None:
        self.conn.close()
