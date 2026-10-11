"""Geocode provider protocol."""

from __future__ import annotations

from typing import Protocol

from community_asset_mapper.models.records import GeocodeResult


class GeocodeProvider(Protocol):
    def geocode(self, address: str) -> GeocodeResult: ...
