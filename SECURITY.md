# Security Policy

## Supported Versions

| Version | Supported | Python Runtime |
| :--- | :---: | :--- |
| `0.2.x` | Yes | Python `3.10` – `3.14` |
| `0.1.x` | Security fixes only | Python `3.10` – `3.14` |

## Reporting a Vulnerability

Please report suspected security vulnerabilities privately by emailing **creativeinnovationspace@gmail.com** rather than opening a public GitHub issue or pull request.

Include in your report:
1. **Affected subsystem:** (`inventory/`, `compiler/`, `store/`, `guardian/`, `qa/`, `certificate/`, `dashboard/`, or `integrations/`).
2. **Reproduction steps:** Minimal CLI command or fixture payload demonstrating the boundary violation.
3. **Impact assessment:** Potential impact on Google Workspace object integrity, approval-ledger bypass, credential handling, or provenance spoofing.

**Response Targets:**
- **Acknowledgement:** Within **48 hours** of receipt.
- **Triage & Remediation Plan:** Within **7 calendar days**, with coordinated disclosure once a verified fix lands on `main`.

---

## Security Architecture & Trust Boundaries

OpsGraph operates adjacent to sensitive company shared drives (legal agreements, board governance, HR policies, security evidence). Its architecture enforces four structural safety boundaries in code rather than relying on prompt instructions:

### 1. Split Least-Privilege Google OAuth Scopes (`drive.metadata.readonly` vs. `drive.file`)

OpsGraph **never** requests the monolithic `https://www.googleapis.com/auth/drive` read/write scope. Read discovery and write compilation are isolated across distinct adapters and OAuth scopes:

| Adapter | Module | OAuth Scope | Permitted Operations | Structurally Prohibited |
| :--- | :--- | :--- | :--- | :--- |
| **Inventory Scanner** | `inventory/drive_source.py` (`GoogleDriveSource`) | `https://www.googleapis.com/auth/drive.metadata.readonly` | List file/folder IDs, names, parent links, MIME types, timestamps, sizes, owner emails, and `changes.list` delta tokens | Downloading file bodies/content; creating, editing, moving, or deleting any Drive object |
| **Create-Only Writer** | `compiler/drive_apply.py` (`GoogleDriveWriter` / `DriveWriteBackend`) | `https://www.googleapis.com/auth/drive.file` | `create_folder` and `create_file` only; skips any canonical target that already exists (`action: "skip"`) | Blanket workspace-wide access (OAuth scope); overwriting, renaming, moving, or deleting files (adapter protocol) |
| **Scoped Reversal Adapter** | `compiler/drive_apply.py` (`GoogleDriveTrasher` / `DriveTrashBackend`) | `https://www.googleapis.com/auth/drive.file` | Trashes (`trashed=True`) only the exact `new_id` entries recorded in a prior `apply --record` manifest, gated by `--reverse <run_id> --execute --approver <name>` | Permanent `files.delete`; touching any Drive ID outside the recorded `apply` manifest |

**OAuth Scope vs. Adapter Enforcement:** At the Google API layer, `drive.file` avoids blanket workspace-wide access by limiting visibility to files/folders created by the app or explicitly opened/shared with that OAuth client by a user (for example via a file picker). OpsGraph adds two stricter code-level guarantees on top of `drive.file`: `GoogleDriveWriter` exposes no update/move/trash methods at all, and `GoogleDriveTrasher` only acts on the enumerated `new_id` values captured during `apply --record`.

### 2. Local SQLite WAL Persistence & Human-Approval Ledger (`store/store.py`)

