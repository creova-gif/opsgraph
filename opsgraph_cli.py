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
import sys
import webbrowser
from dataclasses import asdict
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from compiler.compiler import WorkspaceCompiler, format_plan_markdown
from dashboard.generator import DashboardGenerator
from dashboard.server import serve_dashboard
from demo.run_demo import run_full_demo
from gap_engine.analyzer import GapAnalyzer, format_gap_markdown
from guardian.guardian import CompanyGuardian, format_health_digest_markdown, load_register_entries
from inventory.drive_source import GoogleDriveSource, merge_delta
from inventory.scanner import LocalDirectorySource, SnapshotSource, WorkspaceScanner
from resolver.resolver import StateResolver, format_markdown
from store.store import DEFAULT_DB_PATH, ProfileStore


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


def cmd_gap(args):
    profile_path = Path(args.profile)
    inventory_path = Path(args.inventory)

    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    scanner = WorkspaceScanner()
    inventory_snapshot = scanner.load_snapshot(inventory_path)

    resolver = StateResolver()
    resolution = resolver.resolve(profile_data)

    analyzer = GapAnalyzer()
    gap_report = analyzer.analyze(resolution, inventory_snapshot)

    if args.format == "json":
        print(json.dumps(asdict(gap_report), indent=2))
    else:
        print(format_gap_markdown(gap_report))


def cmd_compile(args):
    profile_path = Path(args.profile)
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    inventory_snapshot = None
    if args.inventory:
        scanner = WorkspaceScanner()
        inventory_snapshot = scanner.load_snapshot(Path(args.inventory))

    compiler = WorkspaceCompiler()
    approved_set = set(args.approve) if args.approve else None

    if args.dry_run:
        plan = compiler.plan(
            profile_data=profile_data,
            inventory=inventory_snapshot,
            target_dir=args.target,
            approved_artifact_ids=approved_set,
        )
        print(format_plan_markdown(plan))
    else:
        result = compiler.execute(
            profile_data=profile_data,
            inventory=inventory_snapshot,
            target_dir=args.target,
            approved_artifact_ids=approved_set,
            dry_run=False,
        )
        print(f"✅ Compilation Complete for {result.company_name}!")
        print(f"   Target Directory : {result.target_directory}")
        print(f"   Folders Created  : {len(result.folders_created)}")
        print(f"   Artifacts Stamped: {len(result.artifacts_created)}")
        print(f"   Master Register  : {result.master_register_path}")
        print(f"   Audit Log        : {result.audit_log_path}")


def cmd_guardian(args):
    profile_path = Path(args.profile)
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    scanner = WorkspaceScanner()
    inventory_snapshot = scanner.load_snapshot(Path(args.inventory))

    register_entries = None
    if args.register:
        register_entries = load_register_entries(Path(args.register))

    guardian = CompanyGuardian()
    digest = guardian.audit(
        profile_data=profile_data,
        inventory=inventory_snapshot,
        master_register_entries=register_entries,
    )

    if args.format == "json":
        print(json.dumps(asdict(digest), indent=2))
    else:
        print(format_health_digest_markdown(digest))


def cmd_dashboard(args):
    profile_path = Path(args.profile)
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    scanner = WorkspaceScanner()
    inventory_snapshot = scanner.load_snapshot(Path(args.inventory))

    gen = DashboardGenerator()
    out_path = Path(args.output).resolve()
    gen.generate(profile_data, inventory_snapshot, output_path=out_path)
    print(f"📊 Interactive Dashboard generated at: {out_path}")

    if args.open:
        webbrowser.open(f"file://{out_path}")


def cmd_serve(args):
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
    p_resolve.set_defaults(func=cmd_resolve)

    # profile
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
    p_scan.set_defaults(func=cmd_scan)

    # gap
    p_gap = subparsers.add_parser("gap", help="Compare required vs observed state; output Infrastructure Score")
    p_gap.add_argument("profile", help="Path to company profile JSON")
    p_gap.add_argument("inventory", help="Path to workspace inventory JSON")
    p_gap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_gap.set_defaults(func=cmd_gap)

    # compile
    p_compile = subparsers.add_parser("compile", help="Compile approved folder taxonomy, Master Register, and templates")
    p_compile.add_argument("profile", help="Path to company profile JSON")
    p_compile.add_argument("--inventory", default=None, help="Path to workspace inventory JSON")
    p_compile.add_argument("--target", default="./workspace_compiled", help="Target output folder")
    p_compile.add_argument("--dry-run", action="store_true", help="Preview plan without writing")
    p_compile.add_argument("--approve", nargs="+", help="Specific artifact IDs to compile")
    p_compile.set_defaults(func=cmd_compile)

    # guardian
    p_guardian = subparsers.add_parser("guardian", help="Continuous drift monitoring and weekly Health Digest")
    p_guardian.add_argument("profile", help="Path to company profile JSON")
    p_guardian.add_argument("inventory", help="Path to workspace inventory JSON")
    p_guardian.add_argument("--register", default=None, help="Optional Master Register JSON")
    p_guardian.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_guardian.set_defaults(func=cmd_guardian)

    # dashboard
    p_dash = subparsers.add_parser("dashboard", help="Generate single-file interactive HTML readiness dashboard")
    p_dash.add_argument("profile", help="Path to company profile JSON")
    p_dash.add_argument("inventory", help="Path to workspace inventory JSON")
    p_dash.add_argument("--output", default="dashboard.html", help="Output HTML file path")
    p_dash.add_argument("--open", action="store_true", help="Open generated dashboard in default browser")
    p_dash.set_defaults(func=cmd_dashboard)

    # serve
    p_serve = subparsers.add_parser("serve", help="Launch local preview server for interactive dashboard")
    p_serve.add_argument("--profile", default="examples/seed-b2b-saas.json", help="Path to company profile JSON")
    p_serve.add_argument("--inventory", default="examples/sample-drive-inventory.json", help="Path to workspace inventory JSON")
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
