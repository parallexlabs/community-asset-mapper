"""Export HSDS JSON packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from community_asset_mapper.hsds.validate import record_to_hsds
from community_asset_mapper.models.records import InternalRecord


def export_hsds_package(records: list[InternalRecord], output_dir: Path) -> Path:
    """Write HSDS JSON resources to an output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    buckets: dict[str, list[dict[str, Any]]] = {
        "organizations": [],
        "services": [],
        "locations": [],
        "addresses": [],
        "service_at_location": [],
    }
    for record in records:
        package = record_to_hsds(record)
        buckets["organizations"].append(package["organization"])
        buckets["services"].append(package["service"])
        buckets["locations"].append(package["location"])
        buckets["service_at_location"].append(package["service_at_location"])
        if "address" in package:
            buckets["addresses"].append(package["address"])

    for name, items in buckets.items():
        if items:
            path = output_dir / f"{name}.json"
            with path.open("w", encoding="utf-8") as handle:
                json.dump(items, handle, indent=2)

    manifest = {
        "profile": "hsds-3.0",
        "resources": [name for name, items in buckets.items() if items],
        "record_count": len(records),
    }
    manifest_path = output_dir / "datapackage.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest_path
