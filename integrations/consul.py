"""Client seam for the consul-core v1 HTTP contract (docs/architecture/CONSUL_INTEGRATION_CONTRACT.md).
HTTPConsulClient talks to a live Consul; StubConsulClient is the honest local fallback."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AgentRunResult:
    run_id: str
    status: str             # "completed" | "failed" | "pending"
    output: Dict[str, Any]  # skill-specific structured result
    provider: str
    simulation: bool
    usage: Dict[str, Any] = field(default_factory=dict)
    core_version: str = ""  # X-Consul-Core-Version response header; "" when absent


class ConsulUnavailable(Exception):
    pass


class ConsulClient:
    def run_agent(self, skill: str, inputs: dict, company_id: str,
                  idempotency_key: str, policy: dict | None = None) -> AgentRunResult:
        raise NotImplementedError


class HTTPConsulClient(ConsulClient):
    def __init__(self, base_url: str, token: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def run_agent(self, skill: str, inputs: dict, company_id: str,
                  idempotency_key: str, policy: dict | None = None) -> AgentRunResult:
        payload = {
            "skill": skill,
            "inputs": inputs,
            "company_id": company_id,
            "idempotency_key": idempotency_key,
        }
        if policy is not None:
            payload["policy"] = policy
        req = urllib.request.Request(
            f"{self.base_url}/v1/agent-runs",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                core_version = resp.headers.get("X-Consul-Core-Version", "")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            raise ConsulUnavailable(str(e)) from e
        # `simulation` is contract-required: a missing flag would let canned
        # output pass as real model work. Treat absence as a bad response.
        if "simulation" not in data:
            raise ConsulUnavailable("consul-core v1 response missing required field: simulation")
        return AgentRunResult(
            run_id=data.get("run_id", ""),
            status=data.get("status", ""),
            output=data.get("output", {}),
            provider=data.get("provider", ""),
            simulation=data["simulation"],
            usage=data.get("usage", {}),
            core_version=core_version,
        )


_PROPOSAL_TEMPLATES = {
    "MISPLACED_FILE": "Move '{target}' into its designated canonical taxonomy folder.",
    "UNINDEXED_FILE": "Register '{target}' in the Master Document Register and assign a canonical ID.",
    "STALE_REVIEW": "Schedule and complete a review of '{target}', then update the review date.",
    "UNOWNED_FILE": "Reassign '{target}' to an active functional owner.",
    "DUPLICATE_COLLISION": "Archive superseded copies of '{target}' and designate the canonical master file.",
    "MISSING_EVIDENCE": "Collect the missing evidence for '{target}' and file it under the canonical path.",
}

_PATCH_ACTIONS = {
    "MISPLACED_FILE": "move_file",
    "UNINDEXED_FILE": "register_file",
    "STALE_REVIEW": "schedule_review",
    "UNOWNED_FILE": "reassign_owner",
    "DUPLICATE_COLLISION": "deduplicate",
    "MISSING_EVIDENCE": "collect_evidence",
}


class StubConsulClient(ConsulClient):
    """Deterministic local stand-in used when no Consul endpoint is configured."""

    def run_agent(self, skill: str, inputs: dict, company_id: str,
                  idempotency_key: str, policy: dict | None = None) -> AgentRunResult:
        category = inputs.get("category") or inputs.get("event_type") or "UNKNOWN"
        target = (inputs.get("affected_file") or inputs.get("affected_artifact_id")
                  or inputs.get("title") or "the flagged item")
        if category in _PROPOSAL_TEMPLATES:
            proposal = _PROPOSAL_TEMPLATES[category].format(target=target)
        else:
            proposal = (
                f"Route '{target}' for manual review; no automated remediation "
                f"for category {category}."
            )
        output = {
            "proposal": proposal,
            "patch": {"action": _PATCH_ACTIONS.get(category, "manual_review"), "target": target},
            "rationale": (
                f"{category} drift event ({inputs.get('severity', 'UNKNOWN')} severity); "
                "deterministic fallback proposal for human review."
            ),
        }
        return AgentRunResult(
            run_id=f"stub-{idempotency_key}",
            status="completed",
            output=output,
            provider="simulation",
            simulation=True,
        )
