# ADR 0001: Zero-Dependency Python Core, SQLite WAL Persistence, and Non-Destructive v1 Compiler

- **Status:** Accepted
- **Date:** 2026-11-18
- **Owner:** Justin Mafie (`@creova-gif`)

---

## Context

OpsGraph inspects a startup's shared workspace (Google Drive or local directory snapshots), compares observed artifacts against a deterministic ruleset (`rules/core-artifacts.json`) conditioned on the company profile (`schema/company-profile.schema.json`), scores operational readiness, and compiles missing governance structures (folder taxonomy, `CO-001` Master Document Register, and governed template stubs) back into the workspace.

Target customers (Seed to Series A B2B startups undergoing SOC 2 readiness, enterprise procurement, or fundraising diligence) have two strict operational constraints:
1. **Zero Tolerance for Workspace Data Loss:** Founders and operations leads will not grant write access to an automation tool that could accidentally delete, move, or overwrite existing contracts, board minutes, or security policies in Google Drive.
2. **Auditability & Offline Determinism:** Every readiness score, gap classification, approval decision, and workspace write must be reproducible offline, inspectable in CI, and traceable without requiring an external cloud database or opaque SaaS runtime.

---

## Decision

We made three foundational architectural decisions for OpsGraph v1:

1. **Zero-Dependency Python Standard Library Core:**
   - The core engine (`resolver`, `inventory` snapshot/local scanner, `gap_engine`, `compiler`, `guardian`, `plan`, `qa`, `dashboard`, `certificate`, and `store`) uses only the Python 3.10+ standard library.
   - Google Drive API libraries (`google-api-python-client`, `google-auth`, `google-auth-oauthlib`) are isolated behind an optional extra (`pip install ".[drive]"`).

2. **Local SQLite Write-Ahead Logging (WAL) Graph & Audit Store (`store/store.py`):**
   - All stateful workflows (`profile save`, `scan --record`, `gap --record`, `approve`, `compile`, `apply --record`, `guardian --record`) persist to a single-file SQLite database configured with `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON`.
   - Engine runs and approval decisions are stored as append-only records with UTC ISO-8601 timestamps and JSON payloads.

3. **Create-Only, Non-Destructive Compiler Protocol (`compiler/compiler.py`, `compiler/drive_apply.py`):**
   - The v1 compiler and `DriveWriteBackend` implement strictly additive operations: `create_folder` and `create_file`.
   - `delete`, `trash`, `move`, `rename`, and in-place overwrite operations are prohibited at the protocol boundary.
   - Any target folder or file that already exists at its canonical path is skipped (`action: "skip"`) and never overwritten.
   - Every recorded `apply` persists the exact provider-assigned `new_id` for each created folder and file, forming a deterministic reversal manifest (`docs/engineering/APPLY_REVERSIBILITY.md`).

---

## Alternatives Considered

### Alternative 1: External Postgres + ORM (SQLAlchemy / Prisma) for State Persistence
- **Pros:** Multi-tenant cloud hosting out of the box; concurrent network writers.
- **Cons:** Requires Docker/Postgres provisioning before running a single CLI command; breaks zero-setup concierge pilots and air-gapped CI runs; adds heavy third-party dependency trees.

### Alternative 2: Full-Sync Reconciler (Bidirectional Create / Update / Move / Delete)
- **Pros:** Can automatically reorganize messy existing folders and delete duplicate files.
- **Cons:** High blast radius. A false-positive match or rule change could relocate or trash live legal/HR documents, creating an unacceptable trust barrier during customer onboarding.

### Alternative 3: LLM-Driven Gap Evaluation & Free-Form Prompt Compilation
- **Pros:** Flexible handling of unstructured documents without explicit rulesets.
- **Cons:** Non-deterministic scoring across runs, high token latency, inability to certify readiness calculations, and privacy risk from uploading sensitive workspace contents to external model APIs.

---

## Rationale

- **Immediate Verifiability:** Because the core engine requires zero third-party packages and uses SQLite in the standard library, any engineer or CI runner can clone the repository and execute the full loop (`init -> scan -> gap -> plan -> approve -> compile -> guardian -> certificate`) in seconds with zero network calls.
- **Structural Safety:** Restricting `DriveWriteBackend` to `create_folder` and `create_file` guarantees by construction that pre-existing workspace files cannot be destroyed or mutated.
- **Concurrency & Crash Resilience:** SQLite in WAL mode supports concurrent local readers (e.g., `opsgraph serve` dashboard preview alongside CLI queries) and atomic transaction commits for the approval ledger and run history.

---

## Consequences

### Positive
- **Deterministic CI & Fast Tests:** 127+ unit and integration tests run in under 2 seconds across Python 3.10–3.14 without external services or mocks leaking network state.
- **Trivial Reversibility:** Undoing an `opsgraph apply` requires only removing the enumerated `new_id` entries recorded in `opsgraph history --run-id <N>`.
- **Clear Security Posture:** Read paths require only `drive.metadata.readonly`; write paths are gated by explicit approval ledger checks (`--require-approval`).

### Negative / Trade-offs
- **Existing Messy Files Are Not Auto-Moved:** When OpsGraph detects a misplaced or duplicate file in Google Drive, it flags the drift in the Gap Report and Guardian Digest rather than moving or deleting the file automatically. Operators resolve relocations manually or via human-reviewed remediation plans.
- **Single-Node Store Scope:** The local SQLite store is designed for single-workspace concierge pilots and CLI/CI automation rather than high-write distributed multi-tenant SaaS hosting.

---

## Risks & Mitigations

| Risk | Mitigation |
| :--- | :--- |
| Duplicate placeholder creation if `apply` is run repeatedly | `compiler` and `drive_apply` check existing canonical names/paths before creation and emit `skip` audit entries when targets already exist. |
| Unapproved template compilation in regulated workspaces | `opsgraph init` enables `governance.require_compile_approval` by default, enforcing an explicit SQLite approval ledger check before compilation. |
| Schema drift between profile JSON and store records | `store/validate.py` validates every profile against `schema/company-profile.schema.json` before persisting to SQLite. |
