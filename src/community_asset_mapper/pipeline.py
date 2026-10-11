"""Pipeline orchestration helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from community_asset_mapper.adapters.bc_hospitals import load_bc_hospitals
from community_asset_mapper.dedup.engine import apply_merges, propose_duplicates, write_audit_log
from community_asset_mapper.export.formats import export_csv, export_geojson
from community_asset_mapper.gap.metrics import compute_gap_metrics
from community_asset_mapper.geocode.fixture_provider import FixtureProvider
from community_asset_mapper.hsds.export import export_hsds_package
from community_asset_mapper.hsds.validate import validate_package
from community_asset_mapper.models.records import InternalRecord
from community_asset_mapper.quality.engine import run_quality_checks, write_backlog_report
from community_asset_mapper.site.generator import SiteConfig, build_site


def format_address(record: InternalRecord) -> str:
    addr = record.location.address
    if not addr:
        return record.location.name or record.organization.name
    parts = [p for p in [addr.address_1, addr.city, addr.state_province, addr.postal_code] if p]
    return ", ".join(parts)


def geocode_records(
    records: list[InternalRecord],
    fixtures_dir: Path,
) -> list[InternalRecord]:
    """Geocode records using the fixture provider."""
    provider = FixtureProvider(fixtures_dir)
    updated: list[InternalRecord] = []
    for record in records:
        address = format_address(record)
        try:
            result = provider.geocode(address)
            location = record.location.model_copy(
                update={
                    "latitude": result.latitude,
                    "longitude": result.longitude,
                    "geocode": result,
                }
            )
            updated.append(record.model_copy(update={"location": location}))
        except KeyError:
            updated.append(record)
    return updated


def run_pipeline(
    data_path: Path,
    work_dir: Path,
    fixtures_dir: Path,
    demo_dir: Path,
) -> dict[str, object]:
    """Run the full demo pipeline and return summary metadata."""
    work_dir.mkdir(parents=True, exist_ok=True)
    records = load_bc_hospitals(data_path)
    # Stable demo identifiers use row positions, not identities from live inputs.
    for index, record in enumerate(records):

        def demo_id(entity: str, row: int = index) -> str:
            return str(uuid5(NAMESPACE_URL, f"community-asset-mapper/demo/{row}/{entity}"))

        record.organization.id = demo_id("organization")
        record.location.id = demo_id("location")
        record.location.organization_id = record.organization.id
        record.service.id = demo_id("service")
        record.service.organization_id = record.organization.id
        record.service.location_id = record.location.id
        if record.location.address is not None:
            record.location.address.id = demo_id("address")
            record.location.address.location_id = record.location.id
        if record.organization.provenance is not None:
            record.organization.provenance.retrieved_at = None
    records = geocode_records(records, fixtures_dir)

    validation = validate_package(records)
    groups = propose_duplicates(records)
    records, audit = apply_merges(records, groups, only_merge=False)
    if audit:
        write_audit_log(audit, work_dir / "dedup_audit.jsonl")

    gap = compute_gap_metrics(
        records,
        da_boundaries=demo_dir / "boundaries" / "da_sample.geojson",
        csd_boundaries=demo_dir / "boundaries" / "csd_sample.geojson",
        population_csv=demo_dir / "population.csv",
        geography="da",
    )
    with (work_dir / "gap_report.json").open("w", encoding="utf-8") as handle:
        json.dump(gap.to_dict(), handle, indent=2)

    issues = run_quality_checks(records)
    write_backlog_report(issues, work_dir, generated_at=datetime(2026, 9, 28, tzinfo=UTC))

    (work_dir / "state.json").write_text(
        json.dumps([record.model_dump(mode="json") for record in records], indent=2),
        encoding="utf-8",
    )
    export_hsds_package(records, work_dir / "hsds")
    export_geojson(records, work_dir / "services.geojson")
    export_csv(records, work_dir / "services.csv")
    build_site(records, work_dir / "site", SiteConfig(no_tiles=True))

    return {
        "record_count": len(records),
        "validation_valid": validation.valid,
        "validation_errors": validation.errors,
        "duplicate_groups": len(groups),
        "quality_issues": len(issues),
        "gap_metrics": len(gap.metrics),
    }
