#!/usr/bin/env python3
"""
OpsGraph — Unified Command Line Interface
The complete AI-maintained company operating system toolkit.
Executes State Resolution, Workspace Inventory, Gap Analysis, Drive Compilation,
and Guardian Continuous Monitoring.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import webbrowser
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from compiler.compiler import WorkspaceCompiler, format_plan_markdown as format_compile_plan_markdown
from compiler.drive_apply import (
    GoogleDriveTrasher,
    GoogleDriveWriter,
    execute_apply,
    execute_reverse,
    plan_apply,
    plan_reverse,
)
from certificate.generator import CertificateGenerator
from dashboard.generator import DashboardGenerator
from dashboard.server import serve_dashboard
from demo.run_demo import run_full_demo
from gap_engine.analyzer import GapAnalyzer, format_gap_markdown
from guardian.digest import diff_digests, format_digest_delta
from guardian.guardian import CompanyGuardian, format_health_digest_markdown, load_register_entries
from integrations.consul import ConsulClient, ConsulUnavailable, HTTPConsulClient, StubConsulClient
from inventory.drive_source import GoogleDriveSource, merge_delta
from inventory.scanner import LocalDirectorySource, SnapshotSource, WorkspaceScanner, snapshot_from_data
from plan.planner import build_plan, format_plan_markdown
from qa.answerer import CompanyAnswerer
from resolver.resolver import StateResolver, format_markdown
from store.store import DEFAULT_DB_PATH, ProfileStore, SCHEMA_PATH, company_id_for
from store.validate import validate as validate_profile
from onboarding.profile import build_profile, CUSTOMER_TYPE_CHOICES, MODEL_CHOICES, STAGE_CHOICES, TRIGGER_CHOICES


def _record_run(args, run_type: str, payload: dict, summary: str,
                profile_data: dict = None, company_id: str = None) -> None:
    """Persist an engine run when --record is passed. company_id comes from
    the explicit override or derives from profile_data the same way
    profile save does, so history stays anchored to one entity."""
    if not getattr(args, "record", False):
        return
    company_id = company_id or getattr(args, "company_id", None)
    if not company_id and profile_data is not None:
        company_id = company_id_for(profile_data)
    if not company_id:
        sys.stderr.write("run not recorded: pass --company-id or a profile\n")
        return
    db_path = Path(getattr(args, "db", None) or DEFAULT_DB_PATH)
    store = ProfileStore(db_path)
    try:
        run_id = store.save_run(company_id, run_type, payload, summary)
        print(f"run recorded: #{run_id} ({run_type}, {company_id}) -> {db_path}")
    except ValueError as e:
        sys.stderr.write(f"run not recorded: {e}\n")
    finally:
        store.close()


def _latest_scan_snapshot(store: ProfileStore, company_id: str):
    """Newest recorded `scan` run's payload rebuilt as an InventorySnapshot,
    or None when the company has no recorded scan."""
    scan_runs = store.list_runs(company_id, run_type="scan", limit=1)
    if not scan_runs:
        return None
    return snapshot_from_data(store.get_run(scan_runs[0]["id"])["payload"])


def _load_profile_snapshot(args, inventory_required: bool = True):
    """Resolve (profile_data, inventory_snapshot) for read commands.

    With --company-id: the saved profile plus the newest recorded `scan` run's
    payload — recorded runs become queryable state instead of write-only.
    Otherwise: the profile/inventory file paths, as before. Pass
    inventory_required=False where the engine tolerates no snapshot (compile)."""
    company_id = getattr(args, "company_id", None)
    if company_id:
        db_path = Path(getattr(args, "db", None) or DEFAULT_DB_PATH)
        store = ProfileStore(db_path)
        try:
            profile_data = store.get_profile(company_id)
            if profile_data is None:
                sys.stderr.write(
                    f"Error: no saved profile for '{company_id}' — run `profile save` first\n")
                sys.exit(1)
            snapshot = _latest_scan_snapshot(store, company_id)
            if snapshot is None and inventory_required:
                sys.stderr.write(
                    f"Error: no recorded scan for '{company_id}' — run `scan --record` first\n")
                sys.exit(1)
        finally:
            store.close()
        return profile_data, snapshot

    profile_arg = getattr(args, "profile", None)
    inventory_arg = getattr(args, "inventory", None)
    if not profile_arg or (inventory_required and not inventory_arg):
        sys.stderr.write(
            "Error: pass profile + inventory paths, or --company-id to load them from the store\n")
        sys.exit(1)
    with open(profile_arg, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    snapshot = WorkspaceScanner().load_snapshot(Path(inventory_arg)) if inventory_arg else None
    return profile_data, snapshot


def cmd_resolve(args):
    profile_path = Path(args.profile)
    if not profile_path.exists():
        sys.stderr.write(f"Error: Profile file not found: {profile_path}\n")
        sys.exit(1)

    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    resolver = StateResolver()
    report = resolver.resolve(profile_data)

    if args.format == "json":
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_markdown(report))

    _record_run(
        args, "resolve", asdict(report),
        summary=f"artifacts={len(report.artifacts)} required={sum(1 for a in report.artifacts if a.level == 'required')}",
        profile_data=profile_data,
    )


def cmd_profile(args):
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    store = ProfileStore(db_path)
    try:
        if args.profile_action == "save":
            profile_path = Path(args.file)
            if not profile_path.exists():
                sys.stderr.write(f"Error: Profile file not found: {profile_path}\n")
                sys.exit(1)
            with open(profile_path, "r", encoding="utf-8") as f:
                profile_data = json.load(f)
            try:
                company_id, version = store.save_profile(profile_data)
            except ValueError as e:
                sys.stderr.write(f"Error: {e}\n")
                sys.exit(1)
            print(f"Saved profile '{company_id}' as version {version} -> {db_path}")

        elif args.profile_action == "list":
            companies = store.list_companies()
            if not companies:
                print("No companies persisted yet.")
            for c in companies:
                print(f"- {c['company_id']}  ({c['legal_name']})  domain={c['domain']}  latest=v{c['latest_version']}")

        elif args.profile_action == "show":
            profile = store.get_profile(args.company_id, version=args.version)
            if profile is None:
                sys.stderr.write(f"Error: no profile '{args.company_id}' (version {args.version or 'latest'}) in {db_path}\n")
                sys.exit(1)
            print(json.dumps(profile, indent=2))
    finally:
        store.close()


def _write_state_file(state_path: Path, snapshot) -> None:
    """Persist snapshot + changes token for the next incremental Drive scan."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(asdict(snapshot), f, indent=2)


