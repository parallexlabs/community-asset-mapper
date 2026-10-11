"""CSV and GeoJSON export."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from community_asset_mapper.models.records import InternalRecord


def export_csv(records: list[InternalRecord], path: Path) -> Path:
    """Export records to a sanitized CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "organization_name",
        "service_name",
        "address",
        "city",
        "postal_code",
        "latitude",
        "longitude",
        "service_type",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for record in records:
            addr = record.location.address
            row = [
                record.organization.name,
                record.service.name,
                addr.address_1 if addr else "",
                addr.city if addr else "",
                addr.postal_code if addr else "",
                str(record.location.latitude) if record.location.latitude is not None else "",
                str(record.location.longitude) if record.location.longitude is not None else "",
                record.service.service_type or "",
            ]
            safe_row = [
                ("'" + cell)
                if cell and cell[0] in ("=", "+", "-", "@") and idx not in (5, 6)
                else cell
                for idx, cell in enumerate(row)
            ]
            writer.writerow(safe_row)
    return path


def export_geojson(records: list[InternalRecord], path: Path) -> Path:
    """Export geocoded records as GeoJSON."""
    features: list[dict[str, Any]] = []
    for record in records:
        lat = record.location.latitude
        lon = record.location.longitude
        if lat is None or lon is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "organization": record.organization.name,
                    "service": record.service.name,
                    "service_id": record.service.id,
                    "service_type": record.service.service_type,
                },
            }
        )
    collection = {"type": "FeatureCollection", "features": features}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(collection, handle, indent=2)
    return path
