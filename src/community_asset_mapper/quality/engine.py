"""Quality backlog rule engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from community_asset_mapper.models.records import InternalRecord

PII_COLUMN_NAMES = frozenset(
    {
        "client_name",
        "client_id",
        "patient_name",
        "patient_id",
        "ssn",
        "sin",
        "date_of_birth",
        "dob",
    }
)

STALE_DAYS = 365


@dataclass
class QualityIssue:
    record_id: str
    rule: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "record_id": self.record_id,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
        }


def _check_pii_columns(record: InternalRecord) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for col in record.source_row:
        if col.lower() in PII_COLUMN_NAMES:
            issues.append(
                QualityIssue(
                    record_id=record.service.id,
                    rule="pii_column",
                    severity="critical",
                    message=f"PII column detected in source: {col}",
                )
            )
    return issues


def _check_missing_hours(record: InternalRecord) -> QualityIssue | None:
    if not record.service.hours:
        return QualityIssue(
            record_id=record.service.id,
            rule="missing_hours",
            severity="medium",
            message="Service hours not provided",
        )
    return None


def _check_bad_geocode(record: InternalRecord) -> QualityIssue | None:
    lat, lon = record.location.latitude, record.location.longitude
    if lat is None or lon is None:
        return QualityIssue(
            record_id=record.service.id,
            rule="bad_geocode",
            severity="high",
            message="Missing coordinates",
        )
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return QualityIssue(
            record_id=record.service.id,
            rule="bad_geocode",
            severity="high",
            message="Coordinates out of valid range",
        )
    if record.location.geocode and record.location.geocode.confidence < 0.5:
        return QualityIssue(
            record_id=record.service.id,
            rule="bad_geocode",
            severity="medium",
            message=f"Low geocode confidence: {record.location.geocode.confidence:.2f}",
        )
    return None


def _check_stale_verify(record: InternalRecord) -> QualityIssue | None:
    verified = record.service.last_verified
    if verified is None:
        return QualityIssue(
            record_id=record.service.id,
            rule="stale_verify",
            severity="medium",
            message="No verification date recorded",
        )
    if verified < datetime.now(UTC) - timedelta(days=STALE_DAYS):
        return QualityIssue(
            record_id=record.service.id,
            rule="stale_verify",
            severity="medium",
            message=f"Last verified over {STALE_DAYS} days ago",
        )
    return None


def run_quality_checks(records: list[InternalRecord]) -> list[QualityIssue]:
    """Run all quality rules against records."""
    issues: list[QualityIssue] = []
    for record in records:
        issues.extend(_check_pii_columns(record))
        for checker in (_check_missing_hours, _check_bad_geocode, _check_stale_verify):
            result = checker(record)
            if result:
                issues.append(result)
    return issues


def write_backlog_report(
    issues: list[QualityIssue], output_dir: Path, *, generated_at: datetime | None = None
) -> tuple[Path, Path]:
    """Write JSON and Markdown backlog reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "issue_count": len(issues),
        "issues": [i.to_dict() for i in issues],
    }
    json_path = output_dir / "quality_backlog.json"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    md_lines = [
        "# Data Quality Backlog",
        "",
        f"Generated: {payload['generated_at']}",
        f"Total issues: {len(issues)}",
        "",
        "| Record | Rule | Severity | Message |",
        "|--------|------|----------|---------|",
    ]
    for issue in issues:
        md_lines.append(
            f"| {issue.record_id} | {issue.rule} | {issue.severity} | {issue.message} |"
        )
    md_path = output_dir / "quality_backlog.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return json_path, md_path
