"""BC Address Geocoder provider with cache and bounded timeout."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

from community_asset_mapper.geocode.cache import JsonlGeocodeCache
from community_asset_mapper.models.records import GeocodeResult
from community_asset_mapper.security.network import DEFAULT_TIMEOUT_SECONDS, bounded_timeout


class BcAddressGeocoderProvider:
    """Geocode via BC Address Geocoder API."""

    BASE_URL = "https://geocoder.api.gov.bc.ca/addresses.json"

    def __init__(
        self,
        cache: JsonlGeocodeCache | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        api_key: str | None = None,
    ) -> None:
        self.cache = cache
        self.timeout = bounded_timeout(timeout)
        self.api_key = api_key or os.environ.get("CAM_BC_GEOCODER_API_KEY")

    def geocode(self, address: str) -> GeocodeResult:
        if self.cache:
            cached = self.cache.get(address)
            if cached is not None:
                return cached

        params: dict[str, str] = {"addressString": address, "maxResults": "1"}
        if self.api_key:
            params["apikey"] = self.api_key

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            payload: dict[str, Any] = response.json()

        features = payload.get("features", [])
        if not features:
            raise ValueError(f"No geocode result for address: {address}")

        feature = features[0]
        coords = feature["geometry"]["coordinates"]
        props = feature.get("properties", {})
        result = GeocodeResult(
            latitude=float(coords[1]),
            longitude=float(coords[0]),
            match_type=str(props.get("matchPrecision", "unknown")),
            confidence=float(props.get("score", 0)) / 100.0 if props.get("score") else 0.0,
            provider="bc-address-geocoder",
            retrieved_at=datetime.now(UTC),
            raw_reference=str(props.get("fullAddress", address)),
            normalized_address=str(props.get("fullAddress", address)),
        )
        if self.cache:
            self.cache.set(address, result)
        return result
