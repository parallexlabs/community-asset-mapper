"""JSONL geocode cache."""

from __future__ import annotations

import json
from pathlib import Path

from community_asset_mapper.models.records import GeocodeResult


class JsonlGeocodeCache:
    """Append-only JSONL cache keyed by normalized address."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._index: dict[str, GeocodeResult] = {}
        if path.exists():
            self._load()

    def _normalize(self, address: str) -> str:
        return " ".join(address.lower().split())

    def _load(self) -> None:
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                key = payload.get("key", "")
                result = GeocodeResult.model_validate(payload["result"])
                self._index[key] = result

    def get(self, address: str) -> GeocodeResult | None:
        return self._index.get(self._normalize(address))

    def set(self, address: str, result: GeocodeResult) -> None:
        key = self._normalize(address)
        self._index[key] = result
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"key": key, "result": result.model_dump(mode="json")}) + "\n")
