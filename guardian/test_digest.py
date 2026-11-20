#!/usr/bin/env python3
"""Tests for guardian digest deltas."""

import unittest

from guardian.digest import diff_digests, format_digest_delta


def _event(sev, cat, title, target=None, artifact=None):
    return {
        "event_id": "DRIFT-001",
        "severity": sev,
        "category": cat,
        "title": title,
        "affected_file": target,
        "affected_artifact_id": artifact,
        "assigned_owner": "COO",
    }


def _digest(events, health=80.0):
    return {
        "company_name": "Acme",
        "generated_at": "2026-11-20T00:00:00Z",
        "health_score": health,
        "total_drift_events": len(events),
        "events": events,
    }


class TestDigestDelta(unittest.TestCase):
    def test_new_and_resolved_events(self):
        prev = _digest([
            _event("HIGH", "UNINDEXED_FILE", "old drift", target="a.docx"),
            _event("LOW", "STALE_REVIEW", "stale", artifact="PE-002"),
        ], health=75.0)
        latest = _digest([
            _event("MEDIUM", "UNOWNED_FILE", "new drift", target="b.pdf"),
            _event("HIGH", "UNINDEXED_FILE", "old drift", target="a.docx"),
        ], health=70.0)

        d = diff_digests(prev, latest)
        self.assertEqual(d["health_delta"], -5.0)
        self.assertEqual(len(d["new_events"]), 1)
        self.assertEqual(d["new_events"][0]["title"], "new drift")
        self.assertEqual(len(d["resolved_events"]), 1)
        self.assertEqual(d["resolved_events"][0]["affected_artifact_id"], "PE-002")
        self.assertEqual(d["persistent_count"], 1)

    def test_event_identity_uses_category_and_target(self):
        """Same title at a different file is a different event."""
        prev = _digest([_event("LOW", "UNOWNED_FILE", "orphan", target="a.docx")])
        latest = _digest([_event("LOW", "UNOWNED_FILE", "orphan", target="b.docx")])
        d = diff_digests(prev, latest)
        self.assertEqual(len(d["new_events"]), 1)
        self.assertEqual(len(d["resolved_events"]), 1)
        self.assertEqual(d["persistent_count"], 0)

    def test_escalation_detected(self):
        prev = _digest([_event("LOW", "STALE_REVIEW", "stale", artifact="X-001")])
        latest = _digest([_event("HIGH", "STALE_REVIEW", "stale", artifact="X-001")])
        d = diff_digests(prev, latest)
        self.assertEqual(len(d["escalated_events"]), 1)
        self.assertEqual(d["persistent_count"], 1)

    def test_no_change(self):
        events = [_event("MEDIUM", "DUPLICATE_COLLISION", "dup", artifact="CO-001")]
        d = diff_digests(_digest(events, 80.0), _digest(events, 80.0))
        self.assertEqual(d["health_delta"], 0.0)
        self.assertEqual(d["new_events"], [])
        self.assertEqual(d["resolved_events"], [])
        self.assertEqual(d["persistent_count"], 1)

    def test_format_renders_sections(self):
        prev = _digest([_event("LOW", "STALE_REVIEW", "gone", artifact="Y-001")], 60.0)
        latest = _digest(
            [_event("HIGH", "MISSING_EVIDENCE", "new gap", artifact="Z-001")], 55.0
        )
        md = format_digest_delta(diff_digests(prev, latest))
        self.assertIn("60.0% → 55.0%", md)
        self.assertIn("New events", md)
        self.assertIn("Resolved", md)
        self.assertIn("new gap", md)


if __name__ == "__main__":
    unittest.main()
