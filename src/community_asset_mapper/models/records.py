"""Core record types used across the pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id() -> str:
    return str(uuid4())


class Provenance(BaseModel):
    source: str
    source_id: str | None = None
    retrieved_at: datetime | None = None
    licence: str | None = None


class GeocodeResult(BaseModel):
    latitude: float
    longitude: float
    match_type: str = "unknown"
    confidence: float = 0.0
    provider: str
    retrieved_at: datetime
    raw_reference: str
    normalized_address: str | None = None


class OrganizationRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    alternate_name: str | None = None
    description: str | None = None
    email: str | None = None
    website: str | None = None
    provenance: Provenance | None = None


class AddressRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    location_id: str
    address_1: str | None = None
    city: str | None = None
    state_province: str | None = None
    postal_code: str | None = None
    country: str = "CA"


class LocationRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    organization_id: str
    location_type: str = "physical"
    name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geocode: GeocodeResult | None = None
    address: AddressRecord | None = None


class ServiceRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    organization_id: str
    location_id: str | None = None
    name: str
    description: str | None = None
    service_type: str | None = None
    url: str | None = None
    last_verified: datetime | None = None
    hours: str | None = None
    wheelchair_accessible: bool | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class InternalRecord(BaseModel):
    """Normalized working record before HSDS export."""

    organization: OrganizationRecord
    service: ServiceRecord
    location: LocationRecord
    source_row: dict[str, str] = Field(default_factory=dict)