- **Local-First State:** Operational state lives in a local SQLite database (`.opsgraph/opsgraph.db` by default, configurable via `--db`) initialized with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and relational integrity (`PRAGMA foreign_keys=ON`).
- **Immutable Profile & Run Lineage:** Company profiles are validated against `schema/company-profile.schema.json` before insertion into `profile_versions` (each save increments `version` rather than mutating prior records). Engine executions (`scan`, `resolve`, `gap`, `plan`, `compile`, `apply`, `reverse`, `guardian`, `ask`) append immutable audit rows to `runs`.
- **Append-Only Approval Gate:** Human review decisions (`approved` or `rejected`) are recorded in the append-only `approvals` table with `approver`, UTC `created_at` timestamp, and optional `note`. Profiles initialized via `opsgraph init` enable `governance.require_compile_approval = true` by default; `opsgraph compile --require-approval` and `opsgraph apply` refuse to materialize any artifact lacking an effective `approved` ledger state.

### 3. Deterministic vs. Simulation Provenance Boundaries (`qa/`, `integrations/`, `certificate/`)

OpsGraph enforces strict epistemic provenance so simulated or rule-based outputs can never masquerade as live model inference or formal audit certification:

- **Deterministic Q&A Provenance (`qa/answerer.py`):** Every `Answer` emitted by `opsgraph ask` sets `source = "deterministic"`, attaches explicit engine citations (`artifact_id`, `domain:...`, or `event:...`), and degrades to `confidence = "low"` when a question falls outside structured engine state.
- **Mandatory `simulation` Wire Contract (`integrations/consul.py`):** When `opsgraph guardian --propose --consul-url <url>` calls a `consul-core` v1 endpoint (`POST /v1/agent-runs`), `HTTPConsulClient` sends structured metadata events (never raw document bodies) authenticated via `Authorization: Bearer $OPSGRAPH_CONSUL_TOKEN`. If the HTTP response omits `simulation` or returns a non-boolean value (`not isinstance(data.get("simulation"), bool)`), `HTTPConsulClient` raises `ConsulUnavailable` rather than accepting unverified output. When no server is configured or reachable, `StubConsulClient` returns deterministic remediation templates explicitly tagged with `simulation=True` and `provider="simulation"`, rendered as `[simulation]` in CLI output. Neither client can mutate the workspace or bypass the approval ledger.
- **Measurement-Only Certificate (`certificate/generator.py`):** Generated readiness certificates include a verbatim attestation stating that OpsGraph certifies an empirical point-in-time measurement against `rules/core-artifacts.json` — never legal or regulatory compliance (SOC 2, ISO 27001, HIPAA, GDPR).

### 4. Credential Hygiene & Local Preview Server

- **Secrets Never Stored in SQLite or Git:** Google OAuth client secrets, cached OAuth tokens, Service Account JSON keys, and `OPSGRAPH_CONSUL_TOKEN` are read at runtime from local paths or process environment variables (`.env.example`). Store JSON credentials outside the repository or inside the gitignored `.secrets/` directory (in addition to `.secrets/`, `.gitignore` excludes `client_secret*.json`, `service_account*.json`, `token.json`, `token_*.json`, and `oauth_token_cache*.json`).
- **Loopback-Only Preview Binding:** `opsgraph serve` binds to `127.0.0.1` by default so interactive readiness dashboards are not exposed on shared network interfaces unless `--host` is explicitly overridden.

---

## Vulnerability Scope

| In Scope | Out of Scope |
| :--- | :--- |
| Bypass of `--require-approval` / `governance.require_compile_approval` gates in `compiler` or `apply` | Social engineering or physical access to an operator's local workstation |
| Unintended mutation, overwrite, or deletion of pre-existing workspace files | Misconfigured Google Cloud IAM / domain-wide delegation outside OpsGraph's documented scopes |
| Path traversal or arbitrary file write in `compiler`, `dashboard`, `certificate`, or `inventory` | Denial-of-service from intentionally malformed multi-gigabyte local JSON fixtures passed by a local CLI user |
| Missing/spoofed `simulation` or `source="deterministic"` provenance flags | Third-party vulnerabilities in upstream Google Cloud Python SDKs (report upstream; we track via Dependabot) |
| XSS / HTML injection via untrusted Drive file metadata rendered in `dashboard/` or `certificate/` | — |
