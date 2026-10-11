"""Jinja2 static site generator with Leaflet map and accessible table."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from community_asset_mapper.export.formats import export_csv
from community_asset_mapper.models.records import InternalRecord
from community_asset_mapper.resources import resource_path
from community_asset_mapper.security.sanitize import validate_url

DEFAULT_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
OSM_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
)


@dataclass
class SiteConfig:
    title: str = "Community Asset Mapper"
    tile_url: str = DEFAULT_TILE_URL
    tile_attribution: str = OSM_ATTRIBUTION
    no_tiles: bool = False


def _template_dir() -> Path:
    return Path(__file__).resolve().parent / "templates"


def _assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets"


def build_site(
    records: list[InternalRecord],
    output_dir: Path,
    config: SiteConfig | None = None,
) -> Path:
    """Build a static accessible site with map, table, and CSV download."""
    cfg = config or SiteConfig()
    output_dir.mkdir(parents=True, exist_ok=True)
    validate_url(cfg.tile_url)
    assets_out = output_dir / "assets"
    assets_out.mkdir(parents=True, exist_ok=True)

    src_assets = _assets_dir()
    if src_assets.exists():
        for item in src_assets.iterdir():
            dest = assets_out / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

    table_rows: list[dict[str, Any]] = []
    map_features: list[dict[str, Any]] = []
    for row_index, record in enumerate(records):
        addr = record.location.address
        city = addr.city if addr and addr.city else ""
        service_type = record.service.service_type or ""
        table_rows.append(
            {
                "name": record.service.name,
                "organization": record.organization.name,
                "city": city,
                "service_type": service_type,
                "lat": record.location.latitude,
                "lon": record.location.longitude,
            }
        )
        if record.location.latitude is not None and record.location.longitude is not None:
            map_features.append(
                {
                    "row_index": row_index,
                    "name": record.service.name,
                    "organization": record.organization.name,
                    "city": city,
                    "service_type": service_type,
                    "lat": record.location.latitude,
                    "lon": record.location.longitude,
                }
            )

    export_csv(records, output_dir / "services.csv")
    data_licences = resource_path("DATA.md")
    if data_licences.exists():
        shutil.copy2(data_licences, output_dir / "data-licences.md")

    def to_json_script(value: object) -> Markup:
        return Markup(
            json.dumps(value)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
        )

    env = Environment(
        loader=FileSystemLoader(str(_template_dir())),
        autoescape=True,
    )
    env.filters["tojson"] = to_json_script
    template = env.get_template("index.html.j2")
    html = template.render(
        title=cfg.title,
        table_rows=table_rows,
        map_features=map_features,
        tile_url=cfg.tile_url,
        tile_attribution=cfg.tile_attribution,
        no_tiles=cfg.no_tiles,
    )
    index_path = output_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path