def cmd_init(args):
    """Generate a schema-valid profile from CLI answers (pilot onboarding)."""
    try:
        profile_data = build_profile(
            legal_name=args.name,
            domain=args.domain,
            funding_stage=args.stage,
            employee_count=args.headcount,
            model=args.model,
            customer_type=args.customer_type,
            sector=args.sector,
            description=args.description,
            triggers=[t.strip() for t in args.triggers.split(",")] if args.triggers else None,
            jurisdiction=args.jurisdiction,
            countries=[c.strip() for c in args.countries.split(",")] if args.countries else None,
            contractors=args.contractors,
            currently_raising=args.raising,
        )
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = validate_profile(profile_data, schema)
    if errors:
        sys.stderr.write("Error: generated profile failed schema validation (builder drift):\n")
        for e in errors:
            sys.stderr.write(f"  {e}\n")
        sys.exit(1)

    out = Path(args.output)
    out.write_text(json.dumps(profile_data, indent=2) + "\n", encoding="utf-8")
    company_id = company_id_for(profile_data)
    print(f"profile written: {out} (company_id: {company_id})")

    if args.save:
        store = ProfileStore(Path(args.db) if args.db else DEFAULT_DB_PATH)
        try:
            cid, version = store.save_profile(profile_data)
        finally:
            store.close()
        print(f"saved '{cid}' as version {version}")

    if args.save:
        print(f"\nnext: opsgraph scan --snapshot <inventory.json> --company-id {company_id} --record")
    else:
        print(f"next: opsgraph profile save {out} && opsgraph scan --snapshot <inventory.json> --company-id {company_id} --record")


def cmd_scan(args):
    if args.drive:
        if not args.credentials:
            sys.stderr.write(
                "Error: --drive requires --credentials <client_secret|service_account>.json\n"
            )
            sys.exit(1)
        source = GoogleDriveSource(
            credentials_path=Path(args.credentials),
            token_path=Path(args.token) if args.token else None,
            impersonate=args.impersonate,
            domain=args.domain,
        )
        state_path = Path(args.state) if args.state else None
        if state_path and state_path.exists():
            # Incremental: merge a changes.list delta onto the persisted snapshot
            prior = SnapshotSource(state_path).scan()
            token = prior.scan_metadata.get("drive_changes_token")
            if token:
                delta, new_token = source.scan_delta(token)
                if new_token:
                    delta.scan_metadata["drive_changes_token"] = new_token
                snapshot = merge_delta(prior, delta)
            else:
                snapshot = source.scan()  # legacy state file without token
            _write_state_file(state_path, snapshot)
        elif state_path:
            # First incremental run: full scan seeds the state file
            snapshot = source.scan()
            _write_state_file(state_path, snapshot)
        else:
            snapshot = source.scan()
    elif args.snapshot:
        snap_path = Path(args.snapshot)
        if not snap_path.exists():
            sys.stderr.write(f"Snapshot not found: {snap_path}\n")
            sys.exit(1)
        snapshot = SnapshotSource(snap_path).scan()
    elif args.local:
        loc_path = Path(args.local)
        if not loc_path.exists():
            sys.stderr.write(f"Local directory not found: {loc_path}\n")
            sys.exit(1)
        snapshot = LocalDirectorySource(loc_path, domain=args.domain).scan()
    else:
        default_snap = BASE_DIR / "examples" / "sample-drive-inventory.json"
        snapshot = SnapshotSource(default_snap).scan()

    data = asdict(snapshot)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2))
        print(f"Scanned {len(snapshot.files)} files, {len(snapshot.folders)} folders -> {out_path}")
    else:
        print(f"Scanned {len(snapshot.files)} files, {len(snapshot.folders)} folders across '{snapshot.scan_metadata.get('domain', 'workspace')}':")
        for f in snapshot.files[:10]:
            print(f"  - [{f.id}] {f.name} ({f.path})")
        if len(snapshot.files) > 10:
            print(f"  ... and {len(snapshot.files) - 10} more.")

    _record_run(
        args, "scan", data,
        summary=f"files={len(snapshot.files)} folders={len(snapshot.folders)}",
    )


def cmd_gap(args):
    profile_data, inventory_snapshot = _load_profile_snapshot(args)

    resolver = StateResolver()
    resolution = resolver.resolve(profile_data)

    analyzer = GapAnalyzer()
    gap_report = analyzer.analyze(resolution, inventory_snapshot)

    if args.format == "json":
        print(json.dumps(asdict(gap_report), indent=2))
    else:
        print(format_gap_markdown(gap_report))

    _record_run(
        args, "gap", asdict(gap_report),
        summary=f"score={gap_report.infrastructure_score}% missing={gap_report.missing_count}",
        profile_data=profile_data,
    )


