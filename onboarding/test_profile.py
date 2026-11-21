#!/usr/bin/env python3
"""Tests for the opsgraph init profile builder."""

import json
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from onboarding.profile import build_profile, DEFAULT_TRIGGERS
from store.validate import validate

SCHEMA = json.loads((BASE_DIR / "schema" / "company-profile.schema.json").read_text())


def _build(**overrides):
    args = dict(
        legal_name="NewCo Robotics, Inc.",
        domain="newco.dev",
        funding_stage="pre_seed",
        employee_count=5,
    )
    args.update(overrides)
    return build_profile(**args)


class TestBuildProfile(unittest.TestCase):
    def test_minimal_profile_validates(self):
        self.assertEqual(validate(_build(), SCHEMA), [])

    def test_full_answers_validate_and_clear_unanswered(self):
        p = _build(sector="Robotics", description="Fleet software",
                   triggers=["rapid_hiring"], currently_raising=True)
        self.assertEqual(validate(p, SCHEMA), [])
        self.assertEqual(p["provenance"]["unanswered"], [])
        self.assertEqual(p["stage"]["currently_raising"], True)
        self.assertEqual(p["triggers"], ["rapid_hiring"])

    def test_defaults_are_honest(self):
        p = _build()
        self.assertEqual(p["provenance"]["unanswered"],
                         ["business.sector", "business.description"])
        self.assertEqual(p["triggers"], DEFAULT_TRIGGERS)
        self.assertEqual(p["company"]["website"], "https://newco.dev")

    def test_safety_posture_is_schema_const(self):
        p = _build()
        self.assertEqual(p["permissions"]["move_rename"], "propose_only")
        self.assertEqual(p["permissions"]["delete"], "never")
        self.assertEqual(p["permissions"]["external_sharing_or_permission_changes"], "never")
        self.assertEqual(p["governance"]["require_compile_approval"], True)

    def test_bad_enums_rejected(self):
        with self.assertRaises(ValueError):
            _build(funding_stage="unicorn")
        with self.assertRaises(ValueError):
            _build(model="nft_marketplace")
        with self.assertRaises(ValueError):
            _build(triggers=["world_domination"])
        with self.assertRaises(ValueError):
            _build(triggers=[])


if __name__ == "__main__":
    unittest.main()
