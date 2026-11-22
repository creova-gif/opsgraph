# OpsGraph

[![CI](https://github.com/creova-gif/opsgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/creova-gif/opsgraph/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-0.2.0-informational)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.14-blue)

Turns a startup's existing Google Workspace into an AI-maintained company operating system.
Required state (what should exist) is compared with observed state (what exists), approved gaps are
compiled into the workspace, and a Guardian monitors drift.

**v1 scope:** Seed to Series A B2B tech startups (5-50 people) on Google Workspace, sold against an
urgent trigger (enterprise deal, fundraise, security/SOC 2 request, rapid hiring). Concierge first.

Core loop: `Company Profile -> Required State -> Workspace Inventory -> Gap Report -> Compile (approved) -> Guardian`

## Install

Requires Python 3.10 or newer. The core engine has no runtime dependencies; the Google Drive
scanner is an optional extra.

```bash
git clone https://github.com/creova-gif/opsgraph.git
cd opsgraph
python -m venv .venv && source .venv/bin/activate
pip install -e .            # core CLI (works fully offline)
pip install -e ".[drive]"   # optional: real Google Drive scanning
```

## Quick start

First number in four commands (works fully offline):

```bash
opsgraph init --name "Acme Cloud Technologies, Inc." --domain acmecloud.io \
  --stage seed --headcount 14 --output profile.json --save
opsgraph scan --snapshot examples/sample-drive-inventory.json \
  --company-id acmecloud-io --record
opsgraph dashboard --company-id acmecloud-io --output dashboard.html
opsgraph status acmecloud-io
```

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
- [x] **Ask Company (deterministic floor):** `ask` answers questions about readiness, missing/stale artifacts, blockers, owners, and drift — grounded in engine output with citations, honest low-confidence fallback (`qa/`)
- [x] **Guardian Delta:** `digest <company_id>` diffs the last two recorded guardian runs — new/resolved/persistent drift events, severity escalations, and health-score movement (`guardian/digest.py`)
- [x] **Remediation Plan (deterministic floor):** `plan` orders every actionable gap into P0 critical-path → P1–P3 phases in resolver dependency order, with blocked-by annotations (`plan/`)
- [x] **Readiness Certificate:** `certificate` renders the CALIBRATION-series cert from real engine output — score, ruleset version, flag counts, approver chain; certifies a measurement, not compliance (`certificate/`)
- [x] **Plan-driven Apply (Mode D floor):** `apply --from-plan <run_id>` scopes a Drive apply to a recorded plan's ordered steps — the approval ledger gate stays fully intact
- [x] **Profile Onboarding:** `init` generates a schema-valid company profile from answers (`--name --domain --stage --headcount` + optional fields); unanswered answers land in `provenance.unanswered`, governance approval defaults on (`onboarding/`)
- [x] **Store-backed Inputs:** every read/execute command — `gap`, `ask`, `plan`, `certificate`, `dashboard`, `guardian`, `compile`, `apply`, `serve` — accepts `--company-id` to resolve the saved profile + latest recorded scan from the store; record once (`profile save` + `scan --record`), run the whole loop from state
- [x] **Pilot Offer Kit:** 48-Hour offer one-pager, delivery checklist, intake form (`docs/pilot/`)
- [x] **Evidence Room:** 9-folder structure + draft YC application answers (`evidence-room/`)

## Testing

```bash
python -m unittest discover -s . -p 'test_*.py'
```

CI runs the same suite on Python 3.10, 3.12 and 3.14, plus a syntax check and a gap-report smoke test
on the bundled fixtures.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Everyone taking part is expected to follow the
[Code of Conduct](CODE_OF_CONDUCT.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Support

Open an issue on [GitHub](https://github.com/creova-gif/opsgraph/issues) or email
creativeinnovationspace@gmail.com.
