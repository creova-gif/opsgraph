#!/usr/bin/env python3
"""
Company OS — Workspace Compiler Engine (v0.1)
Idempotent compiler that instantiates approved operating system infrastructure
directly into a target workspace directory (or Google Drive destination).
Creates canonical folder taxonomy, Master Document Register, and governed
artifact templates with strict provenance metadata and marked founder input placeholders.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gap_engine.analyzer import GapAnalyzer, GapItem, GapReport
from inventory.scanner import InventorySnapshot, WorkspaceScanner
from resolver.resolver import ResolutionReport, ResolvedArtifact, StateResolver


@dataclass
class CompilationPlan:
    company_name: str
    target_directory: str
    dry_run: bool
    folders_to_create: List[str]
    artifacts_to_compile: List[Dict[str, Any]]
    skipped_existing: List[str]
    total_actions: int


@dataclass
class CompilationResult:
    company_name: str
    executed_at: str
    target_directory: str
    dry_run: bool
    folders_created: List[str]
    artifacts_created: List[str]
    audit_log_path: str
    master_register_path: str


class WorkspaceCompiler:
    def __init__(self, resolver: Optional[StateResolver] = None, analyzer: Optional[GapAnalyzer] = None):
        self.resolver = resolver or StateResolver()
        self.analyzer = analyzer or GapAnalyzer()

    def plan(
        self,
        profile_data: Dict[str, Any],
        inventory: Optional[InventorySnapshot] = None,
        target_dir: str = "./workspace_target",
        approved_artifact_ids: Optional[Set[str]] = None,
    ) -> CompilationPlan:
        resolution = self.resolver.resolve(profile_data)

        # If no inventory provided, scan an empty snapshot (all artifacts will be missing)
        if inventory is None:
            inventory = InventorySnapshot(
                scan_metadata={"scanned_at": datetime.datetime.now(datetime.timezone.utc).isoformat()},
                folders=[],
                files=[],
            )

        gap_report = self.analyzer.analyze(resolution, inventory)

        # Determine folders to create
        folders_to_create: List[str] = []
        for root_code, root_name in self.resolver.taxonomy_roots.items():
            fld_name = f"{root_code}_{self._sanitize_folder_name(root_name)}"
            folders_to_create.append(fld_name)

        artifacts_to_compile: List[Dict[str, Any]] = []
        skipped_existing: List[str] = []

        # Map gap items by ID
        gap_map: Dict[str, GapItem] = {item.artifact_id: item for item in gap_report.items}

        for art in resolution.artifacts:
            # We compile required and recommended artifacts
            if art.level not in ("required", "recommended"):
                continue

            # If user provided a specific approval set, filter by it
            if approved_artifact_ids is not None and art.id not in approved_artifact_ids:
                continue

            gap_item = gap_map.get(art.id)
            if gap_item and gap_item.status == "PRESENT_CURRENT":
                skipped_existing.append(f"{art.id}: Already present and current ({gap_item.matched_files[0]['name']})")
                continue

            root_folder = f"{art.root}_{self._sanitize_folder_name(art.root_name)}"
            filename = f"{art.id}_{self._sanitize_filename(art.name)}.md"
            rel_path = f"{root_folder}/{filename}"

            artifacts_to_compile.append({
                "id": art.id,
                "name": art.name,
                "root": art.root,
                "root_name": art.root_name,
                "root_folder": root_folder,
                "filename": filename,
                "rel_path": rel_path,
                "type": art.type,
                "criticality": art.criticality,
                "owner_role": art.owner_role,
                "resolved_owner": art.resolved_owner,
                "review_cadence_days": art.review_cadence_days,
                "evidence_types": art.evidence_types,
                "framework_mappings": art.framework_mappings,
                "why": art.why,
                "gap_status": gap_item.status if gap_item else "MISSING",
            })

        return CompilationPlan(
            company_name=resolution.company_name,
            target_directory=target_dir,
            dry_run=True,
            folders_to_create=folders_to_create,
            artifacts_to_compile=artifacts_to_compile,
            skipped_existing=skipped_existing,
            total_actions=len(folders_to_create) + len(artifacts_to_compile) + 1,  # +1 for Master Register
        )

    def execute(
        self,
        profile_data: Dict[str, Any],
        inventory: Optional[InventorySnapshot] = None,
        target_dir: str = "./workspace_target",
        approved_artifact_ids: Optional[Set[str]] = None,
        dry_run: bool = False,
    ) -> CompilationResult:
        plan = self.plan(
            profile_data=profile_data,
            inventory=inventory,
            target_dir=target_dir,
            approved_artifact_ids=approved_artifact_ids,
        )

        target_path = Path(target_dir).resolve()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        resolution = self.resolver.resolve(profile_data)
        co_folder = self._master_register_folder(resolution)

        if dry_run:
            return CompilationResult(
                company_name=plan.company_name,
                executed_at=now_iso,
                target_directory=str(target_path),
                dry_run=True,
                folders_created=plan.folders_to_create,
                artifacts_created=[a["rel_path"] for a in plan.artifacts_to_compile],
                audit_log_path=str(target_path / "compiler_audit_log.json"),
                master_register_path=str(target_path / co_folder / "CO-001_Master_Document_Register.csv"),
            )

        # Execute physical creation
        target_path.mkdir(parents=True, exist_ok=True)
        created_folders: List[str] = []
        created_artifacts: List[str] = []

        # 1. Create Folder Taxonomy
        for fld in plan.folders_to_create:
            fld_path = target_path / fld
            fld_path.mkdir(parents=True, exist_ok=True)
            created_folders.append(fld)

        # 2. Instantiate Master Document Register in the CO-001 root folder
        co_dir = target_path / co_folder
        co_dir.mkdir(parents=True, exist_ok=True)
        master_reg_csv = co_dir / "CO-001_Master_Document_Register.csv"
        master_reg_json = co_dir / "CO-001_Master_Document_Register.json"

        register_rows = []
        for art in resolution.artifacts:
            # Determine lifecycle status
            compiled_item = next((a for a in plan.artifacts_to_compile if a["id"] == art.id), None)
            if compiled_item:
                status = "DRAFT_PENDING_APPROVAL"
                loc = compiled_item["rel_path"]
            elif any(s.startswith(f"{art.id}:") for s in plan.skipped_existing):
                status = "APPROVED_ACTIVE"
                loc = "Existing Workspace File"
            else:
                status = "OPTIONAL_NOT_COMPILED"
                loc = "Uncompiled"

            register_rows.append({
                "Document_ID": art.id,
                "Title": art.name,
                "Taxonomy_Root": f"{art.root} {art.root_name}",
                "Type": art.type,
                "Criticality": art.criticality.upper(),
                "Owner": art.resolved_owner,
                "Review_Cadence_Days": art.review_cadence_days,
                "Framework_Mappings": "; ".join(art.framework_mappings),
                "Evidence_Types": "; ".join(art.evidence_types),
                "Location": loc,
                "Status": status,
                "Last_Updated": now_iso[:10],
            })

        # Write CSV
        with open(master_reg_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(register_rows[0].keys()))
            writer.writeheader()
            writer.writerows(register_rows)

        # Write JSON
        with open(master_reg_json, "w", encoding="utf-8") as f:
            json.dump(register_rows, f, indent=2)

        created_artifacts.append(f"{co_folder}/CO-001_Master_Document_Register.csv")

        # 3. Compile Artifact Templates
        for item in plan.artifacts_to_compile:
            # If it's CO-001, we already created the CSV and JSON above
            if item["id"] == "CO-001":
                continue

            file_dest = target_path / item["rel_path"]
            content = self._generate_artifact_template(item, profile_data, now_iso)
            with open(file_dest, "w", encoding="utf-8") as f:
                f.write(content)
            created_artifacts.append(item["rel_path"])

        # 4. Write Immutable Audit Log
        audit_log = {
            "compilation_id": f"comp-{int(datetime.datetime.now().timestamp())}",
            "executed_at": now_iso,
            "company_name": plan.company_name,
            "target_directory": str(target_path),
            "ruleset_version": self.resolver.rules_data.get("version", "0.2"),
            "total_folders_created": len(created_folders),
            "total_artifacts_compiled": len(created_artifacts),
            "created_folders": created_folders,
            "created_artifacts": created_artifacts,
            "skipped_existing": plan.skipped_existing,
        }

        audit_path = target_path / "compiler_audit_log.json"
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(audit_log, f, indent=2)

        return CompilationResult(
            company_name=plan.company_name,
            executed_at=now_iso,
            target_directory=str(target_path),
            dry_run=False,
            folders_created=created_folders,
            artifacts_created=created_artifacts,
            audit_log_path=str(audit_path),
            master_register_path=str(master_reg_csv),
        )

    def _master_register_folder(self, resolution: ResolutionReport) -> str:
        """Folder that hosts the Master Document Register, derived from CO-001's taxonomy root."""
        co_artifact = next((a for a in resolution.artifacts if a.id == "CO-001"), None)
        if co_artifact is None:
            return "00_Company_Control"
        return f"{co_artifact.root}_{self._sanitize_folder_name(co_artifact.root_name)}"

    def _generate_artifact_template(self, item: Dict[str, Any], profile: Dict[str, Any], timestamp: str) -> str:
        company_name = profile.get("company", {}).get("legal_name", "Company OS Client")
        jurisdiction = profile.get("company", {}).get("incorporation_jurisdiction", "Delaware, USA")
        domain = profile.get("workspace", {}).get("domain", "company.io")

        fw_str = ", ".join(item["framework_mappings"]) if item["framework_mappings"] else "Internal Operations"
        ev_str = ", ".join(item["evidence_types"]) if item["evidence_types"] else "Record of Approval"

        provenance_header = f"""<!--
================================================================================
COMPANY OS GOVERNED OPERATIONAL ARTIFACT
================================================================================
Canonical Identifier : {item["id"]}
Document Title       : {item["name"]}
Taxonomy Root        : {item["root"]} {item["root_name"]}
Document Type        : {item["type"]}
Criticality          : {item["criticality"].upper()}
Accountable Owner    : {item["resolved_owner"]}
Review Cadence       : Every {item["review_cadence_days"]} days
Framework Mappings   : {fw_str}
Required Evidence    : {ev_str}
Rule Source          : core-artifacts.json ({self.resolver.rules_data.get("version", "0.2")})
Compiled At          : {timestamp}
Status               : DRAFT_PENDING_APPROVAL
================================================================================
DISCLAIMER: This document was compiled from codified operational rules.
It contains explicit placeholders for verified facts.
Review and approve prior to formal publication.
================================================================================
-->

# {company_name} — {item["name"]}

> **Document ID:** `{item["id"]}`  
> **Effective Date:** `[FOUNDER_INPUT_REQUIRED: Enter effective date, e.g., {timestamp[:10]}]`  
> **Review Cycle:** Every {item["review_cadence_days"]} days | **Next Review:** `[AUTO_CALCULATED: {timestamp[:10]} + {item["review_cadence_days"]}d]`  
> **Accountable Owner:** {item["resolved_owner"]}  
> **Target Frameworks:** `{fw_str}`

---

## 1. Purpose & Objectives
The purpose of this {item["type"]} is to establish clear, auditable operational standards for **{item["name"]}** across {company_name}.
{item["why"]}

---

## 2. Scope & Applicability
This document applies to all personnel, contractors, cloud environments, and systems operating under the `{domain}` domain and related corporate subsidiaries incorporated in **{jurisdiction}**.

---

## 3. Accountable Roles & RACI
* **Accountable Owner (A):** `{item["resolved_owner"]}`
* **Responsible Party (R):** `[FOUNDER_INPUT_REQUIRED: Primary operator responsible for daily execution]`
* **Consulted (C):** `[FOUNDER_INPUT_REQUIRED: Technical, legal, or finance advisors]`
* **Informed (I):** All employees of {company_name}

---

## 4. Operational Requirements & Standards
"""

        # Append type-specific body
        art_type = item["type"]
        if art_type == "register":
            content_body = f"""
| Entry ID | Date Logged | Description / Item Name | Owner | Status | Evidence Link | Next Review |
|:---:|:---:|---|:---:|:---:|:---:|:---:|
| `{item["id"]}-001` | `{timestamp[:10]}` | `[FOUNDER_INPUT_REQUIRED: Initial Entry]` | `{item["resolved_owner"]}` | ACTIVE | `[LINK]` | `{timestamp[:10]}` |
"""
        elif art_type == "checklist":
            content_body = f"""
### Phase 1: Preparation & Pre-requisites
- [ ] **Step 1:** `[FOUNDER_INPUT_REQUIRED: Actionable step 1]` — *Owner:* `{item["resolved_owner"]}`
- [ ] **Step 2:** `[FOUNDER_INPUT_REQUIRED: Actionable step 2]` — *Evidence:* `{ev_str}`

### Phase 2: Execution & Verification
- [ ] **Step 3:** `[FOUNDER_INPUT_REQUIRED: Actionable step 3]`
- [ ] **Step 4:** Secure required approvals and log completion in Master Document Register.
"""
        elif art_type == "template":
            content_body = f"""
### Meeting / Record Overview
* **Date & Time:** `[DATE_TIME]`
* **Attendees / Participants:** `[ATTENDEES]`
* **Primary Topic / Incident:** `[TOPIC]`

### Key Context & Decisions
1. **Context:** `[FOUNDER_INPUT_REQUIRED: Summary of situation]`
2. **Decision Taken:** `[FOUNDER_INPUT_REQUIRED: Specific decision with rationale]`
3. **Action Items:**
   - [ ] Action 1 — Assigned to: `[OWNER]` (Due: `[DATE]`)
"""
        else:
            content_body = f"""
### 4.1 Policy Statements
1. **Mandatory Controls:** `[FOUNDER_INPUT_REQUIRED: Codify company policy control 1]`
2. **Operational Safeguards:** `[FOUNDER_INPUT_REQUIRED: Codify company policy control 2]`
3. **Exceptions:** Any exception to this {item["type"]} must be submitted in writing and approved by `{item["resolved_owner"]}`.

### 4.2 Audit & Verification Evidence
To satisfy audit reviews for `{fw_str}`, the following evidence must be retained:
* `{ev_str}`
"""

        provenance_footer = f"""
---

## 5. Revision History & Approval Log

| Revision | Date | Author / Role | Changes Summary | Approved By |
|:---:|:---:|---|---|:---:|
| `v1.0` | `{timestamp[:10]}` | `{item["resolved_owner"]}` | Initial compiled draft via Company OS | `[PENDING_FOUNDER_SIGNOFF]` |
"""

        return provenance_header + content_body + provenance_footer

    def _sanitize_folder_name(self, name: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9]+", "_", name)
        return clean.strip("_")

    def _sanitize_filename(self, name: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9]+", "_", name)
        return clean.strip("_")


