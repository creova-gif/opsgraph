# OpsGraph — Current State Audit

**Audit date:** 2026-11-18
**Codebase:** `creova-gif/opsgraph` @ `main` (commit `2ccb82a`)
**Method:** Direct source inspection, 22/22 unit tests run and passing, CLI smoke
paths exercised end-to-end (resolve → scan → gap → compile → guardian → dashboard → demo).

Classification scale: **Verified functional** / **Partially functional** /
**Prototype** / **Simulation only** / **Missing** / **Broken** / **Blocked**.

## Verified functional

| Capability | Evidence |
|---|---|
| Deterministic required-state resolution | `resolver/resolver.py`: 31 artifacts / 12 taxonomy roots, condition evaluation, owner-role→person mapping, Kahn topological ordering. First-match override precedence with conflicts surfaced in artifact reason. Covered by tests incl. synthetic-ruleset precedence test. |
| Dependency ordering | Topological sort in resolver; cycles appended deterministically (not flagged — see findings). |
| Workspace inventory — snapshot source | `inventory/scanner.py` `SnapshotSource` loads hand-authored JSON inventories. Used by all examples and tests. |
| Workspace inventory — local dir source | `LocalDirectorySource` via `os.walk`; verified via `scan --local`. |
| Gap analysis + infrastructure scoring | `gap_engine/analyzer.py`: required-vs-observed matching, staleness vs review cadence, weighted domain scoring, dedup collision detection. 22 tests green incl. matcher boundary cases. |
| Dry-run compilation | `compiler/compiler.py`: idempotent local-dir compile, taxonomy folders derived from ruleset, markdown templates with `OPSGRAPH GOVERNED OPERATIONAL ARTIFACT` provenance marker, Master Register JSON+CSV, audit log. |
| Guardian drift detection | `guardian/guardian.py`: 6 drift categories, linear health penalty, action queue, JSON+CSV register loading, UTC-normalized timestamps. |
| Dashboard | `dashboard/generator.py` standalone HTML + `http.server` preview. |
| CLI | `opsgraph_cli.py` unified argparse; `bin/opsgraph` portable shim (`OPSGRAPH_PYTHON` override); `opsgraph` console script via `pip install -e .`. |
| CI | `.github/workflows/ci.yml` — Python 3.10/3.12/3.14, compileall + unittest + gap smoke. Ran green on first push. |
| Artifact matching | `gap_engine/matching.py`: normalized phrase-boundary matching; artifact IDs (`CO-001`) match filenames correctly; `esop`≠`sop`, `taco 001`≠`co 001`. |

## Partially functional

| Capability | Gap |
|---|---|
| Google Drive inventory | `inventory/drive_source.py` is a **read-only metadata adapter** (paginated `files.list`, `drive.metadata.readonly`, OAuth installed-app + service-account w/ domain delegation). Payload→snapshot mapping unit-tested. **Not exercised against a real Drive** — requires `[drive]` extras + real credentials. No incremental scans, no rate-limit/retry handling, no Docs/Sheets content. |
| Override conflict detection | Deterministic first-match + reason annotation, but no standalone conflict report for rule authors. |
| Register loading | JSON + CSV supported; unsupported suffixes error correctly. |

## Prototype

| Capability | Gap |
|---|---|
| Matcher semantics | Phrase-boundary heuristics; no folder-path awareness, no MIME-type weighting, `MISPLACED` detection still path-substring-based (`old backups`, `random`). |
| Dashboard | Static HTML generation; no auth, no live data, single-file output. |

## Simulation only

Nothing — OpsGraph does not simulate. All outputs derive from deterministic rules
over supplied inventory. (This is a strength relative to Consul, whose default
provider returns canned responses.)

## Missing

- **Real Google Workspace write-back** — compile targets a local directory only; no Drive folder/doc/register writes.
- **Auth, tenancy, persistence** — no database, no org/user model, no OAuth session management, no API server.
- **Scheduling** — Guardian runs on demand only; no cron/event triggers.
- **Semantic memory / Consul Brain integration** — none exists (and none exists in Consul yet either).
- **Billing, onboarding UX, web app** — none.
- **Rules single-source** — `rules/core-artifacts.json` and `.yaml` are dual sources (verified in sync today; no automated sync check in CI).

## Broken

None identified.

## Blocked

- **Real Drive E2E test** — blocked on GCP OAuth client / service-account credentials and `[drive]` dependency install. Not a code defect.

## Known risks (post-remediation)

1. **Depends_on cycle handling**: cycles are silently appended, not flagged to rule authors (`resolver.py`).
2. **Matcher heuristics**: folder-blind; a doc in an archive folder still counts as found.
3. **No integration test against Google client mocks** — drive payload mapping is tested; the API client path is not.
4. **Evidence-room docs** contain YC-aspirational claims (e.g., `opsgraph.io` placeholder); they are business artifacts, not verified product behavior.
