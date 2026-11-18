#!/usr/bin/env python3
"""
Unit tests for shared artifact/file matching and edge cases fixed post-v0.1:
canonical-ID matching, phrase-boundary alias matching, naive timestamps,
and Master Register CSV loading.
"""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from gap_engine.analyzer import GapAnalyzer
from gap_engine.matching import contains_phrase, find_matching_files, normalize, placement_class, placement_policy
from guardian.guardian import load_register_entries
from inventory.scanner import WorkspaceFile, InventorySnapshot
from resolver.resolver import ResolvedArtifact, StateResolver


def _file(name: str, path: str = "/", modified: str = "2026-10-01T00:00:00Z") -> WorkspaceFile:
    return WorkspaceFile(
        id=f"f-{name}", name=name, mime_type="text/plain", parent_id=None,
        path=path, created_time="2026-01-01T00:00:00Z", modified_time=modified,
        owners=["ops@acme.io"], size_bytes=10,
    )


def _artifact(art_id: str, name: str) -> ResolvedArtifact:
    return ResolvedArtifact(
        id=art_id, name=name, root="00", root_name="Company Control",
        type="register", criticality="high", owner_role="founder",
        resolved_owner="Founder", review_cadence_days=90, level="required",
        reason="test", depends_on=[], evidence_types=[], framework_mappings=[],
    )


class TestSharedMatcher(unittest.TestCase):
    def test_canonical_id_matches_filename(self):
        """ID matching must work on normalized names (hyphens become spaces)."""
        art = _artifact("CO-001", "Master Document Register")
        files = [_file("CO-001_Master_Document_Register.csv")]
        self.assertEqual(find_matching_files(art, files), files)

    def test_id_does_not_match_inside_other_words(self):
        """'taco 001' must not satisfy artifact 'CO-001'."""
        art = _artifact("CO-001", "Master Document Register")
        files = [_file("taco 001 plan.docx")]
        self.assertEqual(find_matching_files(art, files), [])

    def test_short_alias_respects_word_boundaries(self):
        """Alias 'sop' must not match 'esop' or 'soprano'."""
        art = _artifact("OP-001", "SOP Template")
        self.assertEqual(find_matching_files(art, [_file("esop grant notes.docx")]), [])
        self.assertEqual(find_matching_files(art, [_file("soprano recording.mp3")]), [])
        # ...but a real SOP file still matches
        self.assertEqual(len(find_matching_files(art, [_file("team sop v2.docx")])), 1)

    def test_normalize_and_contains_phrase(self):
        self.assertEqual(normalize("CO-001  Register!"), "co 001 register")
        self.assertTrue(contains_phrase("co 001 register", "co 001"))
        self.assertFalse(contains_phrase("taco 001", "co 001"))


class TestNaiveTimestamps(unittest.TestCase):
    def test_naive_modified_time_does_not_crash(self):
        """Naive (tz-less) modified_time is coerced to UTC instead of raising."""
        profile_path = BASE_DIR / "examples" / "seed-b2b-saas.json"
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
        resolution = StateResolver().resolve(profile)

        snap = InventorySnapshot(
            scan_metadata={"scanned_at": "2026-10-20T18:00:00Z"},
            folders=[],
            files=[_file("CO-002_Document_Control_Procedure.md",
                           modified="2026-10-01 09:30:00")],  # naive timestamp
        )
        report = GapAnalyzer().analyze(resolution, snap)
        self.assertGreater(report.infrastructure_score, 0)


class TestPlacementPolicy(unittest.TestCase):
    def test_archive_dirs_flag_archive_class(self):
        self.assertEqual(placement_class("/Old Backups & Shared/x.doc"), "archive")
        self.assertEqual(placement_class("/backups/2024/file.md"), "archive")

    def test_scratch_dirs_flag_scratch_class(self):
        self.assertEqual(placement_class("/downloads_personal/stuff.zip"), "scratch")
        self.assertEqual(placement_class("/Temp/file.tmp"), "scratch")

    def test_canonical_paths_untouched(self):
        # the canonical archive taxonomy root must NOT be flagged
        self.assertEqual(placement_class("/99_Archive/ES-001_old.md"), "canonical")
        self.assertEqual(placement_class("/05_Engineering_Security/ES-001.md"), "canonical")

    def test_component_match_not_substring(self):
        # "archivex" must not match "archive"
        self.assertEqual(placement_class("/archivex/file.md"), "canonical")

    def test_rules_driven_override(self):
        policy = placement_policy({"placement": {"archive_dirs": ["attic"], "scratch_dirs": ["bin"]}})
        self.assertEqual(placement_class("/attic/x", **policy), "archive")
        self.assertEqual(placement_class("/bin/x", **policy), "scratch")
        self.assertEqual(placement_class("/backups/x", **policy), "canonical")


class TestRegisterLoading(unittest.TestCase):
    def test_load_register_csv(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "register.csv"
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["Document_ID", "Location", "Status"])
                w.writeheader()
                w.writerow({"Document_ID": "CO-001", "Location": "00_Company_Control/x.csv", "Status": "DRAFT"})
            entries = load_register_entries(p)
            self.assertEqual(entries[0]["Document_ID"], "CO-001")

    def test_load_register_rejects_unknown_suffix(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "register.txt"
            p.write_text("nope")
            with self.assertRaises(ValueError):
                load_register_entries(p)


if __name__ == "__main__":
    unittest.main()
