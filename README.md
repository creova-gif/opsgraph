# Company OS

Turns a startup's existing Google Workspace into an AI-maintained company operating system.
Required state (what should exist) is compared with observed state (what exists), approved gaps are
compiled into the workspace, and a Guardian monitors drift.

**v1 scope:** Seed to Series A B2B tech startups (5-50 people) on Google Workspace, sold against an
urgent trigger (enterprise deal, fundraise, security/SOC 2 request, rapid hiring). Concierge first.

Core loop: `Company Profile -> Required State -> Workspace Inventory -> Gap Report -> Compile (approved) -> Guardian`

## Layout
- `evidence-room/` - YC application preparation evidence room (answers, metrics, demo, interviews)
- `resolver/` - deterministic state resolver engine (Python) + test suite
- `inventory/` - read-only workspace metadata scanner: local trees, JSON snapshots, and real Google Drive via `scan --drive` (read-only `drive.metadata.readonly` scope; optional `[drive]` extra)
- `gap_engine/` - required-vs-observed gap analysis engine & infrastructure scoring
- `compiler/` - workspace compiler: creates folder taxonomy, Master Register, and governed templates
- `guardian/` - company guardian: weekly drift monitoring, policy staleness, and health digest
- `dashboard/` - interactive visual HTML dashboard & local preview server
- `docs/pilot/` - concierge pilot offer one-pager, 20-step delivery checklist, intake form
- `docs/strategy/` - viability brief, execution blueprint, YC playbook (source of truth for decisions)
- `schema/company-profile.schema.json` - onboarding output (P0)
- `rules/core-artifacts.yaml` / `.json` - Operating Graph node ruleset, 31 governed artifacts (v0.2)
- `examples/` - sample profiles & drive inventories for testing (Seed, Pre-seed, Series A)
- gstack is available as a user-level skill install; not vendored here

## Principles
Specific before broad - evidence before assertion - propose before destructive action - compile, don't
dump templates - never claim compliance. Delete is never allowed in v1.

## Backlog & Execution Status
- [x] **Resolver (P0):** Profile + rules -> required artifact list with reasons and topological order (`resolver/`)
- [x] **Drive Inventory (P1):** Read-only metadata scanner — real Google Drive API (OAuth installed-app or service account, `drive.metadata.readonly`), JSON snapshots & local trees (`inventory/`)
- [x] **Gap Analysis Engine (P1):** Required vs observed diff, domain scorecards, and 0-100% Infrastructure Score (`gap_engine/`)
- [x] **Workspace Compiler Prototype (P1):** Dry-run preview, folder taxonomy, Master Register sheet, and template stubs with provenance (`compiler/`)
- [x] **Company Guardian Prototype (P2):** Continuous drift detection, staleness alerts, duplicate collisions, and weekly Health Digest (`guardian/`)
- [x] **Interactive Visual Dashboard:** Standalone single-file HTML report with 0–100% dial, gap matrix, and drift feed (`dashboard/`)
- [x] **Pilot Offer Kit:** 48-Hour offer one-pager, delivery checklist, intake form (`docs/pilot/`)
- [x] **Evidence Room:** 9-folder structure + draft YC application answers (`evidence-room/`)
