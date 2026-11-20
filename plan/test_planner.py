#!/usr/bin/env python3
"""Tests for the deterministic remediation planner."""

import json
import unittest
from pathlib import Path

from gap_engine.analyzer import GapAnalyzer
from inventory.scanner import WorkspaceScanner
from plan.planner import build_plan, format_plan_markdown
from resolver.resolver import StateResolver


class TestRemediationPlanner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Path(__file__).resolve().parent.parent
        with open(base / "examples" / "seed-b2b-saas.json", encoding="utf-8") as f:
            cls.profile = json.load(f)
        cls.inventory = WorkspaceScanner().load_snapshot(
            base / "examples" / "sample-drive-inventory.json"
        )
        cls.resolution = StateResolver().resolve(cls.profile)
        cls.gap = GapAnalyzer().analyze(cls.resolution, cls.inventory)
        cls.plan = build_plan(cls.gap.company_name, cls.resolution, cls.gap)

    def test_only_actionable_items_planned(self):
        actionable = {
            i.artifact_id for i in self.gap.items
            if i.status in {"MISSING", "PRESENT_STALE", "MISPLACED", "DUPLICATE_COLLISION"}
        }
        self.assertEqual({s.artifact_id for s in self.plan.steps}, actionable)
        self.assertTrue(len(self.plan.steps) > 0)

    def test_critical_path_is_phase_zero(self):
        critical = set(self.resolution.critical_path)
        for s in self.plan.steps:
            if s.artifact_id in critical:
                self.assertEqual(s.phase, 0, f"{s.artifact_id} should be P0")

    def test_phase_ordering(self):
        phases = [s.phase for s in self.plan.steps]
        self.assertEqual(phases, sorted(phases), "steps must run P0 → P3")

    def test_dependencies_come_first_within_phase(self):
        order = {aid: i for i, aid in enumerate(self.resolution.compilation_order)}
        by_phase = {}
        for s in self.plan.steps:
            by_phase.setdefault(s.phase, []).append(order.get(s.artifact_id, 9999))
        for phase, seq in by_phase.items():
            self.assertEqual(seq, sorted(seq), f"phase {phase} not in compilation order")

    def test_blocked_by_lists_actionable_deps(self):
        actionable = {s.artifact_id for s in self.plan.steps}
        for s in self.plan.steps:
            for dep in s.blocked_by:
                self.assertIn(dep, actionable)

    def test_every_step_has_owner_and_action(self):
        for s in self.plan.steps:
            self.assertTrue(s.owner, f"{s.artifact_id} missing owner")
            self.assertTrue(s.action, f"{s.artifact_id} missing action")

    def test_markdown_renders_phases(self):
        md = format_plan_markdown(self.plan)
        self.assertIn("P0", md)
        self.assertIn("Remediation Plan", md)
        if self.plan.phase_counts.get(0):
            self.assertIn("Critical path", md)


if __name__ == "__main__":
    unittest.main()