def cmd_compile(args):
    profile_data, inventory_snapshot = _load_profile_snapshot(args, inventory_required=False)

    compiler = WorkspaceCompiler()
    approved_set = set(args.approve) if args.approve else None
    held_count = None
    require_approval = args.require_approval or bool(
        (profile_data.get("governance") or {}).get("require_compile_approval")
    )

    if require_approval:
        if not args.require_approval:
            print("governance: require_compile_approval enabled by profile")
        db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
        store = ProfileStore(db_path)
        try:
            approved = store.approved_artifact_ids(company_id_for(profile_data))
        finally:
            store.close()
        approved_set = None if "*" in approved else approved
        if args.approve:
            approved_set = set(args.approve) if approved_set is None else approved_set & set(args.approve)
        eligible = compiler.plan(
            profile_data=profile_data,
            inventory=inventory_snapshot,
            target_dir=args.target,
        )
        eligible_ids = {a["id"] for a in eligible.artifacts_to_compile}
        held_count = len(eligible_ids - approved_set) if approved_set is not None else 0

    if args.dry_run:
        plan = compiler.plan(
            profile_data=profile_data,
            inventory=inventory_snapshot,
            target_dir=args.target,
            approved_artifact_ids=approved_set,
        )
        print(format_compile_plan_markdown(plan))
        if held_count is not None:
            print(f"   Held for approval : {held_count} artifacts")
    else:
        result = compiler.execute(
            profile_data=profile_data,
            inventory=inventory_snapshot,
            target_dir=args.target,
            approved_artifact_ids=approved_set,
            dry_run=False,
        )
        print(f"Compilation complete for {result.company_name}")
        print(f"   Target Directory : {result.target_directory}")
        print(f"   Folders Created  : {len(result.folders_created)}")
        print(f"   Artifacts Stamped: {len(result.artifacts_created)}")
        print(f"   Master Register  : {result.master_register_path}")
        print(f"   Audit Log        : {result.audit_log_path}")
        if held_count is not None:
            print(f"   Held for approval : {held_count} artifacts")

        summary = f"register_v{result.register_version} artifacts={len(result.artifacts_created)}"
        if held_count is not None:
            summary += f" held={held_count}"
        payload = asdict(result)
        # Anchor for Drive apply: row-level versioning continues from these entries
        reg_json_path = Path(result.master_register_path).with_suffix(".json")
        try:
            payload["register_entries"] = json.loads(
                reg_json_path.read_text(encoding="utf-8")
            ).get("entries", [])
        except (OSError, json.JSONDecodeError):
            pass
        _record_run(
            args, "compile", payload,
            summary=summary,
            profile_data=profile_data,
        )


def cmd_apply(args):
    """Phase 2: apply an approved compilation plan to a real Google Drive.

    Default is a dry-run diff — pass --execute to write. Writes are
    create-only, idempotent by artifact ID, and audited; approval-gated
    when the profile declares require_compile_approval.
    """
    if getattr(args, "reverse", None) is not None:
        cmd_reverse(args)
        return

    company_id = getattr(args, "company_id", None)
    store = None
    if not args.profile and not company_id:
        sys.stderr.write("Error: apply requires a profile path or --company-id (or --reverse <run_id>)\n")
        sys.exit(1)
    if company_id:
        store = ProfileStore(Path(getattr(args, "db", None) or DEFAULT_DB_PATH))
        profile_data = store.get_profile(company_id)
        if profile_data is None:
            store.close()
            sys.stderr.write(
                f"Error: no saved profile for '{company_id}' — run `profile save` first\n")
            sys.exit(1)
    else:
        with open(args.profile, "r", encoding="utf-8") as f:
            profile_data = json.load(f)

    # Before-state inventory: explicit snapshot, then live Drive, then the
    # newest recorded scan when --company-id anchors the run in the store.
    try:
        if args.snapshot:
            snapshot = SnapshotSource(Path(args.snapshot)).scan()
        elif args.credentials:
            snapshot = GoogleDriveSource(
                credentials_path=Path(args.credentials),
                token_path=Path(args.token) if args.token else None,
                impersonate=args.impersonate,
                domain=args.domain,
            ).scan()
        elif company_id:
            snapshot = _latest_scan_snapshot(store, company_id)
            if snapshot is None:
                sys.stderr.write(
                    f"Error: no recorded scan for '{company_id}' — pass --snapshot/--credentials or run `scan --record` first\n")
                sys.exit(1)
        else:
            sys.stderr.write(
                "Error: apply requires --credentials <json> for a live Drive, or --snapshot for an offline diff\n"
            )
            sys.exit(1)
    finally:
        if store is not None:
            store.close()

    compiler = WorkspaceCompiler()

    approved_set = None
    governed = bool((profile_data.get("governance") or {}).get("require_compile_approval"))
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    if governed:
        store = ProfileStore(db_path)
        try:
            approved = store.approved_artifact_ids(company_id_for(profile_data))
        finally:
            store.close()
        approved_set = None if "*" in approved else approved
        print("governance: require_compile_approval enabled by profile — unapproved artifacts will be held")

    plan_scope = None
    if args.from_plan is not None:
        store = ProfileStore(db_path)
        try:
            run = store.get_run(args.from_plan)
        finally:
            store.close()
        if not run or run["run_type"] != "plan":
            sys.stderr.write(f"Error: run #{args.from_plan} is not a recorded plan run\n")
            sys.exit(1)
        plan_scope = [s["artifact_id"] for s in run["payload"].get("steps", [])]
        print(f"scope: plan run #{run['id']} — {len(plan_scope)} ordered steps")
        if approved_set is not None:
            approved_set = approved_set & set(plan_scope)
        else:
            approved_set = set(plan_scope)

    plan = compiler.plan(
        profile_data=profile_data,
        inventory=snapshot,
        approved_artifact_ids=approved_set,
    )
    apply_plan = plan_apply(plan, snapshot, include_register=True)

    print(f"Drive Apply Plan — {apply_plan.company_name}")
    print(f"   Folders to create : {len(apply_plan.folders_to_create)}")
    for name in apply_plan.folders_to_create:
        print(f"     + {name}/")
    print(f"   Files to create   : {len(apply_plan.files_to_create)}")
    for spec in apply_plan.files_to_create:
        print(f"     + {spec['root_folder']}/{spec['name']}")
    print(f"   Skipped (existing): {len(apply_plan.skipped)}")
    if governed:
        print(f"   Held for approval : unapproved artifacts excluded from plan")

    if not args.execute:
        print(f"\ndry-run: {apply_plan.total_actions} create actions planned — pass --execute to write to Drive")
        return

    if not args.approver:
        sys.stderr.write("Error: --execute requires --approver <name> for the audit trail\n")
        sys.exit(1)
    if not args.credentials:
        sys.stderr.write("Error: --execute requires --credentials <json> for a live Drive\n")
        sys.exit(1)
    if apply_plan.total_actions == 0:
        print("\nnothing to apply — Drive already matches the approved plan")
        return

    writer = GoogleDriveWriter(
        credentials_path=Path(args.credentials),
        token_path=Path(args.token) if args.token else None,
        impersonate=args.impersonate,
    )
    now_iso = datetime.now(timezone.utc).isoformat()

    # Register versioning anchors to the last recorded compile run so Drive
    # uploads continue the same row-level history instead of restarting at v1.
    reg_csv = reg_json_text = None
    register_version = None
    if any(s.get("content_key") for s in apply_plan.files_to_create):
        prior_version, prior_rows = 0, {}
        db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
        if db_path.exists():
            store = ProfileStore(db_path)
            try:
                latest = store.latest_runs_by_type(company_id_for(profile_data)).get("compile")
                if latest:
                    run = store.get_run(latest["id"])
                    payload = json.loads(run["payload"])
                    prior_version = int(payload.get("register_version", 0) or 0)
                    prior_rows = {
                        r["Document_ID"]: r
                        for r in payload.get("register_entries", [])
                        if isinstance(r, dict) and "Document_ID" in r
                    }
            finally:
                store.close()
        resolution = compiler.resolver.resolve(profile_data)
        built = compiler.build_register(
            resolution, plan, profile_data, prior_version, prior_rows,
            now_iso, compilation_id=f"apply-{int(datetime.now().timestamp())}",
        )
        register_version = built["version"]
        reg_csv = compiler.render_register_csv(built["rows"])
        reg_json_text = json.dumps(
            compiler.render_register_json(
                built["rows"], built["version"], built["provenance"], now_iso
            ),
            indent=2,
        )

    def _content(spec):
        key = spec.get("content_key")
        if key == "register_csv":
            return reg_csv
        if key == "register_json":
            return reg_json_text
        return compiler.render_artifact(spec["item"], profile_data, now_iso)

    result = execute_apply(
        apply_plan,
        writer,
        content_fn=_content,
        approver=args.approver,
    )

    print(f"\nApplied to Drive for {result.company_name}")
    print(f"   Approver        : {result.approver}")
    print(f"   Folders created : {len(result.folders_created)}")
    print(f"   Files created   : {len(result.files_created)}")
    print(f"   Audit entries   : {len(result.audit_log)}")
    if register_version is not None:
        print(f"   Register        : v{register_version} uploaded")

    _record_run(
        args, "apply", asdict(result),
        summary=(
            f"folders={len(result.folders_created)} files={len(result.files_created)} "
            f"skipped={len(apply_plan.skipped)} approver={result.approver}"
        ),
        profile_data=profile_data,
    )


