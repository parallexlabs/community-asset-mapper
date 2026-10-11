"""Pipeline integration tests."""

from __future__ import annotations

from pathlib import Path

from community_asset_mapper.pipeline import run_pipeline


def test_run_pipeline(demo_dir: Path, fixtures_dir: Path, tmp_path: Path) -> None:
    summary = run_pipeline(
        data_path=demo_dir / "data" / "hospitals.csv",
        work_dir=tmp_path / "work",
        fixtures_dir=fixtures_dir,
        demo_dir=demo_dir,
    )
    assert summary["record_count"] == 10
    assert (tmp_path / "work" / "hsds" / "datapackage.json").exists()
    assert (tmp_path / "work" / "site" / "index.html").exists()
    assert (tmp_path / "work" / "quality_backlog.json").exists()


def test_demo_outputs_repeat_exactly(demo_dir: Path, fixtures_dir: Path, tmp_path: Path) -> None:
    import hashlib

    outputs = []
    for name in ("first", "second"):
        work = tmp_path / name
        run_pipeline(demo_dir / "data" / "hospitals.csv", work, fixtures_dir, demo_dir)
        outputs.append(
            {
                str(path.relative_to(work)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in work.rglob("*")
                if path.is_file()
            }
        )
    assert outputs[0] == outputs[1]
