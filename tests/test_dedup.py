"""Deduplication tests."""

from __future__ import annotations

from pathlib import Path

from community_asset_mapper.adapters.bc_hospitals import row_to_record
from community_asset_mapper.dedup.engine import (
    apply_merges,
    propose_duplicates,
    review_group,
    write_audit_log,
)
from community_asset_mapper.dedup.scoring import jaro_winkler


def test_jaro_winkler_identical() -> None:
    assert jaro_winkler("test", "test") == 1.0


def test_jaro_winkler_different() -> None:
    assert jaro_winkler("abc", "xyz") < 0.5


def test_jaro_winkler_empty() -> None:
    assert jaro_winkler("", "abc") == 0.0


def test_propose_duplicates_finds_similar() -> None:
    a = row_to_record(
        {
            "FACILITY_NAME": "Example Hospital",
            "ORGANIZATION_NAME": "Example Organization",
            "ADDRESS": "1 Example Avenue",
            "CITY": "Vancouver",
            "POSTAL_CODE": "V5Z 1M9",
            "LATITUDE": "49.2612",
            "LONGITUDE": "-123.1207",
        }
    )
    b = row_to_record(
        {
            "FACILITY_NAME": "Example Hospital",
            "ORGANIZATION_NAME": "Example Organization",
            "ADDRESS": "1 Example Ave",
            "CITY": "Vancouver",
            "POSTAL_CODE": "V5Z 1M9",
            "LATITUDE": "49.2612",
            "LONGITUDE": "-123.1207",
        }
    )
    groups = propose_duplicates([a, b], threshold=0.5)
    assert len(groups) >= 1
    assert "organization.name" in groups[0].matched_fields


def test_review_group() -> None:
    a = row_to_record({"FACILITY_NAME": "A", "CITY": "Vancouver"})
    b = row_to_record({"FACILITY_NAME": "A", "CITY": "Vancouver", "POSTAL_CODE": "V5Z 1M9"})
    groups = propose_duplicates([a, b], threshold=0.5)
    if groups:
        summary = review_group(groups[0])
        assert "score=" in summary


def test_apply_merges(tmp_path: Path) -> None:
    row = {"FACILITY_NAME": "Same Hospital", "CITY": "Vancouver", "POSTAL_CODE": "V5Z 1M9"}
    a = row_to_record(row)
    b = row_to_record(row)
    groups = propose_duplicates([a, b], threshold=0.5)
    for g in groups:
        g.recommended_action = "merge"
    kept, audit = apply_merges([a, b], groups)
    assert len(kept) == 1
    write_audit_log(audit, tmp_path / "audit.jsonl")
    assert (tmp_path / "audit.jsonl").exists()
