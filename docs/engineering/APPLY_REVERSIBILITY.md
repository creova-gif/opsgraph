# Apply Reversibility

How an `opsgraph apply` run is undone, why the write adapter has no delete,
and what a future `--reverse` must look like to stay honest.

## The guarantee that makes reversal simple

The Phase 2 writer is **create-only** by construction. `DriveWriteBackend`
exposes two methods — `create_folder`, `create_file` — and nothing else.
There is no `update`, `move`, `rename`, `trash`, or `delete` anywhere in the
protocol, so a compromised or buggy apply cannot mutate, relocate, or destroy
anything that existed before it ran.

Consequence: the pre-apply state of a Drive is fully described by "the IDs we
created did not exist." Reversal is therefore not a restore operation — it is
removing a known, enumerated set of objects and nothing more.

## What apply creates

Every executed apply writes:

| Object | Where | Naming |
|---|---|---|
| Taxonomy root folders | Drive root (`root_parent_id`) | `00_Admin/` … `99_Archive/` per the ruleset |
| Artifact placeholder Docs | Inside their canonical root folder | `<ARTIFACT-ID>_<Title>` e.g. `HR-014_Offer_Letter_Template` |
| Master Register CSV + JSON | The `CO-001` folder | `CO-001_Master_Document_Register.{csv,json}` |

Anything that already exists by name in its canonical location is **skipped**
— recorded as a `skip` audit entry, never overwritten, never duplicated.

## The reversal manifest

Every apply executed with `--record` persists its complete write set in the
run payload:

```
opsgraph history --run-id <N>
```

returns the run JSON, whose `payload.audit_log` lists one entry per action:

```json
{"action": "create_folder", "name": "20_People", "parent_id": "root", "new_id": "1AbC…"}
{"action": "create_file", "name": "HR-014_Offer_Letter_Template",
 "artifact_id": "HR-014", "parent_id": "1AbC…", "new_id": "1XyZ…", "mime_type": "…"}
{"action": "skip", "name": "CO-001_Master_Document_Register.csv", "reason": "exists"}
```

The reversal manifest is exactly the set of `new_id` values on `create_*`
entries. No inference, no name matching — the IDs Drive assigned are recorded
at write time.

## Reversing an apply today

1. `opsgraph history --type apply` to find the run.
2. `opsgraph history --run-id <N>` and collect every `new_id` from
   `audit_log` entries whose `action` is `create_folder` or `create_file`.
3. Trash those file IDs in Drive first, then the folder IDs. That is the
   entire reversal — nothing else was ever modified.

Because reversal is a real write, it should be performed with a separately
scoped credential and a separate human decision, never silently as part of
another command.

## Why the writer will never grow a delete

Reversal-by-deletion is intentionally a *different* capability than
apply-by-creation:

- The create-only contract is a security property, not a feature gap. Any
  code path that can trash a Drive ID can trash *any* Drive ID it can reach;
  keeping that code out of `DriveWriteBackend` keeps the whole apply path
  structurally safe.
- A `trash` capability is still a delete-class operation on Drive IDs;
  keeping it behind a different constructor means an apply credential can
  never accidentally gain it.
- The correct shape is a **separate adapter**: `opsgraph apply --reverse
  <run_id>` reads the run's audit log, requires a fresh `--approver`, uses a
  trash-capable client (`DriveTrashBackend`, one `trash` method) constructed
  for that purpose only, and records a `reverse` run of its own. `drive.file`
  scope suffices because reversal only touches objects the app itself
  created. Designing it this way keeps "reversible" true without weakening
  "never destructive by accident."

## What reversal does not touch

- **The store.** The SQLite run history and approval ledger are append-only
  by design — a reversed apply stays in history (that is the audit trail),
  annotated by its own `reverse` run record.
- **The register's version lineage.** `compile --record` remains the version
  of record; trashing a Drive copy of `CO-001_Master_Document_Register.*`
  does not reset register versioning — a subsequent apply re-uploads at the
  next version.
- **Anything Drive-side that OpsGraph did not create.** Skipped and
  pre-existing files are outside the reversal set by construction.

## Implementation

Implemented as specified:

- `compiler/drive_apply.py` — `DriveTrashBackend` (single `trash(file_id)`
  method, no other surface), `plan_reverse` (manifest from the run's
  `audit_log`, files before folders), `execute_reverse` (per-item failures
  recorded, never halting the pass), `GoogleDriveTrasher` (`files.update`
  with `trashed: true`, `drive.file` scope) and `MemoryDriveTrasher`.
- `opsgraph_cli.py` — `apply --reverse <run_id>`: dry-run prints the
  manifest; `--execute` requires a fresh `--approver` and `--credentials`;
  non-`apply` and missing run IDs are rejected; executed reversals record a
  `reverse` run against the same `company_id`.
- `store/store.py` — `reverse` added to `RUN_TYPES`.

The remaining Phase 2 gate is the credentialed real-Drive validation run —
apply, then reverse, on a test Workspace.
