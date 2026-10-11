"""HSDS JSON Schema validation."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from community_asset_mapper.hsds.schemas import load_schemas
from community_asset_mapper.models.records import InternalRecord


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=lambda: list[str]())


def _validator_for(resource: str) -> Draft202012Validator:
    schema = load_schemas()[resource]
    return Draft202012Validator(schema)


def validate_record(resource: str, record: dict[str, Any]) -> ValidationResult:
    """Validate a single HSDS record against its schema."""
    validator = _validator_for(resource)
    errors: list[str] = []
    error_iter = cast(
        Iterator[ValidationError],
        validator.iter_errors(record),  # pyright: ignore[reportUnknownMemberType]
    )
    for error in sorted(error_iter, key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.path) or "<root>"
        errors.append(f"{path}: {error.message}")
    return ValidationResult(valid=not errors, errors=errors)


def record_to_hsds(record: InternalRecord) -> dict[str, dict[str, Any]]:
    """Convert an internal record to HSDS resource dictionaries."""
    org = {
        "id": record.organization.id,
        "name": record.organization.name,
    }
    if record.organization.alternate_name:
        org["alternate_name"] = record.organization.alternate_name
    if record.organization.description:
        org["description"] = record.organization.description
    if record.organization.email:
        org["email"] = record.organization.email
    if record.organization.website:
        org["website"] = record.organization.website

    location: dict[str, Any] = {
        "id": record.location.id,
        "location_type": record.location.location_type,
    }
    if record.location.name:
        location["name"] = record.location.name
    if record.location.latitude is not None:
        location["latitude"] = record.location.latitude
    if record.location.longitude is not None:
        location["longitude"] = record.location.longitude

    address: dict[str, Any] | None = None
    if record.location.address:
        addr = record.location.address
        address = {
            "id": addr.id,
            "location_id": record.location.id,
        }
        if addr.address_1:
            address["address_1"] = addr.address_1
        if addr.city:
            address["city"] = addr.city
        if addr.state_province:
            address["state_province"] = addr.state_province
        if addr.postal_code:
            address["postal_code"] = addr.postal_code
        if addr.country:
            address["country"] = addr.country
        address["address_type"] = "physical"

    service: dict[str, Any] = {
        "id": record.service.id,
        "organization_id": record.organization.id,
        "name": record.service.name,
        "status": "active",
    }
    if record.service.description:
        service["description"] = record.service.description
    if record.service.url:
        service["url"] = record.service.url

    sal_id = str(uuid5(NAMESPACE_URL, f"{record.service.id}:{record.location.id}"))
    sal = {
        "id": sal_id,
        "service_id": record.service.id,
        "location_id": record.location.id,
    }

    package: dict[str, dict[str, Any]] = {
        "organization": org,
        "location": location,
        "service": service,
        "service_at_location": sal,
    }
    if address:
        package["address"] = address
    return package


def validate_package(records: list[InternalRecord]) -> ValidationResult:
    """Validate a list of internal records as an HSDS package."""
    all_errors: list[str] = []
    for idx, record in enumerate(records):
        package = record_to_hsds(record)
        for resource, payload in package.items():
            if resource not in load_schemas():
                continue
            result = validate_record(resource, payload)
            for err in result.errors:
                all_errors.append(f"record[{idx}].{resource}.{err}")
    return ValidationResult(valid=not all_errors, errors=all_errors)
