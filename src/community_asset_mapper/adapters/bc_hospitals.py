"""BC Hospitals in BC open-data adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from community_asset_mapper.adapters.csv import read_csv
from community_asset_mapper.models.records import (
    AddressRecord,
    InternalRecord,
    LocationRecord,
    OrganizationRecord,
    Provenance,
    ServiceRecord,
)


def _get(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in row and row[key].strip():
            return row[key].strip()
    return ""


def _parse_float(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def row_to_record(row: dict[str, str]) -> InternalRecord:
    """Map a BC Hospitals CSV row to an internal record."""
    facility = _get(row, "FACILITY_NAME", "Facility Name", "facility_name")
    org_name = _get(row, "ORGANIZATION_NAME", "Organization Name", "organization_name") or facility
    address = _get(row, "ADDRESS", "Address", "address")
    city = _get(row, "CITY", "City", "city")
    province = _get(row, "PROVINCE", "Province", "province") or "BC"
    postal = _get(row, "POSTAL_CODE", "Postal Code", "postal_code")
    lat = _parse_float(_get(row, "LATITUDE", "Latitude", "latitude"))
    lon = _parse_float(_get(row, "LONGITUDE", "Longitude", "longitude"))
    wheelchair = _get(
        row, "WHEELCHAIR_ACCESSIBLE", "Wheelchair Accessible", "wheelchair_accessible"
    )
    hours = _get(row, "HOURS", "Hours", "hours")
    source_id = _get(row, "FACILITY_ID", "Facility ID", "facility_id") or facility

    org = OrganizationRecord(
        name=org_name,
        description=f"Hospital facility: {facility}",
        provenance=Provenance(
            source="hospitals-in-bc",
            source_id=source_id,
            retrieved_at=datetime.now(UTC),
            licence="Open Government Licence - British Columbia",
        ),
    )
    address_record = AddressRecord(
        location_id="",
        address_1=address,
        city=city,
        state_province=province,
        postal_code=postal,
    )
    location = LocationRecord(
        organization_id=org.id,
        name=facility,
        latitude=lat,
        longitude=lon,
        address=address_record.model_copy(update={"location_id": "pending"}),
    )
    location.address = address_record.model_copy(update={"location_id": location.id})
    service = ServiceRecord(
        organization_id=org.id,
        location_id=location.id,
        name=facility,
        description="Acute care hospital",
        service_type="hospital",
        hours=hours or None,
        wheelchair_accessible=(
            wheelchair.lower() in {"y", "yes", "true", "1"} if wheelchair else None
        ),
    )
    return InternalRecord(organization=org, service=service, location=location, source_row=row)


def load_bc_hospitals(path: Path) -> list[InternalRecord]:
    """Load BC hospital records from a CSV file."""
    return [row_to_record(row) for row in read_csv(path)]
