"""Safe CSV parsing."""

from __future__ import annotations

import csv
from pathlib import Path

from community_asset_mapper.security.io import MAX_FILE_BYTES


def read_csv(path: Path, max_bytes: int = MAX_FILE_BYTES) -> list[dict[str, str]]:
    """Read a CSV file into a list of string dictionaries."""
    resolved = path.resolve()
    size = resolved.stat().st_size
    if size > max_bytes:
        raise ValueError(f"CSV file exceeds size limit ({size} > {max_bytes})")
    rows: list[dict[str, str]] = []
    with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return rows
        for row in reader:
            rows.append({k: (v if v is not None else "") for k, v in row.items()})
    return rows