def cmd_reverse(args):
    """Reverse a recorded apply run — trash exactly the IDs it created.

    Deliberately a separate path from apply: its own manifest (the apply
    run's audit log), its own credential, its own --approver, its own
    'reverse' run record. Dry-run prints the manifest; --execute trashes
    files then folders. See docs/engineering/APPLY_REVERSIBILITY.md.
    """
    run_id = args.reverse
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    store = ProfileStore(db_path)
    try:
        run = store.get_run(run_id)
    finally:
        store.close()

    if run is None:
        sys.stderr.write(f"Error: no run #{run_id} in {db_path}\n")
        sys.exit(1)
    if run["run_type"] != "apply":
        sys.stderr.write(
            f"Error: run #{run_id} is a {run['run_type']} run — only apply runs are reversible\n"
        )
        sys.exit(1)

    plan = plan_reverse(run)

    print(f"Reverse Plan — apply run #{plan.run_id} ({plan.company_name})")
    print(f"   Files to trash   : {len(plan.files_to_trash)}")
    for item in plan.files_to_trash:
        print(f"     {item['new_id']}  {item['name']}")
    print(f"   Folders to trash : {len(plan.folders_to_trash)}")
    for item in plan.folders_to_trash:
        print(f"     {item['new_id']}  {item['name']}")

    if plan.total_actions == 0:
        print("\nnothing created by that apply — nothing to reverse")
        return
    if not args.execute:
        print(f"\ndry-run: {plan.total_actions} trash actions planned — pass --execute to reverse")
        return
    if not args.approver:
        sys.stderr.write("Error: --execute requires --approver (reversal needs its own sign-off)\n")
        sys.exit(1)
    if not args.credentials:
        sys.stderr.write(
            "Error: --execute requires --credentials <json> for a live Drive\n"
        )
        sys.exit(1)

    trasher = GoogleDriveTrasher(
        credentials_path=Path(args.credentials),
        token_path=Path(args.token) if args.token else None,
        impersonate=args.impersonate,
    )
    result = execute_reverse(plan, trasher, approver=args.approver)

    print(f"\nReversed apply #{result.run_id} for {result.company_name}")
    print(f"   Approver : {result.approver}")
    print(f"   Trashed  : {len(result.trashed)}")
    print(f"   Failed   : {len(result.failed)}")
    for item in result.failed:
        print(f"     ✗ {item['new_id']}  {item['name']}  — {item['error']}")

    _record_run(
        args, "reverse", asdict(result),
        summary=(
            f"reversed apply #{result.run_id}: trashed={len(result.trashed)} "
            f"failed={len(result.failed)} approver={result.approver}"
        ),
        company_id=run["company_id"],
    )


def _consul_client(args) -> ConsulClient:
    """HTTP client when --consul-url is set, else the deterministic local stub."""
    if args.consul_url:
        return HTTPConsulClient(args.consul_url, os.environ.get("OPSGRAPH_CONSUL_TOKEN", ""))
    return StubConsulClient()


