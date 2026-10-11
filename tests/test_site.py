"""Static site generator tests."""

from __future__ import annotations

from pathlib import Path

from community_asset_mapper.pipeline import geocode_records
from community_asset_mapper.site.generator import SiteConfig, build_site


def test_build_site_no_tiles(hospital_records: list, fixtures_dir: Path, tmp_path: Path) -> None:
    geocoded = geocode_records(hospital_records[:3], fixtures_dir)
    index = build_site(geocoded, tmp_path / "site", SiteConfig(no_tiles=True))
    html = index.read_text(encoding="utf-8")
    assert "<h1>" in html
    assert 'role="main"' in html
    assert "<caption>" in html
    assert "no-tiles" in html
    assert "&lt;script&gt;" not in html
    assert (tmp_path / "site" / "services.csv").exists()
    assert (tmp_path / "site" / "assets" / "leaflet.min.js").exists()


def test_build_site_escapes_html(
    hospital_records: list, fixtures_dir: Path, tmp_path: Path
) -> None:
    geocoded = geocode_records(hospital_records[:1], fixtures_dir)
    geocoded[0].service.name = "<script>alert(1)</script>"
    index = build_site(geocoded, tmp_path / "site2", SiteConfig(no_tiles=True))
    html = index.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "\\u003cscript\\u003e" in html or "&lt;script&gt;" in html


def test_template_escapes_once_and_popup_uses_text(hospital_records: list, tmp_path: Path) -> None:
    record = hospital_records[0]
    record.service.name = 'A & B <img src=x onerror="alert(1)">'
    index = build_site([record], tmp_path / "site", SiteConfig(title="<img src=x>", no_tiles=True))
    html = index.read_text()
    assert "A &amp; B &lt;img" in html
    assert "&amp;amp;" not in html
    assert "<title>&lt;img src=x&gt;</title>" in html
    assert "line.textContent = text" in html
    assert "L.marker" in html
    assert "if (!noTiles)" in html
    assert 'role="region"' in html


def test_zero_and_missing_coordinates(hospital_records: list, tmp_path: Path) -> None:
    first, second = hospital_records[:2]
    first.location.latitude = 0.0
    first.location.longitude = 0.0
    second.location.latitude = None
    html = build_site([first, second], tmp_path / "site", SiteConfig(no_tiles=True)).read_text()
    assert 'data-feature="0"' in html
    assert 'data-feature="1"' not in html
    assert "No coordinates" in html
