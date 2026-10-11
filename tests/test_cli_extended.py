"""Extended CLI command coverage."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from community_asset_mapper.cli.main import app

runner = CliRunner()


def _setup_state(monkeypatch, tmp_path: Path, demo_dir: Path) -> None:
    state_file = tmp_path / "state.json"
    monkeypatch.setattr("community_asset_mapper.cli.main._state_path", state_file)
    hospitals = str(demo_dir / "data" / "hospitals.csv")
    runner.invoke(app, ["ingest", "bc_hospitals", hospitals])


def test_cli_geocode_fixture(demo_dir: Path, tmp_path: Path, monkeypatch) -> None:
    _setup_state(monkeypatch, tmp_path, demo_dir)
    result = runner.invoke(app, ["geocode", "--provider", "fixture"])
    assert result.exit_code == 0


def test_cli_dedup_and_gap(demo_dir: Path, tmp_path: Path, monkeypatch) -> None:
    _setup_state(monkeypatch, tmp_path, demo_dir)
    runner.invoke(app, ["geocode", "--provider", "fixture"])
    dedup = runner.invoke(app, ["dedup", "--threshold", "0.5"])
    assert dedup.exit_code == 0
    gap = runner.invoke(app, ["gap", "--geography", "da", "--output", str(tmp_path / "gap.json")])
    assert gap.exit_code == 0


def test_cli_quality_and_exports(demo_dir: Path, tmp_path: Path, monkeypatch) -> None:
    _setup_state(monkeypatch, tmp_path, demo_dir)
    runner.invoke(app, ["geocode", "--provider", "fixture"])
    quality = runner.invoke(app, ["quality", "--output-dir", str(tmp_path / "quality")])
    assert quality.exit_code == 0
    hsds = runner.invoke(app, ["export", "hsds", "--output", str(tmp_path / "hsds")])
    assert hsds.exit_code == 0
    csv = runner.invoke(app, ["export", "csv", "--output", str(tmp_path / "out.csv")])
    assert csv.exit_code == 0


def test_cli_build_site(demo_dir: Path, tmp_path: Path, monkeypatch) -> None:
    _setup_state(monkeypatch, tmp_path, demo_dir)
    runner.invoke(app, ["geocode", "--provider", "fixture"])
    result = runner.invoke(app, ["build-site", "-o", str(tmp_path / "dist"), "--no-tiles"])
    assert result.exit_code == 0


def test_cli_ingest_csv_no_hospital_columns(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "generic.csv"
    csv_path.write_text("name,value\nfoo,bar\n", encoding="utf-8")
    state_file = tmp_path / "state.json"
    monkeypatch.setattr("community_asset_mapper.cli.main._state_path", state_file)
    result = runner.invoke(app, ["ingest", "csv", str(csv_path)])
    assert result.exit_code == 0


def test_cli_validate_no_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("community_asset_mapper.cli.main._state_path", tmp_path / "missing.json")
    result = runner.invoke(app, ["validate"])
    assert result.exit_code != 0


def test_demo_then_build_site(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("community_asset_mapper.cli.main._state_path", tmp_path / "state.json")
    result = runner.invoke(app, ["run-demo", "--work-dir", str(tmp_path / "demo")])
    assert result.exit_code == 0
    result = runner.invoke(app, ["build-site", "-o", str(tmp_path / "site"), "--no-tiles"])
    assert result.exit_code == 0
    assert (tmp_path / "site" / "index.html").exists()


def test_excel_hospital_ingestion(tmp_path: Path, monkeypatch) -> None:
    import json

    from openpyxl import Workbook

    source = tmp_path / "hospital.xlsx"
    state = tmp_path / "state.json"
    monkeypatch.setattr("community_asset_mapper.cli.main._state_path", state)
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["FACILITY_NAME", "CITY"])
    sheet.append(["Example Hospital", "Vancouver"])
    workbook.save(source)
    result = runner.invoke(app, ["ingest", "excel", str(source)])
    assert result.exit_code == 0
    assert json.loads(state.read_text())[0]["service"]["name"] == "Example Hospital"


def test_unknown_geocoder_rejected(demo_dir: Path, tmp_path: Path, monkeypatch) -> None:
    _setup_state(monkeypatch, tmp_path, demo_dir)
    result = runner.invoke(app, ["geocode", "--provider", "invalid-provider"])
    assert result.exit_code != 0
