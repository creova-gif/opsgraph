# Contributing to OpsGraph

Thank you for your interest in contributing to OpsGraph.

## 1. Development Setup

OpsGraph requires **Python 3.10+**. The core engine uses only the Python standard library; optional Google Drive SDK packages are isolated under the `drive` extra.

```bash
git clone https://github.com/creova-gif/opsgraph.git
cd opsgraph
python3 -m venv .venv && source .venv/bin/activate
pip install -e .            # zero-dependency core CLI
pip install -e ".[drive]"   # optional: live Google Drive API adapters
```

## 2. Architectural & Safety Guardrails

Before proposing changes, review [AGENTS.md](AGENTS.md), [SECURITY.md](SECURITY.md), and [ADR 0001](docs/adr/0001-sqlite-wal-and-non-destructive-compiler.md):

- **Zero-Dependency Core:** Do not introduce third-party runtime dependencies into core packages.
- **Split OAuth & Non-Destructive Writes:** Keep `inventory/drive_source.py` strictly on `drive.metadata.readonly` (no document body downloads) and `compiler/drive_apply.py` (`DriveWriteBackend`) strictly additive (`create_folder`, `create_file` under `drive.file` — never `delete`, `move`, or `overwrite`).
- **Epistemic Provenance:** Preserve `source="deterministic"` in `qa/answerer.py`, require the boolean `simulation` flag in `integrations/consul.py`, and never claim legal or regulatory compliance in generated outputs.
- **Design System:** Read [DESIGN.md](DESIGN.md) and `docs/design/tokens.json` before changing HTML/CSS in `dashboard/` or `certificate/`.
- **Code Style:** Place all imports at module top. Keep changes focused and atomic.

## 3. Pre-PR Verification Checklist

1. Create a feature branch from `main` (`feat/...`, `fix/...`, `docs/...`, `chore/...`) and format commits using [Conventional Commits](https://www.conventionalcommits.org/).
2. Run syntax checks across all packages, the full 16-suite `unittest` discovery pass, and an offline CLI smoke check:
   ```bash
   python3 -m compileall -q certificate compiler dashboard demo gap_engine guardian integrations inventory onboarding plan qa resolver rules schema store opsgraph_cli.py
   python3 -m unittest discover -s . -p 'test_*.py'
   python3 opsgraph_cli.py gap examples/seed-b2b-saas.json examples/sample-drive-inventory.json
   ```
3. Verify `git status` is clean of `.opsgraph/`, `.sqlite*`, `.env`, or Google OAuth credential files before pushing.

## 4. Reporting Issues & Security Disclosures

- **Bugs & feature requests:** Open a GitHub issue using our issue forms with reproducible fixture commands. Never include real company workspace data or Google credentials.
- **Security vulnerabilities:** Follow [SECURITY.md](SECURITY.md) and email `creativeinnovationspace@gmail.com` privately.
- **Community standards:** All contributors are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).
