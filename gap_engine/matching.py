#!/usr/bin/env python3
"""
OpsGraph — Shared Artifact/File Matching Utilities
Canonical ID/name/alias matching used by both the Gap Analyzer and the
Company Guardian. All matching is phrase-boundary aware so short aliases
(e.g. "sop", "bcp") cannot match inside unrelated words ("esop", "taco 001").
"""

from __future__ import annotations

import re
from typing import List

from inventory.scanner import WorkspaceFile
from resolver.resolver import ResolvedArtifact

# Artifact alias dictionary for fuzzy semantic matching against unstructured file names
ARTIFACT_ALIASES = {
    "CO-001": ["master document register", "master register", "document index", "document register"],
    "CO-002": ["document control procedure", "document control policy", "document standard"],
    "CO-003": ["company profile", "pitch deck", "company overview", "venture profile"],
    "CO-004": ["ownership matrix", "raci matrix", "raci", "roles and responsibilities"],
    "CO-005": ["policy register", "policy index", "policy list"],
    "GV-001": ["decision record log", "decision record", "decision log", "adr log"],
    "GV-002": ["risk register", "risk assessment", "risk log"],
    "GV-003": ["weekly leadership agenda", "leadership sync", "weekly sync notes", "leadership agenda"],
    "GV-004": ["monthly operating review", "operating review", "monthly mor"],
    "GV-005": ["annual objectives", "company okrs", "annual goals", "annual priorities"],
    "FN-001": ["vendor register", "vendor list", "software subscriptions", "vendor inventory"],
    "FN-002": ["approval matrix", "spending limits", "signature authority", "delegation of authority"],
    "FN-003": ["investor update template", "investor update", "investor newsletter", "investor report"],
    "FN-004": ["data room index", "data room", "due diligence index", "diligence checklist"],
    "FN-005": ["procurement checklist", "vendor onboarding checklist", "purchasing procedure"],
    "PE-001": ["hiring checklist", "interview checklist", "recruiting checklist"],
    "PE-002": ["onboarding checklist", "new hire onboarding", "employee onboarding"],
    "PE-003": ["offboarding checklist", "employee offboarding", "exit checklist", "termination checklist"],
    "PE-004": ["role charter template", "role charter", "job description template"],
    "PE-005": ["training register", "security training log", "compliance training log"],
    "ES-001": ["access register", "user access review", "access list", "system access log"],
    "ES-002": ["incident record template", "incident record", "incident postmortem", "post-mortem template", "postmortem"],
    "ES-003": ["change record template", "change record", "production change log", "rfc template"],
    "ES-004": ["architecture decision record template", "architecture decision record", "adr template"],
    "ES-005": ["security review calendar", "security calendar", "audit schedule"],
    "SC-001": ["customer security request tracker", "customer security faq", "caiq", "sig", "vsq answers", "security questionnaire"],
    "SC-002": ["contract obligations register", "contract register", "customer obligations", "sla register"],
    "SC-003": ["evidence index", "audit evidence index", "soc2 evidence", "controls evidence"],
    "OP-001": ["sop template", "standard operating procedure", "sop"],
    "OP-002": ["business continuity plan", "bcp", "disaster recovery plan", "dr plan"],
    "LG-001": ["policy gap report", "compliance gap report", "readiness report"],
}


def normalize(text: str) -> str:
    """Lowercase and collapse every non-alphanumeric run into a single space."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def contains_phrase(haystack_norm: str, needle_norm: str) -> bool:
    """Whole-phrase boundary match over normalized (space-separated) text."""
    return f" {needle_norm} " in f" {haystack_norm} "


def find_matching_files(art: ResolvedArtifact, files: List[WorkspaceFile]) -> List[WorkspaceFile]:
    """Match an artifact to workspace files by canonical ID, name, or alias."""
    matches: List[WorkspaceFile] = []
    art_id_clean = normalize(art.id)
    art_name_clean = normalize(art.name)
    aliases = ARTIFACT_ALIASES.get(art.id, [])

    for f in files:
        fname_clean = normalize(f.name)
        if contains_phrase(fname_clean, art_id_clean):
            matches.append(f)
            continue
        if contains_phrase(fname_clean, art_name_clean):
            matches.append(f)
            continue
        for alias in aliases:
            if contains_phrase(fname_clean, normalize(alias)):
                matches.append(f)
                break

    return matches
