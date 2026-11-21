#!/usr/bin/env python3
"""
Profile builder for `opsgraph init`.

Produces a minimal schema-valid company profile from a handful of answers.
Anything the caller didn't supply lands in `provenance.unanswered` — the
same field the intake flow uses for questions the founder couldn't answer,
so a generated profile is honest about what was asked vs defaulted.
"""

import datetime
from typing import Any, Dict, List, Optional

TRIGGER_CHOICES = [
    "enterprise_sales", "fundraise_data_room", "security_questionnaires",
    "soc2_iso", "audit", "rapid_hiring", "international_expansion",
    "leadership_handoff",
]
STAGE_CHOICES = ["idea", "pre_seed", "seed", "series_a", "series_b_plus", "bootstrapped"]
MODEL_CHOICES = ["b2b_saas", "ai_software", "software_enabled_services", "b2c",
                 "marketplace", "ecommerce", "professional_services", "other"]
CUSTOMER_TYPE_CHOICES = ["enterprise", "mid_market", "smb", "consumer", "government", "mixed"]

DEFAULT_TRIGGERS = ["enterprise_sales", "security_questionnaires"]


def build_profile(
    legal_name: str,
    domain: str,
    funding_stage: str,
    employee_count: int,
    model: str = "b2b_saas",
    customer_type: str = "enterprise",
    sector: Optional[str] = None,
    description: Optional[str] = None,
    triggers: Optional[List[str]] = None,
    jurisdiction: str = "Delaware",
    countries: Optional[List[str]] = None,
    contractors: int = 0,
    currently_raising: bool = False,
) -> Dict[str, Any]:
    """Assemble a schema-valid profile; defaulted fields go to unanswered."""
    unanswered: List[str] = []
    if funding_stage not in STAGE_CHOICES:
        raise ValueError(f"stage must be one of {STAGE_CHOICES}")
    if model not in MODEL_CHOICES:
        raise ValueError(f"model must be one of {MODEL_CHOICES}")
    if customer_type not in CUSTOMER_TYPE_CHOICES:
        raise ValueError(f"customer-type must be one of {CUSTOMER_TYPE_CHOICES}")

    triggers = triggers if triggers is not None else list(DEFAULT_TRIGGERS)
    if not triggers:
        raise ValueError("at least one trigger is required")
    bad = [t for t in triggers if t not in TRIGGER_CHOICES]
    if bad:
        raise ValueError(f"unknown triggers {bad}; choices: {TRIGGER_CHOICES}")
    if sector is None:
        sector = "Technology"
        unanswered.append("business.sector")
    if description is None:
        description = f"{legal_name} is a {model.replace('_', ' ')} company."
        unanswered.append("business.description")

    return {
        "company": {
            "legal_name": legal_name,
            "website": f"https://{domain}",
            "incorporation_jurisdiction": jurisdiction,
            "operating_countries": countries or ["US"],
        },
        "stage": {
            "funding_stage": funding_stage,
            "employee_count": employee_count,
            "contractor_count": contractors,
            "currently_raising": currently_raising,
        },
        "business": {
            "model": model,
            "sector": sector,
            "description": description,
            "customer_type": customer_type,
            "regulated_activities": [],
        },
        "workspace": {
            "platform": "google_workspace",
            "domain": domain,
            "shared_drives": [],
            "key_folders": [],
            "access_boundaries": "metadata-only scan; creates only under approved roots",
        },
        "triggers": triggers,
        "permissions": {
            "read_metadata": True,
            "read_content_roots": [],
            "create_roots": ["OpsGraph"],
            "move_rename": "propose_only",
            "delete": "never",
            "external_sharing_or_permission_changes": "never",
            "auto_execute_allowed": [],
        },
        "governance": {"require_compile_approval": True},
        "provenance": {
            "collected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "collected_by": "opsgraph init",
            "unanswered": unanswered,
        },
    }
