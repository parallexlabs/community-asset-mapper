"""Typer CLI for Community Asset Mapper."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from community_asset_mapper import __version__
from community_asset_mapper.adapters.bc_hospitals import load_bc_hospitals, row_to_record
from community_asset_mapper.adapters.csv import read_csv
from community_asset_mapper.adapters.excel import read_excel
from community_asset_mapper.dedup.engine import apply_merges, propose_duplicates, write_audit_log
from community_asset_mapper.export.formats import export_csv, export_geojson
from community_asset_mapper.gap.metrics import compute_gap_metrics
from community_asset_mapper.geocode.bc_provider import BcAddressGeocoderProvider
from community_asset_mapper.geocode.cache import JsonlGeocodeCache
from community_asset_mapper.hsds.export import export_hsds_package
from community_asset_mapper.hsds.validate import validate_package
from community_asset_mapper.models.records import InternalRecord
from community_asset_mapper.pipeline import format_address, geocode_records, run_pipeline
from community_asset_mapper.quality.engine import run_quality_checks, write_backlog_report
from community_asset_mapper.resources import resource_path
from community_asset_mapper.site.generator import SiteConfig, build_site

app = typer.Typer(help="Community Asset Mapper - open service inventory pipeline.")
_state_path = Path(".cam/state.json")


class ExportFormat(StrEnum):
    hsds = "hsds"
    geojson = "geojson"
    csv = "csv"


class AdapterName(StrEnum):
    bc_hospitals = "bc_hospitals"
    csv = "csv"
    excel = "excel"


def _fixtures_dir() -> Path:
    return resource_path("fixtures/geocoder")


def _demo_dir() -> Path:
    return resource_path("examples/demo_bc")


def _save_state(records: list[InternalRecord]) -> None:
    _state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.model_dump(mode="json") for r in records]
    _state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_state() -> list[InternalRecord]:
    if not _state_path.exists():
        raise typer.BadParameter("No working state found. Run `cam ingest` first.")
    data = json.loads(_state_path.read_text(encoding="utf-8"))
    return [InternalRecord.model_validate(item) for item in data]


def version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """Community Asset Mapper CLI."""


@app.command()
def ingest(
    adapter: AdapterName,
    path: Path,
) -> None:
    """Load source data into working state."""
    if adapter == AdapterName.bc_hospitals:
        records = load_bc_hospitals(path)
    elif adapter == AdapterName.csv:
        rows = read_csv(path)
        records = load_bc_hospitals(path) if "FACILITY_NAME" in (rows[0] if rows else {}) else []
        if not records:
            typer.echo(f"Loaded {len(rows)} CSV rows (no hospital-style records saved).")
            return
    else:
        rows = read_excel(path)
        records = (
            [row_to_record(row) for row in rows] if rows and "FACILITY_NAME" in rows[0] else []
        )
        if not records:
            typer.echo(f"Loaded {len(rows)} Excel rows (no hospital-style records saved).")
            return
    _save_state(records)
    typer.echo(f"Ingested {len(records)} records via {adapter.value}.")


@app.command()
def validate() -> None:
    """Validate working state against HSDS schemas."""
    records = _load_state()
    result = validate_package(records)
    if result.valid:
        typer.echo(f"Validation passed for {len(records)} records.")
    else:
        for err in result.errors:
            typer.echo(err)
        raise typer.Exit(code=1)


@app.command()
def geocode(
    provider: Annotated[str, typer.Option(help="bc or fixture")] = "fixture",
    cache_path: Annotated[Path | None, typer.Option(help="JSONL cache path")] = None,
) -> None:
    """Geocode records in working state."""
    records = _load_state()
    if provider == "fixture":
        records = geocode_records(records, _fixtures_dir())
    elif provider == "bc":
        cache = JsonlGeocodeCache(cache_path or Path(".cam/geocode_cache.jsonl"))
        bc = BcAddressGeocoderProvider(cache=cache)
        updated: list[InternalRecord] = []
        for record in records:
            address = format_address(record)
            try:
                result = bc.geocode(address)
                location = record.location.model_copy(
                    update={
                        "latitude": result.latitude,
                        "longitude": result.longitude,
                        "geocode": result,
                    }
                )
                updated.append(record.model_copy(update={"location": location}))
            except Exception:
                typer.echo("Geocode failed; record retained without an update.")
                updated.append(record)
        records = updated
    else:
        raise typer.BadParameter("Provider must be fixture or bc.")
    _save_state(records)
    typer.echo(f"Geocoded {len(records)} records using {provider} provider.")


@app.command()
def dedup(
    threshold: Annotated[float, typer.Option(help="Similarity threshold")] = 0.85,
    apply: Annotated[bool, typer.Option("--apply", help="Apply merge recommendations")] = False,
) -> None:
    """Propose or apply duplicate merges."""
    records = _load_state()
    groups = propose_duplicates(records, threshold=threshold)
    typer.echo(f"Found {len(groups)} duplicate groups.")
    for group in groups:
        typer.echo(
            f"  {group.record_ids} score={group.score:.2f} action={group.recommended_action}"
        )
    if apply:
        records, audit = apply_merges(records, groups)
        write_audit_log(audit, Path(".cam/dedup_audit.jsonl"))
        _save_state(records)
        typer.echo(f"Applied {len(audit)} merges.")


@app.command()
def gap(
    geography: Annotated[str, typer.Option(help="da or csd")] = "da",
    demo_dir: Annotated[Path | None, typer.Option(help="Demo data directory")] = None,
    output: Annotated[Path, typer.Option(help="Output JSON path")] = Path(".cam/gap_report.json"),
) -> None:
    """Compute gap metrics."""
    records = _load_state()
    demo = demo_dir or _demo_dir()
    report = compute_gap_metrics(
        records,
        da_boundaries=demo / "boundaries" / "da_sample.geojson",
        csd_boundaries=demo / "boundaries" / "csd_sample.geojson",
        population_csv=demo / "population.csv",
        geography=geography,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    typer.echo(f"Wrote gap report with {len(report.metrics)} metrics to {output}.")


@app.command()
def quality(
    output_dir: Annotated[Path, typer.Option(help="Output directory")] = Path(".cam/quality"),
) -> None:
    """Emit data-quality backlog."""
    records = _load_state()
    issues = run_quality_checks(records)
    json_path, md_path = write_backlog_report(issues, output_dir)
    typer.echo(f"Found {len(issues)} issues. Wrote {json_path} and {md_path}.")


@app.command(name="export")
def export_cmd(
    format: ExportFormat,
    output: Annotated[Path, typer.Option(help="Output path or directory")] = Path(".cam/export"),
) -> None:
    """Export working state."""
    records = _load_state()
    if format == ExportFormat.hsds:
        path = export_hsds_package(records, output)
        typer.echo(f"Exported HSDS package to {path.parent}.")
    elif format == ExportFormat.geojson:
        path = export_geojson(records, output)
        typer.echo(f"Exported GeoJSON to {path}.")
    else:
        path = export_csv(records, output)
        typer.echo(f"Exported CSV to {path}.")


@app.command(name="build-site")
def build_site_cmd(
    output: Annotated[Path, typer.Option("-o", help="Output directory")] = Path("dist"),
    no_tiles: Annotated[bool, typer.Option(help="Disable map tiles")] = False,
) -> None:
    """Build static accessible site."""
    records = _load_state()
    config = SiteConfig(no_tiles=no_tiles)
    path = build_site(records, output, config)
    typer.echo(f"Built site at {path}.")


@app.command(name="run-demo")
def run_demo_cmd(
    work_dir: Annotated[Path, typer.Option(help="Working directory")] = Path(".cam/demo"),
) -> None:
    """Run full demo pipeline on bundled BC hospital fixtures."""
    demo = _demo_dir()
    summary = run_pipeline(
        data_path=demo / "data" / "hospitals.csv",
        work_dir=work_dir,
        fixtures_dir=_fixtures_dir(),
        demo_dir=demo,
    )
    state = json.loads((work_dir / "state.json").read_text(encoding="utf-8"))
    _save_state([InternalRecord.model_validate(item) for item in state])
    typer.echo(json.dumps(summary, indent=2))
    if not summary["validation_valid"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
