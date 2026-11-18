# OpsGraph × Consul — Implementation Roadmap

**Date:** 2026-11-18
**Sources:** `docs/audits/OPSGRAPH_CURRENT_STATE.md`, `docs/audits/CONSUL_CURRENT_STATE.md`
**Scope:** Evidence-based backlog toward the brief's goal — a commercially
deployable OpsGraph powered by Consul. Phases follow the brief's numbering but
are re-scoped to audited reality. No phase claims work that audits marked
missing.

## Boundary decisions (locked)

- **OpsGraph owns:** company profiles, the Operating Graph, required-state rules,
  inventory, gap detection, readiness scores, compilation, Guardian policies,
  registers, reports, onboarding, billing.
- **Consul owns:** model gateway, markdown-skill workforce, agent planning
  (resolver), adversarial review (cofounder), approval vault, ADR/decision store.
- **Shared substrate to extract:** `ai/provider.ts` shape + skill registry +
  vault primitives → `consul-core` package consumed via a versioned contract.
- **Authority rule:** OpsGraph's deterministic engine and Operating Graph are
  the system of record. Consul output is advisory context and execution labor —
  never silently mutates business facts.

## Phase 0 — Baseline (this audit)

- [x] Audit both repos, classify capabilities, run test suites.
- [x] OpsGraph: 22/22 tests, CI on push/PR, public Apache-2.0 repo.
- [x] Consul: 19/19 tests after build; classified vs the brief's expected surface.

**Consul-side prerequisites before any integration is credible:**

1. Add CI to consul (build → test; currently `npm test` runs 0 tests without a build).
2. Fix `npm audit` criticals; upgrade `next@14.2.23`.
3. Complete FounderOS→Consul rename (96 leftovers incl. `author`, health endpoint, prompt strings).
4. Remove hardcoded vault HMAC fallback secret; require `VAULT_HMAC_SECRET` or fail closed.
5. Make simulation fallback explicit in `AICompletionResult` (a `simulated: true` flag) so callers can't confuse canned output with real inference.

## Phase 1 — Trustworthy local core (OpsGraph only, no Consul)

| Item | Notes |
|---|---|
| Company profile persistence | SQLite first (single-tenant local), schema from `schema/company-profile.schema.json`; Postgres path deferred to SaaS phase. |
| `rules/` single-source | Pick JSON canonical; generate or validate YAML in CI. |
| Drive E2E smoke | Real credentialed scan on a test Workspace; incremental-scan state token; retry/backoff on 403/429. |
| Folder-aware matching | Penalize/archive-aware artifact placement; replace `old backups`/`random` substring heuristic with rules-driven placement policy. |
| depends_on cycle detection | Report cycles to rule authors instead of silent append. |
| Register versioning | Master Register entries carry version + provenance of last compiler run. |

**Exit:** `opsgraph` CLI on a real Workspace snapshot produces a reproducible, explainable gap report — no AI involved.

## Phase 2 — Authorized compilation to a real workspace

| Item | Notes |
|---|---|
| Drive write adapter | Drive folders + Docs creation via least-privilege write scope; idempotent by register ID; dry-run diff first. |
| Approval gate | Approval token required for any write; local-signed approval record persisted with the compile run. |
| Audit trail | Every write logged with before/after state, approver, timestamp. |
| No destructive ops | Initial release never deletes/moves existing customer files. |

**Exit:** OpsGraph applies an approved gap-fix plan into a real Drive, reversibly and audibly.

## Phase 3 — Consul substrate integration (first real AI touchpoint)

| Item | Notes |
|---|---|
| `consul-core` extraction | Provider gateway + markdown-skill registry + vault → shared package or vendored module, versioned. |
| Contract | `AgentTaskRequest`/`AgentTaskResult` typed contract; `simulated` flag mandatory; authenticated service identity between the two runtimes. |
| Guardian remediation PoC | One end-to-end slice: Guardian detects stale policy → OpsGraph emits exception → Consul research+draft+review pattern produces proposed revision → human approves → compiler applies → version recorded. |
| Failure modes | Provider outage → degrade to deterministic report; never block core loop on AI. |

**Exit:** The stale-policy remediation workflow runs end-to-end with a real model and a real approval, or the phase is not done.

## Phase 4 — Agent modes (selective)

Order by pilot value: **Mode A Ask Company** (grounded Q&A over inventory+graph,
with citations) → **Mode E Guardian** (scheduled/event-driven checks) →
**Mode C Planning** → **Mode D Execution**. Modes F/G (specialist workforce,
multi-agent) stay out until at least one paying pilot exists.

## Phase 5 — Commercial SaaS

Multi-tenant Postgres, org/user/roles, OAuth session management, encrypted
secret store (GCP Secret Manager), billing, onboarding UX, web app replacing
the static dashboard, monitoring, backups, customer docs. Consul runs as an
internal service; its execution APIs never face customer browsers.

## Phase 6 — Expansion (evidence-gated)

M365/Notion/CRM integrations, industry packs — only after pilot repeatability.

## Explicit non-goals for now

- No Consul Brain / semantic memory until Phase 3 contract proves the
  integration pattern; build it tenant-aware from day one when built.
- No multi-agent free-roam execution; all consequential actions pass the
  approval vault.
- No claiming compliance certification; readiness scores stay explainable
  infrastructure metrics.

## Open questions for the founder

1. **Repo topology:** extract `consul-core` into a third repo/package, or keep
   OpsGraph→Consul a versioned HTTP contract? (Recommend package extraction —
   Consul's API is domain-bound and unauthenticated today.)
2. **Who owns Consul fixes?** Its prerequisites (CI, vulns, rename, HMAC secret,
   simulation flag) gate Phase 3.
3. **License posture of Consul:** MIT — fine for extraction; note attribution.
4. **Pilot target:** pick one friendly seed-stage Google Workspace company to
   gate Phase 2's exit criteria.
