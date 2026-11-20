#!/usr/bin/env python3
"""
OpsGraph — deterministic remediation planner (Mode C floor).

Orders every actionable gap into a phased remediation plan:
P0 critical-path blockers → P1 high → P2 medium → P3 low, each phase
sorted by the resolver's dependency order so prerequisites land first.

When Consul planning arrives, the model sequences strategy; the order
constraints computed here remain the hard floor it must respect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from gap_engine.analyzer import GapReport
from resolver.resolver import ResolutionReport

_ACTIONABLE = {"MISSING", "PRESENT_STALE", "MISPLACED", "DUPLICATE_COLLISION"}
_PHASE_FOR = {"high": 1, "medium": 2, "low": 3}


@dataclass
class PlanStep:
    artifact_id: str
    name: str
    status: str
    owner: str
    action: str
    why: str
    phase: int
    blocked_by: List[str] = field(default_factory=list)


@dataclass
class RemediationPlan:
    company_name: str
    steps: List[PlanStep]
    phase_counts: Dict[int, int]


def build_plan(
    company_name: str,
    resolution: ResolutionReport,
    gap: GapReport,
) -> RemediationPlan:
    order_index = {aid: i for i, aid in enumerate(resolution.compilation_order)}
    critical_path = set(resolution.critical_path)
    artifact_by_id = {a.id: a for a in resolution.artifacts}
    actionable_ids = {
        i.artifact_id for i in gap.items if i.status in _ACTIONABLE
    }

    steps: List[PlanStep] = []
    for item in gap.items:
        if item.status not in _ACTIONABLE:
            continue
        art = artifact_by_id.get(item.artifact_id)
        phase = 0 if item.artifact_id in critical_path else _PHASE_FOR.get(
            item.criticality, 3
        )
        blocked_by = [
            d for d in (art.depends_on if art else []) if d in actionable_ids
        ]
        steps.append(
            PlanStep(
                artifact_id=item.artifact_id,
                name=item.artifact_name,
                status=item.status,
                owner=item.resolved_owner,
                action=item.remediation_action,
                why=art.reason if art else "",
                phase=phase,
                blocked_by=blocked_by,
            )
        )

    steps.sort(key=lambda s: (s.phase, order_index.get(s.artifact_id, 9999)))

    phase_counts: Dict[int, int] = {}
    for s in steps:
        phase_counts[s.phase] = phase_counts.get(s.phase, 0) + 1

    return RemediationPlan(
        company_name=company_name, steps=steps, phase_counts=phase_counts
    )


_PHASE_LABEL = {
    0: "P0 — Critical path (unblocks diligence)",
    1: "P1 — High criticality",
    2: "P2 — Medium criticality",
    3: "P3 — Low criticality",
}


def format_plan_markdown(plan: RemediationPlan) -> str:
    lines = [f"# Remediation Plan — {plan.company_name}", ""]
    total = len(plan.steps)
    if not total:
        lines.append("No actionable gaps — the operating graph is in tolerance.")
        return "\n".join(lines)
    lines.append(
        f"**{total} remediation steps** "
        + " · ".join(
            f"{_PHASE_LABEL[p].split(' — ')[0]}: {plan.phase_counts.get(p, 0)}"
            for p in sorted(plan.phase_counts)
        )
    )
    current = -1
    n = 0
    for s in plan.steps:
        if s.phase != current:
            current = s.phase
            lines.append("")
            lines.append(f"## {_PHASE_LABEL[current]}")
        n += 1
        deps = f"  _blocked by {', '.join(s.blocked_by)}_" if s.blocked_by else ""
        lines.append(f"{n}. **{s.artifact_id}** {s.name} — `{s.status}` — {s.owner}")
        lines.append(f"   {s.action}{deps}")
    return "\n".join(lines)
