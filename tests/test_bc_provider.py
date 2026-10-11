"""BC geocoder provider tests with mocked HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from community_asset_mapper.geocode.bc_provider import BcAddressGeocoderProvider
from community_asset_mapper.geocode.cache import JsonlGeocodeCache


def test_bc_provider_geocode_success(tmp_path) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "features": [
            {
                "geometry": {"coordinates": [-123.1, 49.2]},
                "properties": {"matchPrecision": "rooftop", "score": 95, "fullAddress": "Test"},
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = mock_response
        provider = BcAddressGeocoderProvider(api_key="test-key")
        result = provider.geocode("123 Main St, Vancouver")

    assert result.latitude == 49.2
    assert result.provider == "bc-address-geocoder"


def test_bc_provider_no_results() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"features": []}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = mock_response
        provider = BcAddressGeocoderProvider(api_key="test-key")
        try:
            provider.geocode("unknown")
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


def test_bc_provider_writes_cache(tmp_path) -> None:
    cache = JsonlGeocodeCache(tmp_path / "cache.jsonl")
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "features": [
            {
                "geometry": {"coordinates": [-123.0, 49.0]},
                "properties": {"matchPrecision": "interpolated", "score": 80},
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = mock_response
        provider = BcAddressGeocoderProvider(cache=cache, api_key="key")
        provider.geocode("cached address")

    assert cache.get("cached address") is not None
