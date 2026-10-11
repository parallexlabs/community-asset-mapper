"""Additional HSDS validation tests."""

from community_asset_mapper.adapters.bc_hospitals import row_to_record
from community_asset_mapper.hsds.validate import validate_package, validate_record


def test_validate_package_with_optional_fields() -> None:
    record = row_to_record(
        {
            "FACILITY_NAME": "Test Hospital",
            "ORGANIZATION_NAME": "Test Health",
            "ADDRESS": "1 Main St",
            "CITY": "Vancouver",
            "POSTAL_CODE": "V5Z 1M9",
            "PROVINCE": "BC",
        }
    )
    result = validate_package([record])
    assert result.valid


def test_validate_record_service_requires_status() -> None:
    result = validate_record(
        "service",
        {
            "id": "ac148810-d857-441c-9679-408f346de14b",
            "organization_id": "d9d5e0f5-d3ce-4f73-9a2f-4dd0ecc6c610",
            "name": "Test Service",
        },
    )
    assert not result.valid
