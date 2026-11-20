#!/usr/bin/env python3
"""
OpsGraph — Guardian digest delta (Mode E deterministic floor).

Compares two recorded guardian runs for the same company and reports
what changed: new drift events, resolved events, persistent events,
and health-score movement. Event identity is (category, target) since
event_id is positional and unstable across runs.
"""

from __future__ import annotations

from typing import Any, Dict, List

_SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _event_key(event: Dict[str, Any]) -> str:
    target = event.get("affected_file") or event.get("affected_artifact_id") or event.get("title", "")
    return f"{event.get('category', 'UNKNOWN')}|{target}"


def diff_digests(previous: Dict[str, Any], latest: Dict[str, Any]) -> Dict[str, Any]:
    """Diff two guardian digest payloads (asdict(HealthDigest) shape)."""
    prev_events = {_event_key(e): e for e in previous.get("events", [])}
    latest_events = {_event_key(e): e for e in latest.get("events", [])}

    new_keys = [k for k in latest_events if k not in prev_events]
    resolved_keys = [k for k in prev_events if k not in latest_events]
    persistent_keys = [k for k in latest_events if k in prev_events]

    escalated = []
    for k in persistent_keys:
        before = _SEVERITY_ORDER.get(prev_events[k].get("severity"), 3)
        after = _SEVERITY_ORDER.get(latest_events[k].get("severity"), 3)
        if after < before:
            escalated.append(latest_events[k])

    def _sort(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(events, key=lambda e: _SEVERITY_ORDER.get(e.get("severity"), 3))

    prev_health = previous.get("health_score", 0.0)
    latest_health = latest.get("health_score", 0.0)

    return {
        "company_name": latest.get("company_name", ""),
        "health_before": prev_health,
        "health_after": latest_health,
        "health_delta": round(latest_health - prev_health, 1),
        "new_events": _sort([latest_events[k] for k in new_keys]),
        "resolved_events": _sort([prev_events[k] for k in resolved_keys]),
        "persistent_count": len(persistent_keys),
        "escalated_events": _sort(escalated),
        "generated_at": latest.get("generated_at", ""),
    }


def format_digest_delta(delta: Dict[str, Any]) -> str:
    """Markdown rendering of a digest delta."""
    lines = [f"# Guardian Delta — {delta['company_name']}", ""]
    sign = "+" if delta["health_delta"] > 0 else ""
    direction = "▲" if delta["health_delta"] > 0 else ("▼" if delta["health_delta"] < 0 else "=")
    lines.append(
        f"**Health: {delta['health_before']}% → {delta['health_after']}% "
        f"({direction} {sign}{delta['health_delta']}%)**"
    )
    lines.append("")
    lines.append(
        f"**{len(delta['new_events'])} new · {len(delta['resolved_events'])} resolved · "
        f"{delta['persistent_count']} persistent · {len(delta['escalated_events'])} escalated**"
    )

    for heading, key in (
        ("New events", "new_events"),
        ("Escalated", "escalated_events"),
        ("Resolved", "resolved_events"),
    ):
        events = delta[key]
        if not events:
            continue
        lines.append("")
        lines.append(f"## {heading}")
        for e in events:
            target = e.get("affected_file") or e.get("affected_artifact_id") or "—"
            lines.append(f"- [{e.get('severity', '?')}] {e.get('title', '?')}  (`{target}`)")
    return "\n".join(lines)
