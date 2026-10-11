"""Locate bundled data in installed packages or source checkouts."""

from pathlib import Path


def resource_path(relative: str) -> Path:
    packaged = Path(__file__).resolve().parent / "data" / relative
    if packaged.exists():
        return packaged
    return Path(__file__).resolve().parents[2] / relative
