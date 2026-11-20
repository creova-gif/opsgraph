# OpsGraph

Turns a startup's existing Google Workspace into an AI-maintained company operating system.
Required state (what should exist) is compared with observed state (what exists), approved gaps are
compiled into the workspace, and a Guardian monitors drift.

**v1 scope:** Seed to Series A B2B tech startups (5-50 people) on Google Workspace, sold against an
urgent trigger (enterprise deal, fundraise, security/SOC 2 request, rapid hiring). Concierge first.

Core loop: `Company Profile -> Required State -> Workspace Inventory -> Gap Report -> Compile (approved) -> Guardian`

## Layout
- `evidence-room/` - YC application preparation evidence room (answers, metrics, demo, interviews)
- `resolver/` - deterministic state resolver engine (Python) + test suite
- `inventory/` - read-only workspace metadata scanner: local trees, JSON snapshots, and real Google Drive via `scan --drive` (read-only `drive.metadata.readonly` scope; optional `[drive]` extra; incremental scans via `--state` file + `changes.list` tokens)
- `store/` - SQLite (WAL) persistence: versioned, schema-validated profiles (`profile save|list|show`), engine-run history (`--record` + `history`), an approval decision ledger (`approve`/`approvals`), and a whole-loop summary (`status`)
- `gap_engine/` - required-vs-observed gap analysis engine & infrastructure scoring
- `compiler/` - workspace compiler: creates folder taxonomy, Master Register, and governed templates
- `guardian/` - company guardian: weekly drift monitoring, policy staleness, and health digest; `--propose` emits remediation proposals per drift event via consul-core
- `integrations/` - consul-core v1 client seam: HTTP client (bearer token, `OPSGRAPH_CONSUL_TOKEN`) + deterministic local simulation fallback
- `dashboard/` - interactive visual HTML dashboard & local preview server
- `docs/pilot/` - concierge pilot offer one-pager, 20-step delivery checklist, intake form
- `docs/strategy/` - viability brief, execution blueprint, YC playbook (source of truth for decisions)
- `docs/architecture/` - OpsGraph–Consul integration contract (`consul-core` v1 surface)
- `schema/company-profile.schema.json` - onboarding output (P0)
- `rules/core-artifacts.json` - Operating Graph node ruleset (JSON is the single canonical source), 31 governed artifacts + placement policy (v0.3)
- `examples/` - sample profiles & drive inventories for testing (Seed, Pre-seed, Series A)
- gstack is available as a user-level skill install; not vendored here

## Principles
Specific before broad - evidence before assertion - propose before destructive action - compile, don't
dump templates - never claim compliance. Delete is never allowed in v1.

## Backlog & Execution Status
- [x] **Resolver (P0):** Profile + rules -> required artifact list with reasons and topological order (`resolver/`)
- [x] **Drive Inventory (P1):** Read-only metadata scanner — real Google Drive API (OAuth installed-app or service account, `drive.metadata.readonly`), JSON snapshots & local trees (`inventory/`)
- [x] **Gap Analysis Engine (P1):** Required vs observed diff, domain scorecards, and 0-100% Infrastructure Score (`gap_engine/`)
- [x] **Workspace Compiler Prototype (P1):** Dry-run preview, folder taxonomy, versioned Master Register (register + row versions, provenance) and template stubs with provenance (`compiler/`)
- [x] **Company Guardian Prototype (P2):** Continuous drift detection, staleness alerts, duplicate collisions, and weekly Health Digest (`guardian/`)
- [x] **Persistent Store:** Versioned profiles, engine-run history (`--record`, `history`), and an append-only approval ledger — `approve`/`approvals` record decisions, `compile --require-approval` only compiles store-approved artifacts, automatic when the profile sets `governance.require_compile_approval` (`store/`)
- [x] **Interactive Visual Dashboard:** Standalone single-file HTML report in the CALIBRATION design system — readiness numeral with tolerance band, gap matrix, domain scorecards, and drift feed (`dashboard/`)
- [x] **Pilot Offer Kit:** 48-Hour offer one-pager, delivery checklist, intake form (`docs/pilot/`)
- [x] **Evidence Room:** 9-folder structure + draft YC application answers (`evidence-room/`)
