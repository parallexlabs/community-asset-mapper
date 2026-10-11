"""CLI tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from community_asset_mapper import __version__
from community_asset_mapper.cli.main import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_run_demo(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("community_asset_mapper.cli.main._state_path", tmp_path / "state.json")
    work = tmp_path / "demo"
    result = runner.invoke(app, ["run-demo", "--work-dir", str(work)])
    assert result.exit_code == 0
    assert "record_count" in result.stdout


def test_ingest_validate_export(demo_dir: Path, tmp_path: Path, monkeypatch) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_file = state_dir / "state.json"
    monkeypatch.setattr("community_asset_mapper.cli.main._state_path", state_file)

    hospitals = str(demo_dir / "data" / "hospitals.csv")
    ingest = runner.invoke(app, ["ingest", "bc_hospitals", hospitals])
    assert ingest.exit_code == 0

    validate = runner.invoke(app, ["validate"])
    assert validate.exit_code == 0

    export = runner.invoke(
        app,
        ["export", "geojson", "--output", str(tmp_path / "out.geojson")],
    )
    assert export.exit_code == 0
