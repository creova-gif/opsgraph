#!/usr/bin/env python3
"""
Company OS — State Resolver Engine (v0.2)
Deterministic required-state evaluation engine.
Maps a company profile (schema/company-profile.schema.json) against codified
operating graph rules (rules/core-artifacts.json) to compute required artifacts,
effective owners, review intervals, and dependency ordering.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

STAGE_HIERARCHY: Dict[str, int] = {
    "idea": 0,
    "pre_seed": 1,
    "seed": 2,
    "series_a": 3,
    "series_b_plus": 4,
    "bootstrapped": 2,
}

VALID_LEVELS = {"required", "recommended", "optional", "not_applicable"}
LEVEL_ORDER = {"required": 3, "recommended": 2, "optional": 1, "not_applicable": 0}


@dataclass
class ResolvedArtifact:
    id: str
    name: str
    root: str
    root_name: str
    type: str
    criticality: str
    owner_role: str
    resolved_owner: str
    review_cadence_days: int
    level: str
    reason: str
    depends_on: List[str] = field(default_factory=list)
    evidence_types: List[str] = field(default_factory=list)
    framework_mappings: List[str] = field(default_factory=list)
    why: str = ""


@dataclass
class ResolutionReport:
    company_name: str
    stage: str
    employee_count: int
    triggers: List[str]
    total_evaluated: int
    required_count: int
    recommended_count: int
    optional_count: int
    not_applicable_count: int
    compilation_order: List[str]
    artifacts: List[ResolvedArtifact]
    critical_path: List[str]


class StateResolver:
    def __init__(self, rules_path: Optional[Path] = None):
        if rules_path is None:
            # Default to rules/core-artifacts.json relative to project root
            base_dir = Path(__file__).resolve().parent.parent
            rules_path = base_dir / "rules" / "core-artifacts.json"
        
        self.rules_path = Path(rules_path)
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Artifact rules file not found: {self.rules_path}")
        
        with open(self.rules_path, "r", encoding="utf-8") as f:
            self.rules_data = json.load(f)
        
        self.taxonomy_roots: Dict[str, str] = self.rules_data.get("taxonomy_roots", {})
        self.artifacts_catalog: List[Dict[str, Any]] = self.rules_data.get("artifacts", [])

    def resolve(self, profile_data: Dict[str, Any]) -> ResolutionReport:
        company_info = profile_data.get("company", {})
        stage_info = profile_data.get("stage", {})
        business_info = profile_data.get("business", {})
        triggers: List[str] = profile_data.get("triggers", [])
        functions: List[Dict[str, Any]] = profile_data.get("functions", [])

        company_name = company_info.get("legal_name") or company_info.get("trading_name") or "Unnamed Venture"
        funding_stage = stage_info.get("funding_stage", "seed").lower()
        employee_count = stage_info.get("employee_count", 1)
        regulated_activities = business_info.get("regulated_activities", [])

        # Build functional owner mapping
        owner_map: Dict[str, str] = {}
        for fn in functions:
            fn_name = fn.get("name", "").lower()
            owner = fn.get("owner", "")
            if fn_name and owner:
                owner_map[fn_name] = owner

        resolved_list: List[ResolvedArtifact] = []

        for item in self.artifacts_catalog:
            art_id = item["id"]
            name = item["name"]
            root = item.get("root", "00")
            root_name = self.taxonomy_roots.get(root, "Unassigned")
            art_type = item.get("type", "record")
            criticality = item.get("criticality", "medium")
            owner_role = item.get("owner_role", "founder")
            cadence = item.get("review_cadence_days", 90)
            depends_on = item.get("depends_on", [])
            evidence_types = item.get("evidence_types", [])
            framework_mappings = item.get("framework_mappings", [])
            why = item.get("why", "")

            # Resolve responsible human role to concrete named owner if available
            resolved_owner = self._map_owner(owner_role, owner_map)

            # Determine requirement level
            req_block = item.get("requirement", {})
            default_level = req_block.get("default", "recommended")
            active_level = default_level
            reasons: List[str] = [f"Base default: {default_level}"]

            overrides = req_block.get("overrides", [])
            for ovr in overrides:
                condition = ovr.get("when", {})
                target_level = ovr.get("level", default_level)
                matched, cond_reason = self._evaluate_condition(
                    condition=condition,
                    funding_stage=funding_stage,
                    employee_count=employee_count,
                    triggers=triggers,
                    regulated_activities=regulated_activities,
                )
                if matched:
                    # If this condition elevates or specifies the level
                    active_level = target_level
                    reasons.append(f"Override applied: {cond_reason} -> {target_level}")

            final_reason = "; ".join(reasons)

            resolved_list.append(
                ResolvedArtifact(
                    id=art_id,
                    name=name,
                    root=root,
                    root_name=root_name,
                    type=art_type,
                    criticality=criticality,
                    owner_role=owner_role,
                    resolved_owner=resolved_owner,
                    review_cadence_days=cadence,
                    level=active_level,
                    reason=final_reason,
                    depends_on=depends_on,
                    evidence_types=evidence_types,
                    framework_mappings=framework_mappings,
                    why=why,
                )
            )

        # Compute compilation order via topological sort
        compilation_order = self._topological_sort(resolved_list)

        # Critical path: required artifacts that are marked high criticality
        critical_path = [
            a.id for a in resolved_list if a.level == "required" and a.criticality == "high"
        ]

        required_count = sum(1 for a in resolved_list if a.level == "required")
        recommended_count = sum(1 for a in resolved_list if a.level == "recommended")
        optional_count = sum(1 for a in resolved_list if a.level == "optional")
        na_count = sum(1 for a in resolved_list if a.level == "not_applicable")

        return ResolutionReport(
            company_name=company_name,
            stage=funding_stage,
            employee_count=employee_count,
            triggers=triggers,
            total_evaluated=len(resolved_list),
            required_count=required_count,
            recommended_count=recommended_count,
            optional_count=optional_count,
            not_applicable_count=na_count,
            compilation_order=compilation_order,
            artifacts=resolved_list,
            critical_path=critical_path,
        )

    def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        funding_stage: str,
        employee_count: int,
        triggers: List[str],
        regulated_activities: List[str],
    ) -> Tuple[bool, str]:
        # stage_gte
        if "stage_gte" in condition:
            target = condition["stage_gte"].lower()
            current_val = STAGE_HIERARCHY.get(funding_stage, 0)
            target_val = STAGE_HIERARCHY.get(target, 0)
            if current_val >= target_val:
                return True, f"Stage {funding_stage} >= {target}"
            return False, ""

        # stage_in
        if "stage_in" in condition:
            targets = [s.lower() for s in condition["stage_in"]]
            if funding_stage in targets:
                return True, f"Stage {funding_stage} in {targets}"
            return False, ""

        # employees_gte
        if "employees_gte" in condition:
            target = condition["employees_gte"]
            if employee_count >= target:
                return True, f"Headcount {employee_count} >= {target}"
            return False, ""

        # triggers_any
        if "triggers_any" in condition:
            targets = condition["triggers_any"]
            matched_triggers = [t for t in targets if t in triggers]
            if matched_triggers:
                return True, f"Matched trigger(s): {', '.join(matched_triggers)}"
            return False, ""

        # regulated_in
        if "regulated_in" in condition:
            targets = condition["regulated_in"]
            matched = [r for r in targets if r in regulated_activities]
            if matched:
                return True, f"Regulated activities: {', '.join(matched)}"
            return False, ""

        return False, ""

    def _map_owner(self, owner_role: str, owner_map: Dict[str, str]) -> str:
        role_lower = owner_role.lower()
        if "security" in role_lower or "cto" in role_lower:
            return owner_map.get("security") or owner_map.get("engineering") or "CTO / Security Lead"
        if "people" in role_lower or "hr" in role_lower:
            return owner_map.get("people") or owner_map.get("operations") or "People Lead / Founder"
        if "finance" in role_lower:
            return owner_map.get("finance") or owner_map.get("operations") or "Finance Lead / Founder"
        if "sales" in role_lower:
            return owner_map.get("sales") or "Head of Sales"
        if "legal" in role_lower:
            return owner_map.get("legal") or "External Counsel / Founder"
        if "coo" in role_lower or "operations" in role_lower:
            return owner_map.get("operations") or "COO / Founder"
        return "Founder / CEO"

    def _topological_sort(self, artifacts: List[ResolvedArtifact]) -> List[str]:
        id_set = {a.id for a in artifacts}
        graph: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = {a.id: 0 for a in artifacts}

        for a in artifacts:
            for dep in a.depends_on:
                if dep in id_set:
                    graph[dep].append(a.id)
                    in_degree[a.id] += 1

        queue = deque([node_id for node_id, deg in in_degree.items() if deg == 0])
        order: List[str] = []

        while queue:
            curr = queue.popleft()
            order.append(curr)
            for neighbor in graph[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If any remain due to unexpected cycles, append them
        for a in artifacts:
            if a.id not in order:
                order.append(a.id)

        return order


def format_markdown(report: ResolutionReport) -> str:
    lines = [
        f"# Company OS Required State Report: {report.company_name}",
        f"",
        f"> **Stage:** {report.stage.upper()} | **Headcount:** {report.employee_count} | **Triggers:** {', '.join(report.triggers) if report.triggers else 'None'}",
        f"> **Total Evaluated:** {report.total_evaluated} artifacts",
        f"",
        f"## 1. Requirement Summary",
        f"",
        f"| Level | Count | Share (%) |",
        f"|---|:---:|:---:|",
        f"| 🔴 **Required** | **{report.required_count}** | {round(report.required_count / report.total_evaluated * 100, 1)}% |",
        f"| 🟡 **Recommended** | **{report.recommended_count}** | {round(report.recommended_count / report.total_evaluated * 100, 1)}% |",
        f"| ⚪ **Optional** | **{report.optional_count}** | {round(report.optional_count / report.total_evaluated * 100, 1)}% |",
        f"| ⛔ **Not Applicable** | **{report.not_applicable_count}** | {round(report.not_applicable_count / report.total_evaluated * 100, 1)}% |",
        f"",
        f"## 2. Critical Path (High Criticality Required Nodes)",
        f"",
        f"The following **{len(report.critical_path)}** artifacts must be compiled first to unblock due diligence, enterprise questionnaires, and governance:",
        f"",
    ]

    for cid in report.critical_path:
        art = next(a for a in report.artifacts if a.id == cid)
        lines.append(f"- **`{art.id}` — {art.name}** (`{art.root_name}`) | *Owner:* {art.resolved_owner} | *Evidence:* `{', '.join(art.evidence_types)}`")

    lines.extend([
        f"",
        f"## 3. Recommended Compilation Order (Topological Sort)",
        f"",
        f"Foundational registers and control procedures are instantiated prior to dependent policies:",
        f"",
        f"```text",
        f" -> ".join(report.compilation_order),
        f"```",
        f"",
        f"## 4. Full Artifact Evaluation Table",
        f"",
        f"| ID | Name | Root | Level | Criticality | Assigned Owner | Review Cadence | Frameworks | Reason |",
        f"|---|---|---|:---:|:---:|---|:---:|---|---|",
    ])

    for art in report.artifacts:
        badge = "🔴 Required" if art.level == "required" else ("🟡 Recommended" if art.level == "recommended" else "⚪ Optional")
        frameworks_str = ", ".join(art.framework_mappings) if art.framework_mappings else "Internal"
        lines.append(
            f"| `{art.id}` | {art.name} | {art.root} {art.root_name} | {badge} | {art.criticality.capitalize()} | {art.resolved_owner} | {art.review_cadence_days}d | {frameworks_str} | {art.reason} |"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Company OS State Resolver Engine")
    parser.add_argument("profile", help="Path to company profile JSON file")
    parser.add_argument("--rules", default=None, help="Path to custom core-artifacts.json rules")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")
    parser.add_argument("--output", help="Optional output file path")

    args = parser.parse_args()

    profile_path = Path(args.profile)
    if not profile_path.exists():
        sys.stderr.write(f"Error: Profile file not found: {profile_path}\n")
        sys.exit(1)

    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    resolver = StateResolver(rules_path=Path(args.rules) if args.rules else None)
    report = resolver.resolve(profile_data)

    if args.format == "json":
        # Convert dataclasses to dict
        report_dict = asdict(report)
        formatted_output = json.dumps(report_dict, indent=2)
    else:
        formatted_output = format_markdown(report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(formatted_output)
        print(f"Report written to {out_path}")
    else:
        print(formatted_output)


if __name__ == "__main__":
    main()