def cmd_guardian(args):
    profile_data, inventory_snapshot = _load_profile_snapshot(args)

    register_entries = None
    if args.register:
        register_entries = load_register_entries(Path(args.register))

    guardian = CompanyGuardian()
    digest = guardian.audit(
        profile_data=profile_data,
        inventory=inventory_snapshot,
        master_register_entries=register_entries,
    )

    proposals = []
    if args.propose:
        client = _consul_client(args)
        company_id = company_id_for(profile_data)
        for i, event in enumerate(digest.events):
            key = f"{company_id}-{event.category}-{event.affected_file or event.affected_artifact_id or event.event_id or i}"
            try:
                result = client.run_agent("guardian-remediation", inputs=asdict(event),
                                          company_id=company_id, idempotency_key=key)
                if result.status != "completed":
                    sys.stderr.write(
                        f"Consul run {result.run_id or '?'} returned status "
                        f"'{result.status or 'unknown'}'; falling back to local simulation\n"
                    )
                    raise ConsulUnavailable(f"run status {result.status!r}")
            except ConsulUnavailable as e:
                sys.stderr.write(f"Consul unavailable ({e}); falling back to local simulation\n")
                client = StubConsulClient()
                result = client.run_agent("guardian-remediation", inputs=asdict(event),
                                          company_id=company_id, idempotency_key=key)
            proposals.append({
                "run_id": result.run_id,
                "skill": "guardian-remediation",
                "status": result.status,
                "simulation": result.simulation,
                "provider": result.provider,
                "core_version": result.core_version,
                "event_type": event.category,
                "output": result.output,
            })

    if args.format == "json":
        print(json.dumps(asdict(digest), indent=2))
    else:
        print(format_health_digest_markdown(digest))
        if proposals:
            print("\n## Remediation proposals")
            for p, event in zip(proposals, digest.events):
                tag = "[simulation]" if p["simulation"] else "[real]"
                target = event.affected_file or event.affected_artifact_id or event.event_id
                print(f"{tag} {target}: {str(p['output'].get('proposal', ''))[:100]}")

    payload = asdict(digest)
    if args.propose:
        payload["proposals"] = proposals
    _record_run(
        args, "guardian", payload,
        summary=f"health={digest.health_score}% events={digest.total_drift_events}",
        profile_data=profile_data,
    )


def cmd_approve(args):
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    store = ProfileStore(db_path)
    decision = "rejected" if args.reject else "approved"
    try:
        for artifact_id in args.artifact_ids:
            try:
                decision_id = store.record_decision(
                    args.company_id, artifact_id, decision, args.approver, args.note
                )
            except ValueError as e:
                sys.stderr.write(f"Error: {e}\n")
                sys.exit(1)
            print(f"{artifact_id}: {decision} by {args.approver} (decision #{decision_id})")
    finally:
        store.close()


def cmd_approvals(args):
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    store = ProfileStore(db_path)
    try:
        approved = store.approved_artifact_ids(args.company_id)
        print(f"Effective approvals for {args.company_id}:")
        if not approved:
            print("  (none — nothing is currently approved)")
        for aid in sorted(approved):
            suffix = "  (all artifacts)" if aid == "*" else ""
            print(f"  {aid}{suffix}")
        decisions = store.list_decisions(args.company_id, limit=10)
        print(f"Latest decisions ({len(decisions)} shown):")
        for d in decisions:
            note = f"  \"{d['note']}\"" if d["note"] else ""
            print(f"  #{d['id']}  {d['created_at'][:19]}  {d['artifact_id']}  {d['decision']}  by {d['approver']}{note}")
    finally:
        store.close()


def cmd_history(args):
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    store = ProfileStore(db_path)
    try:
        if args.run_id is not None:
            run = store.get_run(args.run_id)
            if run is None:
                sys.stderr.write(f"Error: no run #{args.run_id} in {db_path}\n")
                sys.exit(1)
            print(json.dumps(run, indent=2))
            return
        runs = store.list_runs(
            company_id=args.company_id, run_type=args.type, limit=args.limit
        )
        if not runs:
            print("No runs recorded yet.")
        for r in runs:
            print(f"#{r['id']}  {r['created_at'][:19]}  {r['company_id']}  {r['run_type']}  {r['summary']}")
    finally:
        store.close()


STAGE_ORDER = ("scan", "resolve", "gap", "compile", "guardian")


