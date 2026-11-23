# AGENTS.md

Project facts, stack and verification commands: `.ai/project.yaml`.
Claude Code: see `CLAUDE.md` (gstack required). Toolchain reference: `docs/ai/`.

Definition of done: run the commands under `verification:` in `.ai/project.yaml`; if one cannot run, report NOT VERIFIED with the reason.
Never push, force-push, or modify remotes without explicit approval.

## Design System

Read `DESIGN.md` before visual or UI work: it defines the CALIBRATION fonts, colors, spacing, and aesthetic direction. Ask the user before departing from it. When reviewing or QA-ing UI, flag code that doesn't match `DESIGN.md`.
