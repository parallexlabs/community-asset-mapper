"""Quality engine tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from community_asset_mapper.adapters.bc_hospitals import row_to_record
from community_asset_mapper.quality.engine import run_quality_checks, write_backlog_report


def test_missing_hours_issue() -> None:
    record = row_to_record({"FACILITY_NAME": "Test", "CITY": "Vancouver"})
    issues = run_quality_checks([record])
    rules = {i.rule for i in issues}
    assert "missing_hours" in rules


def test_pii_column_detected() -> None:
    record = row_to_record({"FACILITY_NAME": "Test", "CITY": "Vancouver"})
    record.source_row["client_name"] = "Secret"
    issues = run_quality_checks([record])
    assert any(i.rule == "pii_column" for i in issues)


def test_stale_verify() -> None:
    record = row_to_record({"FACILITY_NAME": "Test", "CITY": "Vancouver"})
    record.service.last_verified = datetime.now(UTC) - timedelta(days=400)
    issues = run_quality_checks([record])
    assert any(i.rule == "stale_verify" for i in issues)


def test_bad_geocode_missing_coords() -> None:
    record = row_to_record({"FACILITY_NAME": "Test", "CITY": "Vancouver"})
    record.location.latitude = None
    issues = run_quality_checks([record])
    assert any(i.rule == "bad_geocode" for i in issues)


def test_write_backlog_report(tmp_path: Path) -> None:
    record = row_to_record({"FACILITY_NAME": "Test", "CITY": "Vancouver"})
    issues = run_quality_checks([record])
    json_path, md_path = write_backlog_report(issues, tmp_path)
    assert json_path.exists()
    assert md_path.exists()
    assert "Data Quality Backlog" in md_path.read_text(encoding="utf-8")
