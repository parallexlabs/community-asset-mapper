"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from community_asset_mapper.adapters.bc_hospitals import load_bc_hospitals
from community_asset_mapper.models.records import InternalRecord


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def demo_dir(repo_root: Path) -> Path:
    return repo_root / "examples" / "demo_bc"


@pytest.fixture
def fixtures_dir(repo_root: Path) -> Path:
    return repo_root / "fixtures" / "geocoder"


@pytest.fixture
def hospital_records(demo_dir: Path) -> list[InternalRecord]:
    return load_bc_hospitals(demo_dir / "data" / "hospitals.csv")


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    monkeypatch.delenv("CAM_BC_GEOCODER_API_KEY", raising=False)

    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Network access is forbidden in fixture tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
