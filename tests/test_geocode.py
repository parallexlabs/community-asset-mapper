"""Geocoding tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from community_asset_mapper.geocode.bc_provider import BcAddressGeocoderProvider
from community_asset_mapper.geocode.cache import JsonlGeocodeCache
from community_asset_mapper.geocode.fixture_provider import FixtureProvider
from community_asset_mapper.models.records import GeocodeResult
from community_asset_mapper.pipeline import geocode_records
from community_asset_mapper.security.network import bounded_timeout


def test_fixture_provider_geocode(fixtures_dir: Path) -> None:
    provider = FixtureProvider(fixtures_dir)
    result = provider.geocode("899 West 12th Avenue, Vancouver, BC, V5Z 1M9")
    assert result.latitude == 49.2612
    assert result.provider == "fixture"


def test_fixture_provider_missing_address(fixtures_dir: Path) -> None:
    provider = FixtureProvider(fixtures_dir)
    with pytest.raises(KeyError):
        provider.geocode("999 Unknown Street")


def test_jsonl_cache_roundtrip(tmp_path: Path) -> None:
    cache = JsonlGeocodeCache(tmp_path / "cache.jsonl")
    result = GeocodeResult(
        latitude=1.0,
        longitude=2.0,
        provider="test",
        retrieved_at=datetime.now(UTC),
        raw_reference="ref",
    )
    cache.set("123 Main St", result)
    loaded = JsonlGeocodeCache(tmp_path / "cache.jsonl")
    assert loaded.get("123 Main St") is not None


def test_geocode_records(hospital_records: list, fixtures_dir: Path) -> None:
    geocoded = geocode_records(hospital_records[:3], fixtures_dir)
    assert geocoded[0].location.latitude is not None


def test_bounded_timeout() -> None:
    assert bounded_timeout(5.0) == 5.0


def test_bc_provider_uses_cache(tmp_path: Path) -> None:
    cache = JsonlGeocodeCache(tmp_path / "cache.jsonl")
    result = GeocodeResult(
        latitude=49.0,
        longitude=-123.0,
        provider="bc-address-geocoder",
        retrieved_at=datetime.now(UTC),
        raw_reference="cached",
    )
    cache.set("test address", result)
    provider = BcAddressGeocoderProvider(cache=cache)
    assert provider.geocode("test address").raw_reference == "cached"
