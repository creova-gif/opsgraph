# Security Policy

## Supported Versions

| Version | Supported |
| :--- | :---: |
| `0.2.x` | :white_check_mark: |
| `0.1.x` | :white_check_mark: |

## Reporting a Vulnerability

Please report security vulnerabilities privately by emailing **creativeinnovationspace@gmail.com** rather than opening a public GitHub issue.

Include:
1. A description of the vulnerability and the affected component (`inventory/`, `compiler/`, `store/`, `guardian/`, or `integrations/`).
2. Minimal steps or a fixture-based command to reproduce the issue.
3. Any potential impact on workspace integrity or data exposure.

We aim to acknowledge reports within **48 hours** and provide a remediation plan or patch within **7 days**.

---

## Security & Trust Boundaries

OpsGraph is engineered with explicit, verifiable safety boundaries for operating against company shared drives and repositories:

### 1. Read-Only Metadata Scanning (`drive.metadata.readonly`)
- The Google Drive scanner (`inventory/drive_source.py`) requests only the **`https://www.googleapis.com/auth/drive.metadata.readonly`** OAuth scope by default.
- During inventory and gap analysis (`opsgraph scan`, `opsgraph gap`, `opsgraph guardian`), OpsGraph inspects file names, folder hierarchy, MIME types, modification timestamps, and ownership metadata — it **never downloads raw document contents** during inventory scans and never sends document bodies to external LLM providers.

### 2. Non-Destructive v1 Compiler Guarantee (No `delete`, `move`, or `overwrite`)
- The workspace compiler and Drive write adapter (`compiler/compiler.py`, `compiler/drive_apply.py`) are **create-only** by protocol construction.
- `DriveWriteBackend` exposes only two operations: `create_folder` and `create_file`. There are **no** `delete`, `trash`, `update`, `move`, or `rename` methods in the v1 write surface.
- Existing files or folders matching canonical targets are recorded as `skip` entries in the audit log and are never overwritten or modified.
- Every executed `opsgraph apply --record` persists a complete, deterministic reversal manifest (`new_id` values for all created objects) in the SQLite store (`docs/engineering/APPLY_REVERSIBILITY.md`).

### 3. Append-Only Approval Ledger Gate
- When `governance.require_compile_approval` is enabled on a company profile (default for `opsgraph init`) or `--require-approval` is passed, `opsgraph compile` and `opsgraph apply` refuse to materialize any artifact that does not have an explicit `approved` entry in the local SQLite approval ledger (`store/store.py`).

### 4. Local-First SQLite WAL State & Credential Hygiene
- Operational state (profiles, scan snapshots, gap runs, approval ledgers) is stored locally in SQLite with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and foreign-key enforcement (`PRAGMA foreign_keys=ON`).
- OAuth client secrets, service account JSON keys, and `OPSGRAPH_CONSUL_TOKEN` bearer tokens are read strictly from runtime paths or environment variables and must never be committed to version control.
