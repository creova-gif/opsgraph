# Changelog

All notable changes to **OpsGraph** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-22

### Added
- **Profile Onboarding (`opsgraph init`):** Generates schema-valid company profiles (`schema/company-profile.schema.json`) from CLI flags with unanswered fields tracked in `provenance.unanswered` (`onboarding/`).
- **Store-Backed Execution (`--company-id`):** Unified `--company-id` resolution across `gap`, `ask`, `plan`, `certificate`, `dashboard`, `guardian`, `compile`, `apply`, and `serve` (`store/`).
- **Deterministic Remediation Planner (`opsgraph plan`) & Scoped Apply (`--from-plan`):** Orders actionable gaps into `P0`–`P3` phases in topological resolver dependency order and allows scoping `apply` runs to recorded plan steps (`plan/`).
- **Readiness Certificate (`opsgraph certificate`):** Renders CALIBRATION-series HTML/PDF readiness certificates from verified engine output (`certificate/`).
- **Guardian Digest Delta (`opsgraph digest`):** Computes run-over-run drift deltas, severity escalations, and health-score movement (`guardian/digest.py`).
- **Ask Company Deterministic Floor (`opsgraph ask`):** Answers natural-language queries about readiness, missing/stale artifacts, blockers, owners, and drift with grounded engine citations (`qa/`).
- **Consul-Core v1 Integration Seam (`integrations/`):** Versioned HTTP client (`HTTPConsulClient`) with bearer auth (`OPSGRAPH_CONSUL_TOKEN`), idempotency keys, and deterministic local simulation fallback (`StubConsulClient`).
- **Governance & Architecture Baseline:** Added `SECURITY.md`, `.ai/project.yaml`, `.github/dependabot.yml`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `docs/adr/0001-sqlite-wal-and-non-destructive-compiler.md`.

### Changed
- **Packaging (`pyproject.toml`):** Made `opsgraph` wheel-installable with `rules/*.json` and `schema/*.json` bundled as package data.
- **CALIBRATION Design System:** Unified visual dashboard (`dashboard/`) and CLI output around the CALIBRATION typographic and color specification (`DESIGN.md`).

## [0.1.0] - 2026-11-18

### Added
- **Deterministic State Resolver (`resolver/`):** Evaluates company profiles against `rules/core-artifacts.json` (31 governed operational artifacts across `00_Admin` through `99_Archive`) to compute required state with topological ordering.
- **Read-Only Workspace Inventory Scanner (`inventory/`):** Supports local filesystem trees, JSON inventory snapshots, and live Google Drive scanning via `drive.metadata.readonly` with incremental `changes.list` page tokens.
- **Gap Analysis Engine (`gap_engine/`):** Computes required-vs-observed artifact diffs, domain scorecards, and a 0–100% Infrastructure Readiness Score.
- **Non-Destructive Workspace Compiler (`compiler/`):** Generates dry-run compilation plans, canonical folder taxonomies, versioned `CO-001` Master Document Registers (CSV + JSON), and governed markdown template stubs without delete or overwrite operations.
- **Company Guardian (`guardian/`):** Detects policy staleness, missing owners, unapproved drift, and duplicate artifact collisions.
- **SQLite WAL Store (`store/`):** Local persistence for versioned profiles, immutable engine run history, and an append-only artifact approval ledger.
