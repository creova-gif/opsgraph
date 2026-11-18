# OpsGraph–Consul Integration Contract

**Status:** draft v0.1 — no code consumes this contract yet. It exists so Consul
and OpsGraph can be built in parallel against the same surface.
**Grounded in:** `docs/audits/CONSUL_CURRENT_STATE.md`, `docs/audits/OPSGRAPH_CURRENT_STATE.md`.

## Why this document exists

The original brief assumed Consul was a ready-made agent platform OpsGraph
could call. The Phase 0 audit found otherwise: Consul is a peer application
(accelerator/founder workflows) with reusable internals but no generic
execution API. This contract defines the surface that must exist before
OpsGraph delegates any intelligent work to Consul.

Two repositories, two responsibilities:

- **OpsGraph** owns operational truth: profiles, required state, inventory,
  gap reports, the approval ledger, compilation, and Guardian drift detection.
- **Consul** owns intelligent execution: model calls, agent runs, and
  (eventually) memory. It never touches a workspace directly.

## The boundary

OpsGraph calls Consul over a versioned HTTP API, `consul-core` v1. Consul
returns typed results; OpsGraph decides what to do with them. Consul never
writes to Drive, never compiles, never mutates the OpsGraph store.

```
OpsGraph (CLI / Guardian)                consul-core v1 (Consul service)
┌─────────────────────────┐   HTTP      ┌──────────────────────────────┐
│ guardian detects drift  │ ──────────► │ POST /v1/agent-runs          │
│ gap report needs triage │   bearer    │   { skill, inputs, policy }  │
│                         │ ◄────────── │   → { run_id, output,        │
│ approval ledger decides │             │        provider, simulation }│
│ compiler applies        │             └──────────────────────────────┘
└─────────────────────────┘
```

## Data shapes

All payloads are JSON. Field names are `snake_case`. Times are ISO-8601 UTC.

### Request — `POST /v1/agent-runs`

| Field | Type | Required | Notes |
|---|---|---|---|
| `skill` | string | yes | Named Consul skill, e.g. `"guardian-remediation"`. Skills are versioned markdown directives, not free-form prompts. |
| `inputs` | object | yes | Skill-specific payload. OpsGraph sends structured domain objects (a drift event, a gap report), never raw file contents. |
| `company_id` | string | yes | OpsGraph company ID (domain slug). Used for telemetry attribution, not tenancy — Consul remains single-tenant in v1. |
| `policy` | object | no | Execution constraints: `max_tokens`, `timeout_seconds`, `provider` allow-list. Defaults are server-side. |
| `idempotency_key` | string | yes | OpsGraph run ID. Retries with the same key return the original result, not a second model call. |

### Response

| Field | Type | Notes |
|---|---|---|
| `run_id` | string | Consul's run identifier. |
| `status` | `"completed" \| "failed" \| "pending"` | `pending` means poll `GET /v1/agent-runs/{run_id}`. v1 may complete synchronously and never emit `pending`. |
| `output` | object | Skill-specific structured result. JSON-schema'd per skill. |
| `provider` | string | Model that produced the output, e.g. `"gemini-2.0-flash"`, `"nim-llama-3.1"`, or `"simulation"`. |
| `simulation` | boolean | **Required.** `true` when the output came from Consul's deterministic fallback. OpsGraph must treat `simulation: true` results as proposals for human review only — never as evidence. |
| `usage` | object | `input_tokens`, `output_tokens`, `cost_usd`. |

### Errors

RFC 7807-style body: `{ "type", "title", "status", "detail" }`. OpsGraph treats
any non-2xx as a failed agent run, records it in `runs`, and falls back to its
deterministic path (the gap report and Guardian digest work without Consul).

## Authentication

v1: shared bearer token in an `Authorization: Bearer` header. The token lives
in an env var on each side (`OPSGRAPH_CONSUL_TOKEN`), never in the store, never
in a repo. Consul must reject unauthenticated requests — its current API has
none, which is blocker #1 below.

## Versioning

- The API version is in the path (`/v1/`). Additive changes ship under the
  same version; breaking changes bump it.
- Consul returns `X-Consul-Core-Version` on every response so OpsGraph can log
  and pin.

## The first integration slice

Smallest end-to-end use of this contract, mapped onto the loop OpsGraph
already has:

1. `opsgraph guardian` detects drift events (existing).
2. For each drift event above a severity threshold, OpsGraph calls
   `POST /v1/agent-runs` with `skill: "guardian-remediation"` and the event as
   `inputs`.
3. Consul returns a remediation proposal (`output.proposal`, `output.patch`,
   `output.rationale`).
4. OpsGraph writes the proposal into the run payload (`--record`) and, when
   the proposal implies a compile, surfaces it through the existing approval
   ledger (`approve` → `compile --require-approval`).

Nothing in this slice lets Consul act. It proposes; the ledger decides.

## Consul-side prerequisites

Ordered blockers, from the audit, that must land in `creova-gif/consul`
before this contract can be implemented:

1. **Request authentication** — Consul's ~30 endpoints are unauthenticated
   with open CORS today.
2. **Explicit simulation flag** — a missing API key currently returns canned
   output indistinguishable from real results. `simulation: true` in the
   contract makes the fallback honest.
3. **Durable run records** — agent runs need a persisted record (the in-memory
   vault/queues lose state on restart).
4. **Extract `consul-core`** — `ai/provider.ts`, the skill registry, the
   approval vault, and the ADR store become a versioned package separate from
   accelerator-domain endpoints.
5. **Vault secret out of source** — the hardcoded HMAC fallback must go.

## Non-goals for v1

- No semantic memory / "Consul Brain". Remediation proposals are stateless;
  OpsGraph's `runs` table is the audit trail.
- No multi-tenancy. `company_id` is telemetry attribution only.
- No Consul-initiated writes anywhere. Pull model only: OpsGraph asks, Consul
  answers.
- No tool gateway. Skills receive structured inputs; they do not call back
  into OpsGraph or Google APIs.