def format_plan_markdown(plan: CompilationPlan) -> str:
    lines = [
        f"# Company OS Workspace Compilation Plan",
        f"",
        f"**Target Company:** {plan.company_name}  ",
        f"**Target Directory:** `{plan.target_directory}`  ",
        f"**Dry Run Mode:** `{'Enabled' if plan.dry_run else 'Disabled'}`  ",
        f"",
        f"---",
        f"",
        f"## 1. Folder Taxonomy to Create ({len(plan.folders_to_create)})",
        f"",
    ]
    for fld in plan.folders_to_create:
        lines.append(f"- 📁 `{fld}/`")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 2. Artifacts to Compile ({len(plan.artifacts_to_compile)})",
        f"",
        f"| ID | Artifact Name | Root Folder | Criticality | Assigned Owner | Frameworks | Status |",
        f"|---|---|---|:---:|---|---|:---:|",
    ])

    for a in plan.artifacts_to_compile:
        fw = ", ".join(a["framework_mappings"]) if a["framework_mappings"] else "Internal"
        lines.append(
            f"| `{a['id']}` | {a['name']} | `{a['root_folder']}` | {a['criticality'].upper()} | {a['resolved_owner']} | {fw} | 🔴 {a['gap_status']} |"
        )

    if plan.skipped_existing:
        lines.extend([
            f"",
            f"---",
            f"",
            f"## 3. Skipped Artifacts (Already Present in Workspace)",
            f"",
        ])
        for s in plan.skipped_existing:
            lines.append(f"- 🟢 {s}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Company OS Workspace Compiler")
    parser.add_argument("profile", help="Path to company profile JSON")
    parser.add_argument("--inventory", default=None, help="Path to scanned workspace inventory JSON")
    parser.add_argument("--target", default="./workspace_compiled", help="Target output directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview compilation plan without creating files")
    parser.add_argument("--approve", nargs="+", help="Optional list of specific artifact IDs to compile")

    args = parser.parse_args()

    profile_path = Path(args.profile)
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    inventory_snapshot = None
    if args.inventory:
        inv_path = Path(args.inventory)
        scanner = WorkspaceScanner()
        inventory_snapshot = scanner.load_snapshot(inv_path)

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
        print(f"Compilation Complete for {result.company_name}!")
        print(f"  Target: {result.target_directory}")
        print(f"  Folders Created: {len(result.folders_created)}")
        print(f"  Artifacts Compiled: {len(result.artifacts_created)}")
        print(f"  Master Document Register: {result.master_register_path}")
        print(f"  Audit Log: {result.audit_log_path}")


if __name__ == "__main__":
    main()
