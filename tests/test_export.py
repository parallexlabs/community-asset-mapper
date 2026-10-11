"""Export format tests."""

from __future__ import annotations

import json
from pathlib import Path

from community_asset_mapper.export.formats import export_csv, export_geojson
from community_asset_mapper.pipeline import geocode_records


def test_export_geojson(hospital_records: list, fixtures_dir: Path, tmp_path: Path) -> None:
    geocoded = geocode_records(hospital_records[:2], fixtures_dir)
    path = export_geojson(geocoded, tmp_path / "out.geojson")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 1


def test_export_csv(hospital_records: list, tmp_path: Path) -> None:
    path = export_csv(hospital_records[:2], tmp_path / "out.csv")
    content = path.read_text(encoding="utf-8")
    assert "organization_name" in content
    assert "Vancouver" in content


def test_csv_coordinates_and_text_roundtrip(hospital_records: list, tmp_path: Path) -> None:
    import csv

    record = hospital_records[0]
    record.location.latitude = 0.0
    record.location.longitude = -123.1
    record.service.name = '=SUM(1,2) "example"'
    path = export_csv([record], tmp_path / "roundtrip.csv")
    with path.open(newline="") as handle:
        row = next(csv.DictReader(handle))
    assert float(row["latitude"]) == 0.0
    assert float(row["longitude"]) == -123.1
    assert row["service_name"] == "'" + record.service.name
