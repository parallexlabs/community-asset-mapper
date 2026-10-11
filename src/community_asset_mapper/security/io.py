"""Safe filesystem and YAML loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_YAML_BYTES = 10 * 1024 * 1024


def safe_path(base: Path, user_path: str | Path) -> Path:
    """Resolve a user-supplied path under a base directory."""
    base_resolved = base.resolve()
    candidate = (base_resolved / user_path).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        raise ValueError(f"Path escapes base directory: {user_path}") from None
    return candidate


def safe_yaml_load(path: Path, max_bytes: int = MAX_YAML_BYTES) -> Any:
    """Load YAML from a file with size limits and safe loader."""
    resolved = path.resolve()
    size = resolved.stat().st_size
    if size > max_bytes:
        raise ValueError(f"YAML file exceeds size limit ({size} > {max_bytes})")
    with resolved.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)
