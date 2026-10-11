"""Fixture-based geocoder for tests and offline demos."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from community_asset_mapper.models.records import GeocodeResult
from community_asset_mapper.security.io import safe_yaml_load


class FixtureProvider:
    """Geocode using synthetic fixture responses."""

    def __init__(self, fixtures_dir: Path) -> None:
        self.fixtures_dir = fixtures_dir
        manifest_path = fixtures_dir / "manifest.yaml"
        if manifest_path.exists():
            self._manifest: dict[str, str] = safe_yaml_load(manifest_path)
        else:
            self._manifest = {}
        self._responses: dict[str, dict[str, object]] = {}
        responses_path = fixtures_dir / "bc_responses.jsonl"
        if responses_path.exists():
            with responses_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    self._responses[entry["id"]] = entry

    def _normalize(self, address: str) -> str:
        return " ".join(address.lower().split())

    def geocode(self, address: str) -> GeocodeResult:
        normalized = self._normalize(address)
        entry_id = self._manifest.get(normalized) or self._manifest.get(address)
        if not entry_id:
            raise KeyError(f"No fixture for address: {address}")
        entry = self._responses[entry_id]
        return GeocodeResult(
            latitude=float(str(entry["latitude"])),
            longitude=float(str(entry["longitude"])),
            match_type=str(entry.get("match_type", "fixture")),
            confidence=float(str(entry.get("confidence", 1.0))),
            provider="fixture",
            retrieved_at=(
                datetime.fromisoformat(str(entry["reference_time"]))
                if "reference_time" in entry
                else datetime.now(UTC)
            ),
            raw_reference=str(entry_id),
            normalized_address=normalized,
        )
