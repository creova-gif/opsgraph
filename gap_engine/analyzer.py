#!/usr/bin/env python3
"""
OpsGraph — Gap Analysis Engine (v0.1)
Compares Required State (from State Resolver) against Observed State (from Workspace Inventory).
Detects missing, stale, duplicated, unowned, and misplaced artifacts.
Calculates the explainable Company Infrastructure Score (0-100%).
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gap_engine.matching import find_matching_files, placement_class, placement_policy
from inventory.scanner import InventorySnapshot, WorkspaceScanner
from resolver.resolver import ResolutionReport, StateResolver, load_rules_data

CRITICALITY_WEIGHTS = {"high": 3, "medium": 2, "low": 1}


@dataclass
class GapItem:
    artifact_id: str
    artifact_name: str
    root: str
    root_name: str
    level: str  # required, recommended, optional
    criticality: str  # high, medium, low
    status: str  # PRESENT_CURRENT, PRESENT_STALE, MISSING, MISPLACED, DUPLICATE_COLLISION
    resolved_owner: str
    matched_files: List[Dict[str, Any]]
    review_cadence_days: int
    days_stale: int
    remediation_action: str
    framework_mappings: List[str]


@dataclass
class DomainScore:
    root_id: str
    name: str
    earned_points: float
    total_points: float
    percentage: float
    missing_critical: int


@dataclass
class GapReport:
    company_name: str
    scanned_at: str
    infrastructure_score: float
    total_required: int
    present_current_count: int
    present_stale_count: int
    duplicate_count: int
    missing_count: int
    misplaced_count: int
    domain_scores: List[DomainScore]
    immediate_blockers: List[GapItem]
    items: List[GapItem]


class GapAnalyzer:
    def __init__(
        self,
        ref_time: Optional[datetime.datetime] = None,
        rules_data: Optional[Dict[str, Any]] = None,
    ):
        self.ref_time = ref_time or datetime.datetime.now(datetime.timezone.utc)
        self._placement = placement_policy(rules_data or load_rules_data())

    def analyze(self, resolver_report: ResolutionReport, inventory: InventorySnapshot) -> GapReport:
        # Parse scanned_at or use ref_time
        scan_time_str = inventory.scan_metadata.get("scanned_at")
        if scan_time_str:
            try:
                base_time = datetime.datetime.fromisoformat(scan_time_str.replace("Z", "+00:00"))
            except ValueError:
                base_time = self.ref_time
        else:
            base_time = self.ref_time

        gap_items: List[GapItem] = []
        domain_buckets: Dict[str, Dict[str, Any]] = {}

        for art in resolver_report.artifacts:
            # We focus on required and recommended artifacts for gap scoring
            root_id = art.root
            root_name = art.root_name
            if root_id not in domain_buckets:
                domain_buckets[root_id] = {
                    "name": root_name,
                    "earned": 0.0,
                    "total": 0.0,
                    "missing_critical": 0,
                }

            matched = find_matching_files(art, inventory.files)
            weight = CRITICALITY_WEIGHTS.get(art.criticality, 1)

            if art.level == "required":
                domain_buckets[root_id]["total"] += weight
            elif art.level == "recommended":
                domain_buckets[root_id]["total"] += weight * 0.5

            status = "MISSING"
            remediation = ""
            days_stale = 0
            file_dicts: List[Dict[str, Any]] = []

            for f in matched:
                file_dicts.append({
                    "id": f.id,
                    "name": f.name,
                    "path": f.path,
                    "modified_time": f.modified_time,
                    "owners": f.owners,
                })

            if len(matched) == 0:
                status = "MISSING"
                if art.criticality == "high" and art.level == "required":
                    domain_buckets[root_id]["missing_critical"] += 1
                remediation = f"Compile canonical '{art.name}' into Google Drive; assign to {art.resolved_owner}."

            elif len(matched) > 1:
                status = "DUPLICATE_COLLISION"
                # Partial credit: content exists but needs consolidation
                if art.level == "required":
                    domain_buckets[root_id]["earned"] += weight * 0.5
                elif art.level == "recommended":
                    domain_buckets[root_id]["earned"] += weight * 0.25
                remediation = f"Consolidate {len(matched)} conflicting copies into a single canonical version in the Master Register."

            else:
                target_file = matched[0]
                mod_time = self._parse_iso(target_file.modified_time)
                diff_days = (base_time - mod_time).days if mod_time else 0

                # Check if stale
                if art.review_cadence_days and diff_days > art.review_cadence_days:
                    status = "PRESENT_STALE"
                    days_stale = diff_days - art.review_cadence_days
                    if art.level == "required":
                        domain_buckets[root_id]["earned"] += weight * 0.25
                    elif art.level == "recommended":
                        domain_buckets[root_id]["earned"] += weight * 0.125
                    remediation = f"File is {days_stale} days past review cadence ({art.review_cadence_days}d). {art.resolved_owner} must review and re-stamp."

                # Check if misplaced — rules-driven placement policy, not
                # substring heuristics ("99_Archive" canonical root stays canonical)
                elif placement_class(target_file.path, **self._placement) != "canonical":
                    status = "MISPLACED"
                    if art.level == "required":
                        domain_buckets[root_id]["earned"] += weight * 0.75
                    elif art.level == "recommended":
                        domain_buckets[root_id]["earned"] += weight * 0.375
                    remediation = f"File exists but is located in '{target_file.path}'. Move to canonical {art.root} {art.root_name} folder."

                else:
                    status = "PRESENT_CURRENT"
                    if art.level == "required":
                        domain_buckets[root_id]["earned"] += weight
                    elif art.level == "recommended":
                        domain_buckets[root_id]["earned"] += weight * 0.5
                    remediation = "Verified present and current. Maintain continuous monitoring."

            gap_items.append(
                GapItem(
                    artifact_id=art.id,
                    artifact_name=art.name,
                    root=art.root,
                    root_name=art.root_name,
                    level=art.level,
                    criticality=art.criticality,
                    status=status,
                    resolved_owner=art.resolved_owner,
                    matched_files=file_dicts,
                    review_cadence_days=art.review_cadence_days,
                    days_stale=days_stale,
                    remediation_action=remediation,
                    framework_mappings=art.framework_mappings,
                )
            )

        # Compute Domain Scores
        domain_scores: List[DomainScore] = []
        total_earned = 0.0
        total_possible = 0.0

        for root_id, b in sorted(domain_buckets.items()):
            tot = b["total"]
            earn = b["earned"]
            pct = round((earn / tot * 100), 1) if tot > 0 else 100.0
            domain_scores.append(
                DomainScore(
                    root_id=root_id,
                    name=b["name"],
                    earned_points=round(earn, 1),
                    total_points=round(tot, 1),
                    percentage=pct,
                    missing_critical=b["missing_critical"],
                )
            )
            total_earned += earn
            total_possible += tot

        overall_score = round((total_earned / total_possible * 100), 1) if total_possible > 0 else 0.0

        immediate_blockers = [
            item for item in gap_items
            if item.level == "required" and item.criticality == "high" and item.status in ("MISSING", "PRESENT_STALE", "DUPLICATE_COLLISION")
        ]

        present_current = sum(1 for i in gap_items if i.status == "PRESENT_CURRENT")
        present_stale = sum(1 for i in gap_items if i.status == "PRESENT_STALE")
        duplicates = sum(1 for i in gap_items if i.status == "DUPLICATE_COLLISION")
        missing = sum(1 for i in gap_items if i.status == "MISSING")
        misplaced = sum(1 for i in gap_items if i.status == "MISPLACED")

        return GapReport(
            company_name=resolver_report.company_name,
            scanned_at=base_time.strftime("%Y-%m-%d %H:%M UTC"),
            infrastructure_score=overall_score,
            total_required=resolver_report.required_count,
            present_current_count=present_current,
            present_stale_count=present_stale,
            duplicate_count=duplicates,
            missing_count=missing,
            misplaced_count=misplaced,
            domain_scores=domain_scores,
            immediate_blockers=immediate_blockers,
            items=gap_items,
        )

    def _parse_iso(self, dt_str: str) -> Optional[datetime.datetime]:
        if not dt_str:
            return None
        try:
            dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt


def format_gap_markdown(report: GapReport) -> str:
    lines = [
        f"# OpsGraph Gap Analysis & Infrastructure Report",
        f"",
        f"**Company:** {report.company_name}  ",
        f"**Audit Snapshot Date:** {report.scanned_at}  ",
        f"**Overall Infrastructure Readiness Score:** **`{report.infrastructure_score}%`**  ",
        f"",
        f"---",
        f"",
        f"## 1. Executive Summary & Status Breakdown",
        f"",
        f"| Metric | Count | Description |",
        f"|---|:---:|---|",
        f"| 🟢 **Present & Current** | **{report.present_current_count}** | Valid, recognized, and within review cadence |",
        f"| 🟡 **Present but Stale** | **{report.present_stale_count}** | Found in Drive, but exceeded review interval |",
        f"| 📦 **Misplaced** | **{report.misplaced_count}** | Found, but stored outside canonical folder hierarchy |",
        f"| ⚠️ **Duplicate Collisions** | **{report.duplicate_count}** | Multiple competing versions detected |",
        f"| 🔴 **Missing Required** | **{report.missing_count}** | Completely absent from Google Workspace |",
        f"",
        f"---",
        f"",
        f"## 2. Readiness Score by Operational Domain",
        f"",
        f"| Root | Domain | Earned / Total Pts | Readiness Score | Critical Gaps |",
        f"|:---:|---|:---:|:---:|:---:|",
    ]

    for d in report.domain_scores:
        progress_bar = _render_progress_bar(d.percentage)
        crit_badge = f"🔴 {d.missing_critical} Blocker(s)" if d.missing_critical > 0 else "🟢 Clear"
        lines.append(
            f"| `{d.root_id}` | {d.name} | {d.earned_points} / {d.total_points} | `{d.percentage}%` {progress_bar} | {crit_badge} |"
        )

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 3. Immediate Due Diligence & Audit Blockers ({len(report.immediate_blockers)})",
        f"",
        f"The following high-criticality items are **required for your active enterprise / fundraise / compliance triggers** and must be resolved before proceeding:",
        f"",
    ])

    for b in report.immediate_blockers:
        badge = "🔴 MISSING" if b.status == "MISSING" else ("🟡 STALE" if b.status == "PRESENT_STALE" else "⚠️ CONFLICT")
        fw_str = f" (*Maps to {', '.join(b.framework_mappings)}*)" if b.framework_mappings else ""
        lines.append(f"### {badge}: `{b.artifact_id}` — {b.artifact_name}{fw_str}")
        lines.append(f"- **Domain:** `{b.root} {b.root_name}` | **Assigned Owner:** `{b.resolved_owner}`")
        lines.append(f"- **Recommended Remediation:** {b.remediation_action}")
        if b.matched_files:
            lines.append(f"- **Observed File(s):**")
            for mf in b.matched_files:
                lines.append(f"  - `{mf['name']}` ({mf['path']}) — Modified: {mf['modified_time']}")
        lines.append("")

    lines.extend([
        f"---",
        f"",
        f"## 4. Comprehensive Required-State vs Observed-State Audit Table",
        f"",
        f"| ID | Artifact Name | Level | Status | Owner | Cadence | Observed File | Action |",
        f"|---|---|:---:|:---:|---|:---:|---|---|",
    ])

    for item in report.items:
        status_icon = {
            "PRESENT_CURRENT": "🟢 Current",
            "PRESENT_STALE": "🟡 Stale",
            "MISPLACED": "📦 Misplaced",
            "DUPLICATE_COLLISION": "⚠️ Duplicate",
            "MISSING": "🔴 Missing",
        }.get(item.status, item.status)

        observed = item.matched_files[0]["name"] if item.matched_files else "*(None)*"
        if len(item.matched_files) > 1:
            observed = f"{len(item.matched_files)} files (conflict)"

        lines.append(
            f"| `{item.artifact_id}` | {item.artifact_name} | {item.level} | {status_icon} | {item.resolved_owner} | {item.review_cadence_days}d | {observed} | {item.remediation_action} |"
        )

    return "\n".join(lines)


def _render_progress_bar(pct: float, width: int = 10) -> str:
    filled = int(round(pct / 100 * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"`[{bar}]`"


def main():
    parser = argparse.ArgumentParser(description="OpsGraph Gap Analysis Engine")
    parser.add_argument("profile", help="Path to company profile JSON")
    parser.add_argument("inventory", help="Path to scanned workspace inventory JSON")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")
    parser.add_argument("--output", help="Optional output path")

    args = parser.parse_args()

    profile_path = Path(args.profile)
    inventory_path = Path(args.inventory)

    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    scanner = WorkspaceScanner()
    inventory_snapshot = scanner.load_snapshot(inventory_path)

    resolver = StateResolver()
    resolution_report = resolver.resolve(profile_data)

    analyzer = GapAnalyzer()
    gap_report = analyzer.analyze(resolution_report, inventory_snapshot)

    if args.format == "json":
        data = asdict(gap_report)
        formatted = json.dumps(data, indent=2)
    else:
        formatted = format_gap_markdown(gap_report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(formatted)
        print(f"Gap Report generated at {out_path} (Score: {gap_report.infrastructure_score}%)")
    else:
        print(formatted)


if __name__ == "__main__":
    main()
