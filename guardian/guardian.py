#!/usr/bin/env python3
"""
OpsGraph — Company Guardian Engine (v0.1)
Continuous background governance and drift monitoring agent.
Observes workspace state, flags unindexed files, identifies expired policy review dates,
detects unowned documents and duplicate collisions, and generates the weekly Company Health Digest.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gap_engine.matching import find_matching_files, placement_class, placement_policy
from inventory.scanner import InventorySnapshot, WorkspaceScanner
from resolver.resolver import StateResolver


@dataclass
class DriftEvent:
    event_id: str
    severity: str  # HIGH, MEDIUM, LOW
    category: str  # UNINDEXED_FILE, STALE_REVIEW, UNOWNED_FILE, MISPLACED_FILE, DUPLICATE_COLLISION, MISSING_EVIDENCE
    title: str
    description: str
    affected_file: Optional[str]
    affected_artifact_id: Optional[str]
    assigned_owner: str
    remediation_proposal: str


@dataclass
class HealthDigest:
    company_name: str
    generated_at: str
    health_score: float
    total_drift_events: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    events: List[DriftEvent]
    action_queue: List[Dict[str, Any]]


class CompanyGuardian:
    def __init__(self, resolver: Optional[StateResolver] = None, ref_time: Optional[datetime.datetime] = None):
        self.resolver = resolver or StateResolver()
        self.ref_time = ref_time or datetime.datetime.now(datetime.timezone.utc)
        self._placement = placement_policy(self.resolver.rules_data)

    def audit(
        self,
        profile_data: Dict[str, Any],
        inventory: InventorySnapshot,
        master_register_entries: Optional[List[Dict[str, Any]]] = None,
    ) -> HealthDigest:
        resolution = self.resolver.resolve(profile_data)
        scan_time = self._parse_iso(inventory.scan_metadata.get("scanned_at")) or self.ref_time

        events: List[DriftEvent] = []
        counter = 1

        # 1. Map known canonical IDs and titles
        known_ids = {a.id for a in resolution.artifacts}
        known_artifacts = {a.id: a for a in resolution.artifacts}

        # Index registered files from master register if available
        registered_locations: Set[str] = set()
        if master_register_entries:
            for entry in master_register_entries:
                loc = entry.get("Location")
                if loc and loc not in ("Uncompiled", "Existing Workspace File"):
                    registered_locations.add(loc.strip())

        # 2. Check for Unindexed / Rogue Files in Drive
        for f in inventory.files:
            # Check if file has canonical prefix like CO-001 or is in master register
            has_id = any(art_id in f.name for art_id in known_ids)
            is_registered = any(reg_loc in f.path for reg_loc in registered_locations)

            # Ignore system files / audit logs
            if f.name in ("compiler_audit_log.json", "CO-001_Master_Document_Register.csv", "CO-001_Master_Document_Register.json"):
                continue

            if not has_id and not is_registered:
                # If file looks like a policy, contract, or register created without an ID
                lower_name = f.name.lower()
                looks_like_governed = any(
                    kw in lower_name
                    for kw in ["policy", "agreement", "contract", "register", "checklist", "procedure", "nda", "msa", "dpa"]
                )
                if looks_like_governed:
                    events.append(
                        DriftEvent(
                            event_id=f"DRIFT-{counter:03d}",
                            severity="MEDIUM",
                            category="UNINDEXED_FILE",
                            title=f"Unindexed Governed File: '{f.name}'",
                            description=f"File '{f.name}' appears to be a governed document but lacks a canonical ID and entry in the Master Document Register.",
                            affected_file=f.path,
                            affected_artifact_id=None,
                            assigned_owner=f.owners[0] if f.owners else "COO / Founder",
                            remediation_proposal=f"Assign canonical ID, register in Master Document Register, and move into appropriate root folder.",
                        )
                    )
                    counter += 1

            # 3. Check for Unowned or External Owner Files
            if not f.owners or any("contractor" in o.lower() or "former" in o.lower() for o in f.owners):
                events.append(
                    DriftEvent(
                        event_id=f"DRIFT-{counter:03d}",
                        severity="HIGH",
                        category="UNOWNED_FILE",
                        title=f"Unowned or Orphaned Document: '{f.name}'",
                        description=f"File '{f.name}' is owned by '{', '.join(f.owners) if f.owners else 'None'}' which lacks an active corporate owner.",
                        affected_file=f.path,
                        affected_artifact_id=None,
                        assigned_owner="COO / Founder",
                        remediation_proposal="Reassign document ownership to active functional lead.",
                    )
                )
                counter += 1

            # 4. Check for Misplaced Files — rules-driven placement policy
            if placement_class(f.path, **self._placement) != "canonical":
                events.append(
                    DriftEvent(
                        event_id=f"DRIFT-{counter:03d}",
                        severity="LOW",
                        category="MISPLACED_FILE",
                        title=f"Misplaced File in '{f.path}'",
                        description=f"Document '{f.name}' is stored in an unmanaged folder outside the canonical taxonomy hierarchy.",
                        affected_file=f.path,
                        affected_artifact_id=None,
                        assigned_owner=f.owners[0] if f.owners else "Founder / CEO",
                        remediation_proposal="Move file into its designated numbered taxonomy folder.",
                    )
                )
                counter += 1

        # 5. Check for Policy Review Cadence Expirations & Collisions across Governed Artifacts
        for art in resolution.artifacts:
            matched_files = find_matching_files(art, inventory.files)

            if len(matched_files) > 1:
                events.append(
                    DriftEvent(
                        event_id=f"DRIFT-{counter:03d}",
                        severity="HIGH" if art.criticality == "high" else "MEDIUM",
                        category="DUPLICATE_COLLISION",
                        title=f"Version Collision for `{art.id}` ({art.name})",
                        description=f"Detected {len(matched_files)} competing copies for {art.name} in Drive ({', '.join(f.name for f in matched_files)}).",
                        affected_file=matched_files[0].path,
                        affected_artifact_id=art.id,
                        assigned_owner=art.resolved_owner,
                        remediation_proposal="Archive superseded draft and designate the canonical master file.",
                    )
                )
                counter += 1

            elif len(matched_files) == 1:
                target_file = matched_files[0]
                mod_time = self._parse_iso(target_file.modified_time)
                if mod_time:
                    diff_days = (scan_time - mod_time).days
                    if art.review_cadence_days and diff_days > art.review_cadence_days:
                        overdue = diff_days - art.review_cadence_days
                        events.append(
                            DriftEvent(
                                event_id=f"DRIFT-{counter:03d}",
                                severity="HIGH" if art.criticality == "high" else "MEDIUM",
                                category="STALE_REVIEW",
                                title=f"Overdue Review: `{art.id}` {art.name}",
                                description=f"Document review is {overdue} days overdue (cadence: {art.review_cadence_days}d; last modified {diff_days}d ago).",
                                affected_file=target_file.path,
                                affected_artifact_id=art.id,
                                assigned_owner=art.resolved_owner,
                                remediation_proposal=f"Accountable owner ({art.resolved_owner}) must complete review and update review date.",
                            )
                        )
                        counter += 1

        # 6. Calculate Health Score
        # Start at 100%, deduct based on drift events: High = -6%, Medium = -3%, Low = -1%
        high_count = sum(1 for e in events if e.severity == "HIGH")
        med_count = sum(1 for e in events if e.severity == "MEDIUM")
        low_count = sum(1 for e in events if e.severity == "LOW")

        penalty = (high_count * 6.0) + (med_count * 3.0) + (low_count * 1.0)
        health_score = max(0.0, round(100.0 - penalty, 1))

        # Format action queue
        action_queue = [
            {
                "id": e.event_id,
                "priority": e.severity,
                "task": e.remediation_proposal,
                "owner": e.assigned_owner,
                "target": e.affected_file or e.affected_artifact_id or "Workspace",
            }
            for e in events
        ]

        return HealthDigest(
            company_name=resolution.company_name,
            generated_at=scan_time.strftime("%Y-%m-%d %H:%M UTC"),
            health_score=health_score,
            total_drift_events=len(events),
            high_severity_count=high_count,
            medium_severity_count=med_count,
            low_severity_count=low_count,
            events=events,
            action_queue=action_queue,
        )

    def _parse_iso(self, dt_str: Optional[str]) -> Optional[datetime.datetime]:
        if not dt_str:
            return None
        try:
            dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt


def load_register_entries(reg_path: Path) -> List[Dict[str, Any]]:
    """Load Master Document Register entries from JSON or CSV output by the compiler.

    Handles both the legacy flat-list JSON format and the versioned envelope
    ({"register_version", "provenance", "entries"}) written since ruleset 0.3.
    """
    suffix = reg_path.suffix.lower()
    if suffix == ".json":
        with open(reg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get("entries", [])
        return data
    if suffix == ".csv":
        with open(reg_path, "r", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    raise ValueError(f"Unsupported register format '{suffix}' (expected .json or .csv): {reg_path}")


def format_health_digest_markdown(digest: HealthDigest) -> str:
    lines = [
        f"# Company Guardian — Weekly Health Digest",
        f"",
        f"**Company:** {digest.company_name}  ",
        f"**Audit Snapshot Date:** {digest.generated_at}  ",
        f"**Current Operational Health Score:** **`{digest.health_score}%`**  ",
        f"",
        f"---",
        f"",
        f"## 1. Executive Summary & Drift Indicators",
        f"",
        f"| Severity | Active Events | Impact / Meaning |",
        f"|:---:|:---:|---|",
        f"| 🔴 **HIGH** | **{digest.high_severity_count}** | Immediate deal/audit risk (unowned files, collisions, critical policy expiry) |",
        f"| 🟡 **MEDIUM** | **{digest.medium_severity_count}** | Operational drift (unindexed files, standard review overdue) |",
        f"| ⚪ **LOW** | **{digest.low_severity_count}** | Filing hygiene (misplaced files in backup folders) |",
        f"| 📊 **TOTAL** | **{digest.total_drift_events}** | Total actionable exceptions flagged |",
        f"",
        f"---",
        f"",
        f"## 2. Priority Exception Queue ({len(digest.action_queue)} Actionable Items)",
        f"",
        f"| Priority | Action / Task | Responsible Owner | Target File / Artifact |",
        f"|:---:|---|:---:|---|",
    ]

    for item in digest.action_queue:
        badge = "🔴 HIGH" if item["priority"] == "HIGH" else ("🟡 MED" if item["priority"] == "MEDIUM" else "⚪ LOW")
        lines.append(
            f"| {badge} | {item['task']} | `{item['owner']}` | `{item['target']}` |"
        )

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 3. Detailed Drift Events Log",
        f"",
    ])

    for ev in digest.events:
        sev_badge = "🔴 HIGH" if ev.severity == "HIGH" else ("🟡 MEDIUM" if ev.severity == "MEDIUM" else "⚪ LOW")
        lines.append(f"### [{ev.event_id}] {ev.title} ({sev_badge})")
        lines.append(f"- **Category:** `{ev.category}`")
        lines.append(f"- **Accountable Owner:** `{ev.assigned_owner}`")
        lines.append(f"- **Description:** {ev.description}")
        if ev.affected_file:
            lines.append(f"- **Location:** `{ev.affected_file}`")
        lines.append(f"- **Proposed Action:** `{ev.remediation_proposal}`")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="OpsGraph Guardian Monitoring Engine")
    parser.add_argument("profile", help="Path to company profile JSON")
    parser.add_argument("inventory", help="Path to workspace inventory JSON")
    parser.add_argument("--register", default=None, help="Optional path to master register CSV or JSON")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")
    parser.add_argument("--output", help="Optional output path")

    args = parser.parse_args()

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
        data = asdict(digest)
        formatted = json.dumps(data, indent=2)
    else:
        formatted = format_health_digest_markdown(digest)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(formatted)
        print(f"Guardian Health Digest generated at {out_path} (Score: {digest.health_score}%)")
    else:
        print(formatted)


if __name__ == "__main__":
    main()
