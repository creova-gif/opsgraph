# Consul — Current State Audit (as integration substrate for OpsGraph)

**Audit date:** 2026-11-18
**Codebase:** `creova-gif/consul` @ `master` (local clone `~/consul`, synced to `origin/master`)
**Method:** Full source read of `apps/api/src` (~6,800 LOC TS), `bin/consul.js`,
docs, package manifests; `npm install` + `npm run build:api` + `npm test`
executed locally → **19/19 tests pass** (README badge claims 18; `npm test`
without a prior build runs **0 tests** — the suite executes compiled `dist/` output).

## The headline finding

**Consul is not the reusable AI-infrastructure platform the integration brief
assumes.** It is a peer application: a "sovereign OS for solo founders /
accelerator cohorts" (application scoring, mentor/investor matching, milestone
escrow, cap-table modeling, SDG-8 auditing) with a thin agent layer underneath.
It was previously named **FounderOS** — 96 leftover `founderos`/`FounderOS`
references remain in code, prompts, package author, and docs.

For the OpsGraph brief, the correct framing is:

> Consul contributes **patterns and a partial substrate** (model gateway,
> markdown-skill workforce, resolver decomposition, cryptographic approval
> vault, ADR store), not a ready-made agent platform. A versioned "execute
> agent" service contract does not exist and must be built.

## Capability classification vs the brief's expected Consul surface

| Brief capability | Status | Evidence |
|---|---|---|
| Model gateway | **Partially functional** | `ai/provider.ts`: real `fetch` clients for NVIDIA NIM, Gemini, Claude + deterministic `simulation` fallback. BYOK vault stores masked keys in SQLite; token spend logged per call. No streaming, retries, rate-limit handling, or cost budgets. **Risk:** missing API key silently falls back to canned simulation output (console.warn only) — callers cannot distinguish real vs simulated intelligence. |
| Agent execution runtime | **Prototype** | 13 agent modules; most are single-turn `prompt → JSON.parse` wrappers. Deterministic engines (covenants, captable, vault) are genuinely functional. No tool-use loop, no multi-turn execution, no timeouts/sandbox. |
| Multi-agent orchestration | **Prototype** | `OrchestratorService` is a synchronous method dispatcher with in-memory state and hardcoded mentor/investor fixtures. The README's "parallel execution DAGs" is aspirational — the resolver emits a *plan*; nothing executes dependent steps. Agents never communicate with each other. |
| Persistent AI memory ("Consul Brain") | **Partially functional** | SQLite WAL (`node:sqlite`, experimental in Node ≥22.5) with in-memory fallback: ADRs, proposal evals, standups, token telemetry, BYOK keys. **No semantic memory** — no embeddings, no vector search, no context retrieval, no cross-document reasoning. A "Brain" does not exist. |
| Agent lifecycle management | **Missing** | Agents are stateless singletons; no lifecycle, registration, or health model. |
| Tool gateway | **Missing** | No tool/function-calling abstraction, no permission-scoped tool invocation. "Connected rails" (Mercury, M-Pesa, Linear, Circle) are README claims — the only real integration code is a WhatsApp webhook stub and a generic in-memory webhook queue. |
| Workflow execution | **Prototype** | `services/webhook-queue.ts` (75 lines, in-memory). No durable jobs, scheduling, retries, or dead-lettering. |
| AI task planning | **Partially functional** | `AutonomousResolverAgent.resolveGoal`: one LLM call decomposes a founder goal into a skill-assignment plan. Plan is returned, not executed. |
| Agent observability | **Partially functional** | Per-call token/cost logging to `token_telemetry`. No run tracing, spans, or execution history per task. |
| AI evaluations | **Missing** | Benchmark table in README is positioning prose; no eval harness exists. |
| AI execution policies / approvals | **Partially functional** | `CryptographicApprovalVault`: HMAC-SHA256 signature records, role dedup, 72h expiry, dual-sig threshold ≥$500, in-memory audit log. Real logic — but pending queue and audit log are **in-memory only** (lost on restart), and the HMAC secret defaults to a hardcoded string in source. |
| API services | **Partially functional** | Express, ~30 `/api/v1/orchestrator/*` endpoints. **No authentication or authorization at all; CORS wide open.** Anyone who can reach the port can sign vault actions. Single-tenant by construction. |
| CLI / SDK | **Partially functional** | `bin/consul.js`: zero-dep `init`, `standup`, `adr`, `demo`, `status`, `tunnel` — works locally. `private: true`, so `npx consul` does not resolve outside the repo. No SDK or typed client contract for external products. |
| Security posture | **Partially functional** | `utils/pii.ts` redaction util; BYOK masking; no secrets in tree — but the vault HMAC fallback secret is committed, API has no authn, `npm install` reports **3 vulns (1 critical)**, `next@14.2.23` deprecated with a security advisory. |
| CI | **Missing** | No `.github/` workflows. Test badge is stale (18 vs actual 19) and suite requires a build first. |
| Deployment | **Prototype** | Two Dockerfiles + `infra/deploy-cloud-run.sh`; no IaC, no env validation, Firestore referenced in comments but code path is in-memory/SQLite only. |

## What is genuinely reusable for OpsGraph

1. **Markdown-skill workforce pattern** — versioned `.md` role directives
   (`apps/api/src/skills/`, dogfooded in `.consul/skills/`) map naturally onto
   OpsGraph Mode F "Executive Workforce" agents.
2. **Model gateway shape** — provider enum + single `complete()` entry point +
   token telemetry is the right skeleton; needs hardened fallback semantics,
   streaming, retries, budgets.
3. **Approval vault concept** — signature-tiered consequential-action gating is
   the right primitive for OpsGraph compile approvals; needs durable storage,
   real identity, and no hardcoded secret.
4. **ADR store** — decision records in git + SQLite; aligns with OpsGraph
   governance registers.
5. **Cofounder red-team prompt pattern** — adversarial persona evaluation is a
   prompt-level pattern reusable for Guardian remediation review.

## What must be built (does not exist in either repo)

- A **versioned service contract** between OpsGraph and Consul (typed API,
  authenticated service identity, event/job exchange). Consul's current API is
  domain-bound to accelerator workflows, not generic agent execution.
- **Consul Brain**: semantic memory layer (indexing, retrieval, provenance,
  ACL-aware deletion propagation) — greenfield.
- **Durable execution**: job queue, retries, scheduling, agent run records.
- **Multi-tenancy**: org/user/role model exists in neither codebase.
- **API auth**: Consul has zero request authentication today.

## Integration verdict

- Treat Consul's **patterns** as reference implementations; treat its
  **substrate** (provider, vault, ADR, markdown skills) as extractable modules.
- Do not point OpsGraph at Consul's `/api/v1/orchestrator/*` endpoints — they
  are wrong-domain and unauthenticated.
- Smallest honest first integration: extract `ai/provider.ts` + skill-registry
  concept into a shared `consul-core` package (or vendored module) consumed by
  OpsGraph's Guardian remediation path — behind an explicit `ProviderResult`
  contract that distinguishes `simulation` from real-model output.
