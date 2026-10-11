"""Load vendored HSDS JSON schemas."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from community_asset_mapper.resources import resource_path

SCHEMA_NAMES = (
    "organization",
    "service",
    "location",
    "address",
    "service_at_location",
    "phone",
    "schedule",
    "metadata",
)


def schema_dir() -> Path:
    """Return path to vendored HSDS schemas."""
    return resource_path("schemas/hsds")


@lru_cache(maxsize=1)
def load_schemas() -> dict[str, dict[str, Any]]:
    """Load all vendored HSDS schemas."""
    base = schema_dir()
    schemas: dict[str, dict[str, Any]] = {}
    for name in SCHEMA_NAMES:
        path = base / f"{name}.json"
        with path.open("r", encoding="utf-8") as handle:
            schemas[name] = json.load(handle)
    return schemas
