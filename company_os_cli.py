#!/usr/bin/env python3
"""
Company OS — Unified Command Line Interface
The complete AI-maintained company operating system toolkit.
Executes State Resolution, Workspace Inventory, Gap Analysis, Drive Compilation,
and Guardian Continuous Monitoring.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from compiler.compiler import WorkspaceCompiler, format_plan_markdown
from gap_engine.analyzer import GapAnalyzer, format_gap_markdown
from guardian.guardian import CompanyGuardian, format_health_digest_markdown
from inventory.scanner import WorkspaceScanner
from resolver.resolver import StateResolver, format_markdown


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
        from dataclasses import asdict
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_markdown(report))


def cmd_scan(args):
    scanner = WorkspaceScanner()
    if args.snapshot:
        snap_path = Path(args.snapshot)
        if not snap_path.exists():
            sys.stderr.write(f"Snapshot not found: {snap_path}\n")
            sys.exit(1)
        snapshot = scanner.load_snapshot(snap_path)
    elif args.local:
        loc_path = Path(args.local)
        if not loc_path.exists():
            sys.stderr.write(f"Local directory not found: {loc_path}\n")
            sys.exit(1)
        snapshot = scanner.scan_local_directory(loc_path)
    else:
        default_snap = BASE_DIR / "examples" / "sample-drive-inventory.json"
        snapshot = scanner.load_snapshot(default_snap)

    from dataclasses import asdict
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
        from dataclasses import asdict
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
        reg_path = Path(args.register)
        if reg_path.suffix == ".json":
            with open(reg_path, "r", encoding="utf-8") as f:
                register_entries = json.load(f)

    guardian = CompanyGuardian()
    digest = guardian.audit(
        profile_data=profile_data,
        inventory=inventory_snapshot,
        master_register_entries=register_entries,
    )

    if args.format == "json":
        from dataclasses import asdict
        print(json.dumps(asdict(digest), indent=2))
    else:
        print(format_health_digest_markdown(digest))


def cmd_dashboard(args):
    from dashboard.generator import DashboardGenerator

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
        import webbrowser
        webbrowser.open(f"file://{out_path}")


def cmd_serve(args):
    from dashboard.server import serve_dashboard
    serve_dashboard(args.profile, args.inventory, port=args.port, host=args.host)


def cmd_demo(args):
    # Delegate to demo runner
    from demo.run_demo import run_full_demo
    run_full_demo()


def main():
    parser = argparse.ArgumentParser(
        prog="company-os",
        description="Company OS — Turns a startup's Google Workspace into an AI-maintained operating system.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # resolve
    p_resolve = subparsers.add_parser("resolve", help="Deterministically evaluate required operating state")
    p_resolve.add_argument("profile", help="Path to company profile JSON")
    p_resolve.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_resolve.set_defaults(func=cmd_resolve)

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan workspace metadata without reading sensitive content")
    p_scan.add_argument("--snapshot", help="Path to JSON inventory snapshot")
    p_scan.add_argument("--local", help="Path to local folder simulating drive")
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