def _age(iso_timestamp: str) -> str:
    """Human age of an ISO timestamp relative to now (UTC)."""
    ts = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    seconds = max(0, int((datetime.now(timezone.utc) - ts).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    days = seconds // 86400
    if days < 30:
        return f"{days}d"
    return f"{days // 30}mo"


def cmd_status(args):
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    store = ProfileStore(db_path)
    try:
        if store.get_profile(args.company_id) is None:
            sys.stderr.write(f"Error: no company '{args.company_id}' in {db_path}\n")
            sys.exit(1)
        info = next((c for c in store.list_companies() if c["company_id"] == args.company_id), {})
        print(f"{info.get('legal_name', '')} ({args.company_id}) — profile v{info.get('latest_version', '?')}")
        latest = store.latest_runs_by_type(args.company_id)
        for stage in STAGE_ORDER:
            run = latest.get(stage)
            if run is None:
                print(f"  {stage:<8} : never run")
            else:
                print(f"  {stage:<8} : {_age(run['created_at'])} ago — {run['summary']}")
        approved = store.approved_artifact_ids(args.company_id)
        decision_count = len(store.list_decisions(args.company_id, limit=10000))
        if "*" in approved:
            print(f"Approvals: all (*)  ({decision_count} decisions)")
        else:
            print(f"Approvals: {len(approved)} effective  ({decision_count} decisions)")
    finally:
        store.close()


def cmd_ask(args):
    """Deterministic 'Ask Company' Q&A over the operating graph (Phase 4 Mode A floor)."""
    profile_data, inventory_snapshot = _load_profile_snapshot(args)

    answer = CompanyAnswerer().ask(args.question, profile_data, inventory_snapshot)

    if args.format == "json":
        print(json.dumps(asdict(answer), indent=2))
    else:
        print(answer.text)
        if answer.citations:
            print("\nCitations:")
            for c in answer.citations:
                print(f"  {c}")
        if answer.confidence == "low":
            print("\n[low confidence — deterministic fallback]")

    _record_run(
        args, "ask", asdict(answer),
        summary=f"intent={answer.intent} confidence={answer.confidence}",
        profile_data=profile_data,
    )


def cmd_plan(args):
    """Deterministic remediation plan: phased, dependency-ordered gap fixes."""
    profile_data, inventory_snapshot = _load_profile_snapshot(args)

    resolver = StateResolver()
    resolution = resolver.resolve(profile_data)
    gap_report = GapAnalyzer().analyze(resolution, inventory_snapshot)

    plan = build_plan(gap_report.company_name, resolution, gap_report)

    if args.format == "json":
        print(json.dumps(asdict(plan), indent=2))
    else:
        print(format_plan_markdown(plan))

    _record_run(
        args, "plan", asdict(plan),
        summary=f"steps={len(plan.steps)} p0={plan.phase_counts.get(0, 0)}",
        profile_data=profile_data,
    )


def cmd_digest(args):
    """Diff the two most recent recorded guardian runs for a company."""
    store = ProfileStore(Path(getattr(args, "db", None) or DEFAULT_DB_PATH))
    try:
        runs = store.list_runs(company_id=args.company_id, run_type="guardian", limit=2)
        if len(runs) < 2:
            sys.stderr.write(
                f"need 2 recorded guardian runs for '{args.company_id}' "
                f"(found {len(runs)}); run guardian --record twice first\n"
            )
            sys.exit(1)
        latest = store.get_run(runs[0]["id"])
        previous = store.get_run(runs[1]["id"])
    finally:
        store.close()

    delta = diff_digests(previous["payload"], latest["payload"])
    if args.format == "json":
        print(json.dumps(delta, indent=2))
    else:
        print(format_digest_delta(delta))
        print(f"\n(runs #{previous['id']} → #{latest['id']})")


def cmd_certificate(args):
    """Generate the Operational Readiness Certificate from real engine output."""
    profile_data, inventory_snapshot = _load_profile_snapshot(args)

    html = CertificateGenerator().generate(
        profile_data, inventory_snapshot,
        approver=args.approver, run_ref=args.run_ref,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"certificate written: {out}")


def cmd_dashboard(args):
    profile_data, inventory_snapshot = _load_profile_snapshot(args)

    gen = DashboardGenerator()
    out_path = Path(args.output).resolve()
    gen.generate(profile_data, inventory_snapshot, output_path=out_path)
    print(f"dashboard written: {out_path}")

    if args.open:
        webbrowser.open(f"file://{out_path}")


def cmd_serve(args):
    if getattr(args, "company_id", None):
        profile_data, snapshot = _load_profile_snapshot(args)
        with tempfile.TemporaryDirectory(prefix="opsgraph_serve_") as tmp:
            p_path = Path(tmp) / "profile.json"
            i_path = Path(tmp) / "inventory.json"
            p_path.write_text(json.dumps(profile_data), encoding="utf-8")
            i_path.write_text(json.dumps(asdict(snapshot)), encoding="utf-8")
            serve_dashboard(str(p_path), str(i_path), port=args.port, host=args.host)
        return
    serve_dashboard(args.profile, args.inventory, port=args.port, host=args.host)


def cmd_demo(args):
    # Delegate to demo runner
    run_full_demo()


def main():
    parser = argparse.ArgumentParser(
        prog="opsgraph",
        description="OpsGraph — Turns a startup's Google Workspace into an AI-maintained operating system.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # resolve
    p_resolve = subparsers.add_parser("resolve", help="Deterministically evaluate required operating state")
    p_resolve.add_argument("profile", help="Path to company profile JSON")
    p_resolve.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_resolve.add_argument("--record", action="store_true", help="Persist this run to the store")
    p_resolve.add_argument("--db", default=None, help=f"SQLite DB path (default: {DEFAULT_DB_PATH})")
    p_resolve.set_defaults(func=cmd_resolve)

    # profile
    # init — generate a schema-valid profile from answers (pilot onboarding)
    p_init = subparsers.add_parser("init", help="Generate a company profile from answers (schema-valid)")
    p_init.add_argument("--name", required=True, help="Legal company name")
    p_init.add_argument("--domain", required=True, help="Workspace domain (e.g. acmecloud.io)")
    p_init.add_argument("--stage", required=True, choices=STAGE_CHOICES, help="Funding stage")
    p_init.add_argument("--headcount", required=True, type=int, help="Employee count")
    p_init.add_argument("--model", default="b2b_saas", choices=MODEL_CHOICES)
    p_init.add_argument("--customer-type", default="enterprise", choices=CUSTOMER_TYPE_CHOICES)
    p_init.add_argument("--sector", default=None, help="Sector (defaulted answers are recorded in provenance.unanswered)")
    p_init.add_argument("--description", default=None, help="One-line business description")
    p_init.add_argument("--triggers", default=None, help=f"Comma-separated commercial triggers; default {','.join(['enterprise_sales','security_questionnaires'])}. Choices: {','.join(TRIGGER_CHOICES)}")
    p_init.add_argument("--jurisdiction", default="Delaware", help="Incorporation jurisdiction")
    p_init.add_argument("--countries", default=None, help="Comma-separated operating countries (default US)")
    p_init.add_argument("--contractors", type=int, default=0)
    p_init.add_argument("--raising", action="store_true", help="Currently raising")
    p_init.add_argument("--output", default="profile.json", help="Output profile path (default profile.json)")
    p_init.add_argument("--save", action="store_true", help="Also persist to the store")
    p_init.add_argument("--db", default=None, help=f"SQLite DB path (default: {DEFAULT_DB_PATH})")
    p_init.set_defaults(func=cmd_init)

    p_profile = subparsers.add_parser("profile", help="Persist and retrieve versioned company profiles (SQLite store)")
    profile_sub = p_profile.add_subparsers(dest="profile_action", required=True)
    p_profile_save = profile_sub.add_parser("save", help="Validate + persist a profile JSON as a new version")
    p_profile_save.add_argument("file", help="Path to company profile JSON")
    p_profile_save.add_argument("--db", default=None, help=f"SQLite DB path (default: {DEFAULT_DB_PATH})")
    p_profile_list = profile_sub.add_parser("list", help="List persisted companies")
    p_profile_list.add_argument("--db", default=None, help=f"SQLite DB path (default: {DEFAULT_DB_PATH})")
    p_profile_show = profile_sub.add_parser("show", help="Print a persisted profile version")
    p_profile_show.add_argument("company_id", help="Company ID (domain slug)")
    p_profile_show.add_argument("--version", type=int, default=None, help="Version number (default: latest)")
    p_profile_show.add_argument("--db", default=None, help=f"SQLite DB path (default: {DEFAULT_DB_PATH})")
    p_profile.set_defaults(func=cmd_profile)

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan workspace metadata without reading sensitive content")
    p_scan.add_argument("--snapshot", help="Path to JSON inventory snapshot")
    p_scan.add_argument("--local", help="Path to local folder simulating drive")
    p_scan.add_argument("--drive", action="store_true", help="Scan a real Google Drive via the Drive API (read-only metadata)")
    p_scan.add_argument("--credentials", help="OAuth client_secret or service_account JSON for --drive")
    p_scan.add_argument("--token", help="Cached OAuth token path for --drive (created on first run)")
    p_scan.add_argument("--impersonate", help="Workspace admin user for service-account domain delegation")
    p_scan.add_argument("--domain", default="local", help="Workspace domain label recorded in scan metadata")
    p_scan.add_argument("--state", help="State file for incremental --drive scans (created on first run; tracks changes.list token)")
    p_scan.add_argument("--output", help="Optional output JSON path")
    p_scan.add_argument("--record", action="store_true", help="Persist this run to the store")
    p_scan.add_argument("--company-id", default=None, help="Company ID to record the scan against")
    p_scan.add_argument("--db", default=None, help=f"SQLite DB path (default: {DEFAULT_DB_PATH})")
    p_scan.set_defaults(func=cmd_scan)

    # gap
    p_gap = subparsers.add_parser("gap", help="Compare required vs observed state; output Infrastructure Score")
    p_gap.add_argument("profile", nargs="?", help="Path to company profile JSON (omit with --company-id)")
    p_gap.add_argument("inventory", nargs="?", help="Path to workspace inventory JSON (omit with --company-id)")
    p_gap.add_argument("--company-id", default=None, help="Load saved profile + latest recorded scan from the store")
    p_gap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_gap.add_argument("--record", action="store_true", help="Persist this run to the store")
    p_gap.add_argument("--db", default=None, help="SQLite store path (default: .opsgraph/opsgraph.db)")
    p_gap.set_defaults(func=cmd_gap)

    # compile
    p_compile = subparsers.add_parser("compile", help="Compile approved folder taxonomy, Master Register, and templates")
    p_compile.add_argument("profile", nargs="?", help="Path to company profile JSON (omit with --company-id)")
    p_compile.add_argument("--inventory", default=None, help="Path to workspace inventory JSON (omit with --company-id)")
    p_compile.add_argument("--company-id", default=None, help="Load saved profile + latest recorded scan from the store")
    p_compile.add_argument("--target", default="./workspace_compiled", help="Target output folder")
    p_compile.add_argument("--dry-run", action="store_true", help="Preview plan without writing")
    p_compile.add_argument("--approve", nargs="+", help="Specific artifact IDs to compile")
    p_compile.add_argument("--require-approval", action="store_true",
                           help="Only compile artifacts with a recorded approval in the store")
    p_compile.add_argument("--record", action="store_true", help="Persist this run to the store")
    p_compile.add_argument("--db", default=None, help="SQLite store path (default: .opsgraph/opsgraph.db)")
    p_compile.set_defaults(func=cmd_compile)

    # apply
    p_apply = subparsers.add_parser("apply", help="Apply an approved compilation plan to a real Google Drive (create-only, audited)")
    p_apply.add_argument("profile", nargs="?", help="Path to company profile JSON (not needed with --reverse or --company-id)")
    p_apply.add_argument("--company-id", default=None, help="Load saved profile + latest recorded scan (as before-state) from the store")
    p_apply.add_argument("--reverse", type=int, metavar="RUN_ID", help="Reverse a recorded apply run — trash exactly the IDs it created")
    p_apply.add_argument("--from-plan", type=int, metavar="RUN_ID", help="Scope the apply to a recorded plan run's ordered artifact steps")
    p_apply.add_argument("--credentials", help="OAuth client_secret or service_account JSON (Drive write scope)")
    p_apply.add_argument("--token", help="Cached OAuth token path (created on first run)")
    p_apply.add_argument("--impersonate", help="Workspace admin user for service-account domain delegation")
    p_apply.add_argument("--domain", default="local", help="Workspace domain label recorded in scan metadata")
    p_apply.add_argument("--snapshot", help="Offline inventory JSON for the before-state diff (no live scan)")
    p_apply.add_argument("--approver", help="Name recorded as the executing approver (required with --execute)")
    p_apply.add_argument("--execute", action="store_true", help="Write to Drive — default is a dry-run diff")
    p_apply.add_argument("--record", action="store_true", help="Persist the apply run to the store")
    p_apply.add_argument("--db", default=None, help="SQLite store path (default: .opsgraph/opsgraph.db)")
    p_apply.set_defaults(func=cmd_apply)

    # approve
    p_approve = subparsers.add_parser("approve", help="Record an approval or rejection decision for artifacts")
    p_approve.add_argument("company_id", help="Company ID (domain slug)")
    p_approve.add_argument("artifact_ids", nargs="+", help="Artifact IDs to decide on ('*' approves all)")
    p_approve.add_argument("--approver", required=True, help="Name of the person making the decision")
    p_approve.add_argument("--note", default="", help="Optional decision note")
    p_approve.add_argument("--reject", action="store_true", help="Record a rejection instead of an approval")
    p_approve.add_argument("--db", default=None, help="SQLite store path (default: .opsgraph/opsgraph.db)")
    p_approve.set_defaults(func=cmd_approve)

    # approvals
    p_approvals = subparsers.add_parser("approvals", help="Show effective approvals and recent decisions")
    p_approvals.add_argument("company_id", help="Company ID (domain slug)")
    p_approvals.add_argument("--db", default=None, help="SQLite store path (default: .opsgraph/opsgraph.db)")
    p_approvals.set_defaults(func=cmd_approvals)

    # guardian
    p_guardian = subparsers.add_parser("guardian", help="Continuous drift monitoring and weekly Health Digest")
    p_guardian.add_argument("profile", nargs="?", help="Path to company profile JSON (omit with --company-id)")
    p_guardian.add_argument("inventory", nargs="?", help="Path to workspace inventory JSON (omit with --company-id)")
    p_guardian.add_argument("--company-id", default=None, help="Load saved profile + latest recorded scan from the store")
    p_guardian.add_argument("--register", default=None, help="Optional Master Register JSON")
    p_guardian.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_guardian.add_argument("--propose", action="store_true",
                            help="Request a remediation proposal per drift event via consul-core (guardian-remediation skill)")
    p_guardian.add_argument("--consul-url", default=None,
                            help="consul-core base URL; unset uses the deterministic local simulation")
    p_guardian.add_argument("--record", action="store_true", help="Persist this run to the store")
    p_guardian.add_argument("--db", default=None, help="SQLite store path (default: .opsgraph/opsgraph.db)")
    p_guardian.set_defaults(func=cmd_guardian)

    # history
    p_hist = subparsers.add_parser("history", help="List recorded engine runs from the store")
    p_hist.add_argument("--company-id", default=None, help="Filter by company")
    p_hist.add_argument("--type", choices=["scan", "resolve", "gap", "compile", "guardian", "apply", "reverse", "ask", "plan"], default=None)
    p_hist.add_argument("--run-id", type=int, default=None, help="Print a single run payload")
    p_hist.add_argument("--limit", type=int, default=20)
    p_hist.add_argument("--db", default=None, help="SQLite store path (default: .opsgraph/opsgraph.db)")
    p_hist.set_defaults(func=cmd_history)

    # status
    p_status = subparsers.add_parser("status", help="Read-only summary of the loop state for one company")
    p_status.add_argument("company_id", help="Company ID (domain slug)")
    p_status.add_argument("--db", default=None, help=f"SQLite DB path (default: {DEFAULT_DB_PATH})")
    p_status.set_defaults(func=cmd_status)

    # ask
    p_ask = subparsers.add_parser("ask", help="Deterministic Q&A over the operating graph (Ask Company)")
    p_ask.add_argument("question", help="Question, e.g. 'do we have a master document register?'")
    p_ask.add_argument("--profile", default=None, help="Path to company profile JSON (omit with --company-id)")
    p_ask.add_argument("--inventory", default=None, help="Path to workspace inventory JSON (omit with --company-id)")
    p_ask.add_argument("--company-id", default=None, help="Load saved profile + latest recorded scan from the store")
    p_ask.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_ask.add_argument("--record", action="store_true", help="Persist this run to the store")
    p_ask.add_argument("--db", default=None, help="SQLite store path (default: .opsgraph/opsgraph.db)")
    p_ask.set_defaults(func=cmd_ask)

    # plan
    p_plan = subparsers.add_parser("plan", help="Dependency-ordered remediation plan (deterministic Mode C)")
    p_plan.add_argument("--profile", default=None, help="Path to company profile JSON (omit with --company-id)")
    p_plan.add_argument("--inventory", default=None, help="Path to workspace inventory JSON (omit with --company-id)")
    p_plan.add_argument("--company-id", default=None, help="Load saved profile + latest recorded scan from the store")
    p_plan.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_plan.add_argument("--record", action="store_true", help="Persist this run to the store")
    p_plan.add_argument("--db", default=None, help="SQLite store path (default: .opsgraph/opsgraph.db)")
    p_plan.set_defaults(func=cmd_plan)

    # digest
    p_digest = subparsers.add_parser("digest", help="Diff the last two recorded guardian runs (what changed)")
    p_digest.add_argument("company_id", help="Company ID (domain slug)")
    p_digest.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_digest.add_argument("--db", default=None, help=f"SQLite DB path (default: {DEFAULT_DB_PATH})")
    p_digest.set_defaults(func=cmd_digest)

    # certificate
    p_cert = subparsers.add_parser("certificate", help="Generate the Operational Readiness Certificate (single-file HTML)")
    p_cert.add_argument("profile", nargs="?", help="Path to company profile JSON (omit with --company-id)")
    p_cert.add_argument("inventory", nargs="?", help="Path to workspace inventory JSON (omit with --company-id)")
    p_cert.add_argument("--company-id", default=None, help="Load saved profile + latest recorded scan from the store")
    p_cert.add_argument("--db", default=None, help="SQLite store path (default: .opsgraph/opsgraph.db)")
    p_cert.add_argument("--output", default="certificate.html", help="Output HTML file path")
    p_cert.add_argument("--approver", default=None, help="Approver identity for the CHAIN/approver field")
    p_cert.add_argument("--run-ref", default=None, help="Run reference (e.g. 'run #7 / apply pending approval')")
    p_cert.set_defaults(func=cmd_certificate)

    # dashboard
    p_dash = subparsers.add_parser("dashboard", help="Generate single-file interactive HTML readiness dashboard")
    p_dash.add_argument("profile", nargs="?", help="Path to company profile JSON (omit with --company-id)")
    p_dash.add_argument("inventory", nargs="?", help="Path to workspace inventory JSON (omit with --company-id)")
    p_dash.add_argument("--company-id", default=None, help="Load saved profile + latest recorded scan from the store")
    p_dash.add_argument("--db", default=None, help="SQLite store path (default: .opsgraph/opsgraph.db)")
    p_dash.add_argument("--output", default="dashboard.html", help="Output HTML file path")
    p_dash.add_argument("--open", action="store_true", help="Open generated dashboard in default browser")
    p_dash.set_defaults(func=cmd_dashboard)

    # serve
    p_serve = subparsers.add_parser("serve", help="Launch local preview server for interactive dashboard")
    p_serve.add_argument("--profile", default="examples/seed-b2b-saas.json", help="Path to company profile JSON (omit with --company-id)")
    p_serve.add_argument("--inventory", default="examples/sample-drive-inventory.json", help="Path to workspace inventory JSON (omit with --company-id)")
    p_serve.add_argument("--company-id", default=None, help="Serve from saved profile + latest recorded scan in the store")
    p_serve.add_argument("--db", default=None, help="SQLite store path (default: .opsgraph/opsgraph.db)")
    p_serve.add_argument("--port", type=int, default=8080, help="Local port to serve on")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host interface")
    p_serve.set_defaults(func=cmd_serve)

    # demo
    p_demo = subparsers.add_parser("demo", help="Run end-to-end 7-moment live simulation for YC demo recording")
    p_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args()
    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
