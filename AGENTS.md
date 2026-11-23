# Repository Engineering & AI Agent Contract (`AGENTS.md`)

## 1. Decision Hierarchy

Whenever human contributors or AI coding agents inspect, plan, or modify this repository, conflicts are resolved strictly in the following order (`1` overrides `2`–`4`):

1. **Verified Repository State:** Actual Python source code, `pyproject.toml`, `.ai/project.yaml`, and passing `unittest` suites.
2. **Accepted Architecture & Safety Contracts:** `docs/adr/0001-sqlite-wal-and-non-destructive-compiler.md`, `docs/engineering/APPLY_REVERSIBILITY.md`, `docs/architecture/CONSUL_INTEGRATION_CONTRACT.md`, and `SECURITY.md`.
3. **Repository-Specific Constraints:** Rules in this file, `.ai/project.yaml`, and `DESIGN.md`.
4. **Shared Engineering Governance Standard (`v1.0`):** Organization-wide epistemic honesty, CI, and security baseline.

## 2. Hard Invariants for All Agents (Antigravity, Devin, Claude, Codex, GStack)

- **Epistemic Honesty & Provenance:** Never claim a feature, model, compliance certification, or cloud integration is implemented if backed by stubs or rules. Preserve `source = "deterministic"` on deterministic Q&A (`qa/answerer.py`), enforce the mandatory boolean `simulation` field on `consul-core` responses (`integrations/consul.py`), and keep the non-compliance attestation in `certificate/generator.py` intact.
- **Zero-Dependency Core Lock:** Do **not** add third-party runtime packages to the core engine. Core packages (`resolver`, `inventory`, `gap_engine`, `compiler`, `guardian`, `plan`, `qa`, `dashboard`, `certificate`, `onboarding`, `integrations`, `store`, `rules`, `schema`) must run strictly on the Python 3.10+ standard library. Optional Google Drive SDK dependencies stay isolated under `[project.optional-dependencies].drive` in `pyproject.toml`.
- **Least-Privilege & Non-Destructive Write Boundary:**
  - Read discovery (`inventory/drive_source.py`) uses `drive.metadata.readonly` only and never downloads document bodies.
  - Write compilation (`compiler/drive_apply.py` `DriveWriteBackend`) is strictly additive (`create_folder`, `create_file`) under `drive.file`. Never add `delete`, `move`, `rename`, or `overwrite` methods to `DriveWriteBackend`. Reversal stays isolated in `DriveTrashBackend` (`apply --reverse <run_id>`).
- **No Harness or Asset Pollution:** Never commit `.agents/`, `.cursor/`, `gstack/`, `.gstack/`, `attached_assets/`, `evidence-room/`, `.opsgraph/`, `*.db`, `*.sqlite*`, OAuth credentials (`client_secret*.json`, `service_account*.json`, `token.json`), or `.env` files.
- **Security Fail-Closed & PR Discipline:** Place imports at module top. Never introduce hardcoded fallback secrets or weaken `--require-approval` ledger enforcement. Never push directly to `main` or force-push without explicit approval; land changes via focused Conventional Commit pull requests.

## 3. Verification & Tooling

- **Project configuration & verification gates:** See `.ai/project.yaml`.
  - Install: `pip install -e .`
  - Syntax / lint check: `python3 -m compileall -q .`
  - Full test suite (all 16 colocated suites): `python3 -m unittest discover -s . -p 'test_*.py'`
- If any verification gate in `.ai/project.yaml` cannot run, report `NOT VERIFIED` with the exact reason.
- **Claude Code / gstack:** See `CLAUDE.md` and toolchain reference in `docs/ai/`.

## 4. Design System (`CALIBRATION`)

Read `DESIGN.md` and `docs/design/tokens.json` before modifying HTML/CSS output in `dashboard/` or `certificate/`. Ask the user before departing from CALIBRATION typography, color tokens, spacing, or layout rules, and keep `test_design_tokens_single_source` passing.
