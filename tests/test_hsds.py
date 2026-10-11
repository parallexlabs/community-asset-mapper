"""HSDS validation and export tests."""

from __future__ import annotations

from pathlib import Path

from community_asset_mapper.hsds.export import export_hsds_package
from community_asset_mapper.hsds.schemas import load_schemas, schema_dir
from community_asset_mapper.hsds.validate import record_to_hsds, validate_package, validate_record
from community_asset_mapper.models.records import InternalRecord


def test_schema_dir_exists() -> None:
    assert schema_dir().is_dir()
    assert (schema_dir() / "organization.json").exists()


def test_load_schemas() -> None:
    schemas = load_schemas()
    assert "organization" in schemas
    assert "service" in schemas


def test_validate_record_valid() -> None:
    result = validate_record(
        "organization",
        {"id": "d9d5e0f5-d3ce-4f73-9a2f-4dd0ecc6c610", "name": "Test Org", "description": "Desc"},
    )
    assert result.valid


def test_validate_record_invalid() -> None:
    result = validate_record("organization", {"id": "bad", "name": "Test"})
    assert not result.valid


def test_validate_package(hospital_records: list[InternalRecord]) -> None:
    result = validate_package(hospital_records)
    assert result.valid


def test_record_to_hsds_has_required_fields(hospital_records: list[InternalRecord]) -> None:
    package = record_to_hsds(hospital_records[0])
    assert package["service"]["status"] == "active"
    assert package["address"]["address_type"] == "physical"


def test_export_hsds_package(hospital_records: list[InternalRecord], tmp_path: Path) -> None:
    manifest = export_hsds_package(hospital_records[:2], tmp_path / "hsds")
    assert manifest.exists()
    assert (tmp_path / "hsds" / "organizations.json").exists()
