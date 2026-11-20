#!/usr/bin/env python3
"""
OpsGraph — "Ask Company" deterministic Q&A (Mode A, Phase 4).

Answers questions about the operating graph using only engine outputs —
resolution, gap report, guardian digest. Every claim carries a citation
(artifact ID, domain, or drift event ID) so the answer is auditable.

This is the deterministic floor for Mode A. When the Consul contract is
live, synthesis can be layered on top; the retrieval and citation layer
built here stays the grounding source either way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from gap_engine.analyzer import GapAnalyzer, GapReport
from guardian.guardian import CompanyGuardian, HealthDigest
from inventory.scanner import InventorySnapshot
from resolver.resolver import ResolvedArtifact, ResolutionReport, StateResolver

_ARTIFACT_ID_RE = re.compile(r"\b[A-Z]{2}-\d{3}\b")
_TOKEN_RE = re.compile(r"[a-z0-9]+")

_INTENT_WORDS = {
    "score": ("score", "readiness", "ready", "percent", "health", "how are we"),
    "missing": ("missing", "don't have", "do not have", "lack", "need to create"),
    "stale": ("stale", "out of date", "outdated", "old", "overdue", "review"),
    "blockers": ("blocker", "blockers", "blocking", "diligence", "deal",
                 "urgent", "critical"),
    "drift": ("drift", "guardian", "changed", "events", "issues", "problems"),
    "owner": ("who owns", "owner", "responsible", "whose", "assigned"),
}

_MAX_LIST = 8


@dataclass
class Answer:
    question: str
    text: str
    citations: List[str] = field(default_factory=list)
    confidence: str = "high"  # "high" when grounded, "low" on fallback
    intent: str = "unknown"
    source: str = "deterministic"  # honest provenance — never "model" yet


def _tokens(text: str) -> set:
    return set(_TOKEN_RE.findall(text.lower()))


class CompanyAnswerer:
    """Deterministic question-answerer over profile + inventory."""

    def __init__(
        self,
        resolver: Optional[StateResolver] = None,
        analyzer: Optional[GapAnalyzer] = None,
        guardian: Optional[CompanyGuardian] = None,
    ):
        self.resolver = resolver or StateResolver()
        self.analyzer = analyzer or GapAnalyzer()
        self.guardian = guardian or CompanyGuardian()

    def ask(
        self,
        question: str,
        profile_data: Dict[str, Any],
        inventory: InventorySnapshot,
    ) -> Answer:
        resolution = self.resolver.resolve(profile_data)
        gap = self.analyzer.analyze(resolution, inventory)
        digest = self.guardian.audit(profile_data, inventory)

        artifact = self._match_artifact(question, resolution.artifacts)

        # Owner questions resolve through the matched artifact first.
        if artifact and self._has_intent(question, "owner"):
            return self._answer_owner(question, artifact, gap)

        if artifact:
            return self._answer_artifact(question, artifact, gap)

        intent = self._detect_intent(question)
        if intent == "score":
            return self._answer_score(question, gap)
        if intent == "missing":
            return self._answer_status(question, gap, "MISSING", "missing")
        if intent == "stale":
            return self._answer_status(question, gap, "PRESENT_STALE", "stale")
        if intent == "blockers":
            return self._answer_blockers(question, gap)
        if intent == "drift":
            return self._answer_drift(question, digest)
        if intent == "owner":
            return self._answer_owners(question, gap)

        return self._answer_fallback(question, gap)

    # -- intent + artifact matching --------------------------------------

    def _has_intent(self, question: str, intent: str) -> bool:
        q = question.lower()
        return any(w in q for w in _INTENT_WORDS[intent])

    def _detect_intent(self, question: str) -> Optional[str]:
        q = question.lower()
        for intent in ("score", "missing", "stale", "blockers", "drift", "owner"):
            if self._has_intent(question, intent):
                return intent
        return None

    def _match_artifact(
        self, question: str, artifacts: List[ResolvedArtifact]
    ) -> Optional[ResolvedArtifact]:
        by_id = {a.id: a for a in artifacts}
        m = _ARTIFACT_ID_RE.search(question.upper())
        if m and m.group(0) in by_id:
            return by_id[m.group(0)]

        q_tokens = _tokens(question) - {
            "do", "we", "have", "a", "the", "is", "our", "what", "who",
            "owns", "of", "does", "exist", "an",
        }
        best, best_ratio = None, 0.0
        for a in artifacts:
            name_tokens = _tokens(a.name)
            if not name_tokens:
                continue
            overlap = len(name_tokens & q_tokens) / len(name_tokens)
            if overlap > best_ratio:
                best, best_ratio = a, overlap
        return best if best_ratio >= 0.6 else None

    # -- answer builders --------------------------------------------------

    def _cite(self, item) -> str:
        return f"{item.artifact_id} — {item.artifact_name} [{item.status}]"

    def _answer_artifact(
        self, question: str, artifact: ResolvedArtifact, gap: GapReport
    ) -> Answer:
        item = next(
            (i for i in gap.items if i.artifact_id == artifact.id), None
        )
        if item is None:
            return Answer(
                question=question,
                text=f"{artifact.id} {artifact.name} was not evaluated in this gap report.",
                citations=[artifact.id],
                confidence="low",
                intent="artifact",
            )
        lines = [
            f"{item.artifact_id} — {item.artifact_name}",
            f"Status: {item.status}  ({item.root_name}, {item.criticality} criticality)",
            f"Owner: {item.resolved_owner}",
        ]
        cites = [self._cite(item)]
        if item.matched_files:
            for f in item.matched_files:
                lines.append(f"Matched file: {f['name']}")
                cites.append(f"file: {f['name']}")
        if item.status == "PRESENT_STALE":
            lines.append(f"{item.days_stale} days past review cadence.")
        if item.remediation_action:
            lines.append(f"Action: {item.remediation_action}")
        return Answer(
            question=question,
            text="\n".join(lines),
            citations=cites,
            intent="artifact",
        )

    def _answer_owner(
        self, question: str, artifact: ResolvedArtifact, gap: GapReport
    ) -> Answer:
        return Answer(
            question=question,
            text=(
                f"{artifact.resolved_owner} owns {artifact.id} {artifact.name} "
                f"(role: {artifact.owner_role}, review every {artifact.review_cadence_days} days)."
            ),
            citations=[artifact.id],
            intent="owner",
        )

    def _answer_score(self, question: str, gap: GapReport) -> Answer:
        worst = min(gap.domain_scores, key=lambda d: d.percentage)
        best = max(gap.domain_scores, key=lambda d: d.percentage)
        text = (
            f"Infrastructure readiness is {gap.infrastructure_score}% "
            f"({gap.company_name}, scanned {gap.scanned_at}). "
            f"Weakest domain: {worst.name} at {worst.percentage}%. "
            f"Strongest: {best.name} at {best.percentage}%. "
            f"{gap.missing_count} artifacts missing, "
            f"{gap.present_stale_count} stale, "
            f"{len(gap.immediate_blockers)} immediate blockers."
        )
        return Answer(
            question=question,
            text=text,
            citations=[f"domain:{worst.name}", f"domain:{best.name}"],
            intent="score",
        )

    def _answer_status(
        self, question: str, gap: GapReport, status: str, label: str
    ) -> Answer:
        items = [i for i in gap.items if i.status == status]
        if not items:
            return Answer(
                question=question,
                text=f"No {label} artifacts — every required item is current.",
                intent=label,
            )
        order = {"high": 0, "medium": 1, "low": 2}
        items.sort(key=lambda i: order.get(i.criticality, 3))
        shown = items[:_MAX_LIST]
        lines = [f"{len(items)} {label} artifact{'s' if len(items) != 1 else ''}:"]
        lines += [f"  {self._cite(i)} — {i.resolved_owner}" for i in shown]
        if len(items) > len(shown):
            lines.append(f"  …and {len(items) - len(shown)} more.")
        return Answer(
            question=question,
            text="\n".join(lines),
            citations=[i.artifact_id for i in shown],
            intent=label,
        )

    def _answer_blockers(self, question: str, gap: GapReport) -> Answer:
        blockers = gap.immediate_blockers
        if not blockers:
            return Answer(
                question=question,
                text="No immediate blockers — diligence and trigger readiness are clean.",
                intent="blockers",
            )
        lines = [f"{len(blockers)} immediate blockers:"]
        lines += [
            f"  {self._cite(i)} — {i.remediation_action}"
            for i in blockers[:_MAX_LIST]
        ]
        return Answer(
            question=question,
            text="\n".join(lines),
            citations=[i.artifact_id for i in blockers[:_MAX_LIST]],
            intent="blockers",
        )

    def _answer_drift(self, question: str, digest: HealthDigest) -> Answer:
        if digest.total_drift_events == 0:
            return Answer(
                question=question,
                text="No drift events — Guardian reports the workspace in tolerance.",
                intent="drift",
            )
        lines = [
            f"Guardian health {digest.health_score}% — {digest.total_drift_events} drift events "
            f"({digest.high_severity_count} high, {digest.medium_severity_count} medium, "
            f"{digest.low_severity_count} low):"
        ]
        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        events = sorted(digest.events, key=lambda e: order.get(e.severity, 3))
        for e in events[:_MAX_LIST]:
            lines.append(f"  [{e.severity}] {e.title} — owner: {e.assigned_owner}")
        return Answer(
            question=question,
            text="\n".join(lines),
            citations=[e.event_id for e in events[:_MAX_LIST]],
            intent="drift",
        )

    def _answer_owners(self, question: str, gap: GapReport) -> Answer:
        owners = {}
        for i in gap.items:
            owners.setdefault(i.resolved_owner, []).append(i)
        lines = ["Ownership across the operating graph:"]
        for owner, items in sorted(owners.items()):
            lines.append(f"  {owner}: {len(items)} artifacts")
        return Answer(
            question=question,
            text="\n".join(lines),
            citations=[i.artifact_id for i in gap.items[:_MAX_LIST]],
            intent="owner",
        )

    def _answer_fallback(self, question: str, gap: GapReport) -> Answer:
        return Answer(
            question=question,
            text=(
                "No deterministic answer for that question. I can answer about: "
                "readiness score, missing or stale artifacts, immediate blockers, "
                "artifact owners, and Guardian drift events. "
                "Name an artifact ID (e.g. CO-001) for its status."
            ),
            confidence="low",
            intent="fallback",
        )
