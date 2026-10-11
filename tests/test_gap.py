"""Gap analysis tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from community_asset_mapper.gap.metrics import MAUP_LIMITATIONS, compute_gap_metrics
from community_asset_mapper.pipeline import geocode_records


def test_compute_gap_metrics_da(hospital_records: list, demo_dir: Path, fixtures_dir: Path) -> None:
    geocoded = geocode_records(hospital_records, fixtures_dir)
    report = compute_gap_metrics(
        geocoded,
        da_boundaries=demo_dir / "boundaries" / "da_sample.geojson",
        csd_boundaries=demo_dir / "boundaries" / "csd_sample.geojson",
        population_csv=demo_dir / "population.csv",
        geography="da",
    )
    assert len(report.metrics) == 4
    assert report.metadata["maup_limitations"] == list(MAUP_LIMITATIONS)
    assert report.metrics[0].population_source
    assert report.metrics[0].population_date


def test_compute_gap_metrics_csd(
    hospital_records: list, demo_dir: Path, fixtures_dir: Path
) -> None:
    geocoded = geocode_records(hospital_records[:2], fixtures_dir)
    report = compute_gap_metrics(
        geocoded,
        da_boundaries=demo_dir / "boundaries" / "da_sample.geojson",
        csd_boundaries=demo_dir / "boundaries" / "csd_sample.geojson",
        population_csv=demo_dir / "population.csv",
        geography="csd",
    )
    assert len(report.metrics) == 1


def test_population_csv_missing_columns(
    tmp_path: Path, demo_dir: Path, hospital_records: list
) -> None:
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("DAUID,pop\n1,100\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        compute_gap_metrics(
            hospital_records[:1],
            da_boundaries=demo_dir / "boundaries" / "da_sample.geojson",
            csd_boundaries=None,
            population_csv=bad_csv,
        )
