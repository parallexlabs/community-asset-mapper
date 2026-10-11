"""Offline portable SQLite snapshot export for normalized working records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
import sys
from pathlib import Path
from typing import Any

SCHEMA = "community_asset_mapper.portable_snapshot"
VERSION = "1"
SNAPSHOT_FILENAME = "snapshot.sqlite"
RECEIPT_FILENAME = "receipt.json"

MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_RECORDS = 10_000
MAX_STRING_LEN = 10_000
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 200_000

ORG_KEYS = frozenset(
    {"id", "name", "alternate_name", "description", "email", "website", "provenance"}
)
LOCATION_KEYS = frozenset(
    {
        "id",
        "organization_id",
        "name",
        "location_type",
        "latitude",
        "longitude",
        "geocode",
        "address",
    }
)
SERVICE_KEYS = frozenset(
    {
        "id",
        "organization_id",
        "location_id",
        "name",
        "description",
        "service_type",
        "url",
        "last_verified",
        "hours",
        "wheelchair_accessible",
        "extra",
    }
)
RECORD_KEYS = frozenset({"organization", "service", "location", "source_row"})
PROVENANCE_KEYS = frozenset({"source", "source_id", "retrieved_at", "licence"})

DDL = """
CREATE TABLE organizations (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    provenance_source TEXT,
    provenance_source_id TEXT,
    provenance_retrieved_at TEXT,
    provenance_licence TEXT
);

CREATE TABLE locations (
    id TEXT PRIMARY KEY NOT NULL,
    organization_id TEXT NOT NULL,
    name TEXT,
    location_type TEXT,
    latitude REAL,
    longitude REAL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE (id, organization_id)
);

CREATE TABLE services (
    id TEXT PRIMARY KEY NOT NULL,
    organization_id TEXT NOT NULL,
    location_id TEXT,
    name TEXT NOT NULL,
    service_type TEXT,
    last_verified TEXT,
    hours TEXT,
    wheelchair_accessible INTEGER CHECK (
        wheelchair_accessible IN (0, 1) OR wheelchair_accessible IS NULL
    ),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (location_id, organization_id) REFERENCES locations(id, organization_id)
);
"""


class SnapshotError(Exception):
    """Controlled validation or export failure."""


def _reject(message: str) -> None:
    raise SnapshotError(message)


def _ensure_builtin_json(
    value: Any,
    *,
    seen: set[int] | None = None,
    depth: int = 0,
    budget: list[int] | None = None,
) -> None:
    if depth > MAX_JSON_DEPTH:
        _reject("json nesting too deep")
    if seen is None:
        seen = set()
    if budget is None:
        budget = [MAX_JSON_NODES]
    budget[0] -= 1
    if budget[0] < 0:
        _reject("too many json values")
    kind = type(value)
    if value is None or kind in (str, int, float, bool):
        if kind is int and not -(2**63) <= value < 2**63:
            _reject("integer outside supported range")
        if kind is float and not _is_finite_float(value):
            _reject("nonfinite numeric value")
        if kind is str:
            if len(value) > MAX_STRING_LEN:
                _reject("string exceeds maximum length")
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                _reject("invalid unicode string")
        return
    if kind in (dict, list):
        obj_id = id(value)
        if obj_id in seen:
            _reject("cyclic structure")
        seen.add(obj_id)
        if kind is dict:
            for key, item in value.items():
                if type(key) is not str:
                    _reject("invalid json object key type")
                _ensure_builtin_json(key, seen=seen, depth=depth + 1, budget=budget)
                _ensure_builtin_json(item, seen=seen, depth=depth + 1, budget=budget)
        else:
            for item in value:
                _ensure_builtin_json(item, seen=seen, depth=depth + 1, budget=budget)
        seen.remove(obj_id)
        return
    _reject("unsupported value type")


def _check_encoded_size(value: Any) -> None:
    size = 0
    encoder = json.JSONEncoder(ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    for chunk in encoder.iterencode(value):
        size += len(chunk.encode("utf-8"))
        if size > MAX_INPUT_BYTES:
            _reject("input exceeds size limit")


def _is_finite_float(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def _require_id_string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        _reject(f"invalid {field}")
    if not value or value.strip() != value or not value.strip() or "\x00" in value:
        _reject(f"invalid {field}")
    if len(value) > MAX_STRING_LEN:
        _reject("string exceeds maximum length")
    return value


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _reject(f"invalid {field}")
    if len(value) > MAX_STRING_LEN:
        _reject("string exceeds maximum length")
    if "\x00" in value:
        _reject(f"invalid {field}")
    return value


def _optional_bool(value: Any, field: str) -> bool | None:
    if value is None:
        return None
    if value is True or value is False:
        return value
    _reject(f"invalid {field}")


def _parse_coordinate(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _reject(f"invalid {field}")
    number = float(value)
    if not _is_finite_float(number):
        _reject(f"invalid {field}")
    return number


def _validate_lat_lon(lat: float | None, lon: float | None) -> tuple[float | None, float | None]:
    if lat is None and lon is None:
        return None, None
    if lat is None or lon is None:
        _reject("latitude and longitude must both be present or both absent")
    if not (-90.0 <= lat <= 90.0):
        _reject("latitude out of range")
    if not (-180.0 <= lon <= 180.0):
        _reject("longitude out of range")
    return lat, lon


def _unknown_keys(payload: dict[str, Any], allowed: frozenset[str]) -> None:
    extra = set(payload) - allowed
    if extra:
        _reject("unknown structural keys")


def _project_provenance(value: Any) -> dict[str, str | None]:
    if value is None:
        return {
            "provenance_source": None,
            "provenance_source_id": None,
            "provenance_retrieved_at": None,
            "provenance_licence": None,
        }
    if not isinstance(value, dict):
        _reject("invalid organization provenance")
    _unknown_keys(value, PROVENANCE_KEYS)
    source = _optional_string(value.get("source"), "provenance.source")
    return {
        "provenance_source": source,
        "provenance_source_id": _optional_string(value.get("source_id"), "provenance.source_id"),
        "provenance_retrieved_at": _optional_string(
            value.get("retrieved_at"), "provenance.retrieved_at"
        ),
        "provenance_licence": _optional_string(value.get("licence"), "provenance.licence"),
    }


def _project_organization(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        _reject("invalid organization")
    _unknown_keys(value, ORG_KEYS)
    projected = {
        "id": _require_id_string(value.get("id"), "organization.id"),
        "name": _require_id_string(value.get("name"), "organization.name"),
    }
    projected.update(_project_provenance(value.get("provenance")))
    return projected


def _project_location(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        _reject("invalid location")
    _unknown_keys(value, LOCATION_KEYS)
    lat = _parse_coordinate(value.get("latitude"), "location.latitude")
    lon = _parse_coordinate(value.get("longitude"), "location.longitude")
    lat, lon = _validate_lat_lon(lat, lon)
    return {
        "id": _require_id_string(value.get("id"), "location.id"),
        "organization_id": _require_id_string(
            value.get("organization_id"), "location.organization_id"
        ),
        "name": _optional_string(value.get("name"), "location.name"),
        "location_type": _optional_string(value.get("location_type"), "location.location_type"),
        "latitude": lat,
        "longitude": lon,
    }


def _project_service(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        _reject("invalid service")
    _unknown_keys(value, SERVICE_KEYS)
    location_id_raw = value.get("location_id")
    location_id = None
    if location_id_raw is not None:
        location_id = _require_id_string(location_id_raw, "service.location_id")
    last_verified = value.get("last_verified")
    if last_verified is not None and not isinstance(last_verified, str):
        _reject("invalid service.last_verified")
    if isinstance(last_verified, str) and (
        len(last_verified) > MAX_STRING_LEN or "\x00" in last_verified
    ):
        _reject("invalid service.last_verified")
    return {
        "id": _require_id_string(value.get("id"), "service.id"),
        "organization_id": _require_id_string(
            value.get("organization_id"), "service.organization_id"
        ),
        "location_id": location_id,
        "name": _require_id_string(value.get("name"), "service.name"),
        "service_type": _optional_string(value.get("service_type"), "service.service_type"),
        "last_verified": last_verified,
        "hours": _optional_string(value.get("hours"), "service.hours"),
        "wheelchair_accessible": _optional_bool(
            value.get("wheelchair_accessible"), "service.wheelchair_accessible"
        ),
    }


def _validate_source_row(value: Any) -> None:
    if value is None:
        return
    if isinstance(value, (dict, list, str, int, float, bool)):
        return
    _reject("invalid source_row")


def _validate_record(record: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(record, dict):
        _reject("invalid record")
    _unknown_keys(record, RECORD_KEYS)
    organization = _project_organization(record.get("organization"))
    location = _project_location(record.get("location"))
    service = _project_service(record.get("service"))
    _validate_source_row(record.get("source_row"))
    if organization["id"] != service["organization_id"]:
        _reject("organization id mismatch")
    if organization["id"] != location["organization_id"]:
        _reject("organization id mismatch")
    if service["location_id"] is not None and service["location_id"] != location["id"]:
        _reject("service location mismatch")
    return organization, location, service


def _merge_entity(
    bucket: dict[str, dict[str, Any]],
    entity: dict[str, Any],
    *,
    entity_name: str,
) -> None:
    entity_id = entity["id"]
    existing = bucket.get(entity_id)
    if existing is None:
        bucket[entity_id] = dict(entity)
        return
    if existing != entity:
        _reject(f"conflicting {entity_name}")


def normalize_records(
    records: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(records, list):
        _reject("records must be a list")
    if len(records) > MAX_RECORDS:
        _reject("too many records")
    organizations: dict[str, dict[str, Any]] = {}
    locations: dict[str, dict[str, Any]] = {}
    services: dict[str, dict[str, Any]] = {}
    for record in records:
        organization, location, service = _validate_record(record)
        _merge_entity(organizations, organization, entity_name="organization")
        _merge_entity(locations, location, entity_name="location")
        _merge_entity(services, service, entity_name="service")
    org_rows = [organizations[key] for key in sorted(organizations)]
    location_rows = [locations[key] for key in sorted(locations)]
    service_rows = [services[key] for key in sorted(services)]
    return org_rows, location_rows, service_rows


def compute_logical_digest(
    organizations: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    services: list[dict[str, Any]],
) -> str:
    payload = {
        "schema": SCHEMA,
        "version": VERSION,
        "organizations": organizations,
        "locations": locations,
        "services": services,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _assert_safe_output_parent(output_directory: Path) -> None:
    if ".." in output_directory.parts:
        _reject("unsafe path component")
    if output_directory.exists() or output_directory.is_symlink():
        _reject("output directory already exists")
    parent = output_directory.parent
    if not parent.exists() or not parent.is_dir():
        _reject("output parent directory missing")
    # Inspect lexical ancestors before resolve() can conceal a symlink.
    current = output_directory if output_directory.is_absolute() else Path.cwd() / output_directory
    while True:
        if current.is_symlink():
            _reject("unsafe path component")
        if current == current.parent:
            break
        current = current.parent
    if parent.is_symlink():
        _reject("unsafe path component")


def _wheelchair_storage(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def _insert_rows(connection: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    if table == "organizations":
        connection.executemany(
            """
            INSERT INTO organizations (
                id, name, provenance_source, provenance_source_id,
                provenance_retrieved_at, provenance_licence
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["name"],
                    row["provenance_source"],
                    row["provenance_source_id"],
                    row["provenance_retrieved_at"],
                    row["provenance_licence"],
                )
                for row in rows
            ],
        )
    elif table == "locations":
        connection.executemany(
            """
            INSERT INTO locations (
                id, organization_id, name, location_type, latitude, longitude
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["organization_id"],
                    row["name"],
                    row["location_type"],
                    row["latitude"],
                    row["longitude"],
                )
                for row in rows
            ],
        )
    elif table == "services":
        connection.executemany(
            """
            INSERT INTO services (
                id, organization_id, location_id, name, service_type,
                last_verified, hours, wheelchair_accessible
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["organization_id"],
                    row["location_id"],
                    row["name"],
                    row["service_type"],
                    row["last_verified"],
                    row["hours"],
                    _wheelchair_storage(row["wheelchair_accessible"]),
                )
                for row in rows
            ],
        )
    else:
        _reject("internal table name error")


def _verify_sqlite_structure(
    db_path: Path,
    expected: dict[str, int],
    expected_rows: dict[str, list[dict[str, Any]]],
) -> tuple[int, int]:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        fk_issues = connection.execute("PRAGMA foreign_key_check").fetchall()
        if fk_issues:
            _reject("foreign key check failed")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            _reject("integrity check failed")
        counts = {
            "organizations": connection.execute("SELECT COUNT(*) FROM organizations").fetchone()[0],
            "locations": connection.execute("SELECT COUNT(*) FROM locations").fetchone()[0],
            "services": connection.execute("SELECT COUNT(*) FROM services").fetchone()[0],
        }
        for name, count in expected.items():
            if counts[name] != count:
                _reject("readback count mismatch")
        located = connection.execute(
            "SELECT COUNT(*) FROM services WHERE location_id IS NOT NULL"
        ).fetchone()[0]
        unlocated = connection.execute(
            "SELECT COUNT(*) FROM services WHERE location_id IS NULL"
        ).fetchone()[0]
        if located + unlocated != counts["services"]:
            _reject("service location count mismatch")
        null_bool = connection.execute(
            """
            SELECT COUNT(*) FROM services
            WHERE wheelchair_accessible IS NOT NULL
              AND wheelchair_accessible NOT IN (0, 1)
            """
        ).fetchone()[0]
        if null_bool:
            _reject("invalid wheelchair_accessible values")
        bad_join = connection.execute(
            """
            SELECT COUNT(*) FROM services s
            LEFT JOIN locations l
              ON s.location_id = l.id AND s.organization_id = l.organization_id
            WHERE s.location_id IS NOT NULL AND l.id IS NULL
            """
        ).fetchone()[0]
        if bad_join:
            _reject("service location join mismatch")
        queries = {
            "organizations": "SELECT * FROM organizations ORDER BY id",
            "locations": "SELECT * FROM locations ORDER BY id",
            "services": "SELECT * FROM services ORDER BY id",
        }
        for table, query in queries.items():
            cursor = connection.execute(query)
            columns = [column[0] for column in cursor.description]
            stored = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
            if stored != expected_rows[table]:
                _reject("readback projection mismatch")
        return located, unlocated
    finally:
        connection.close()


def _write_database(
    db_path: Path,
    organizations: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    services: list[dict[str, Any]],
) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        readback = connection.execute("PRAGMA foreign_keys").fetchone()
        if readback is None or readback[0] != 1:
            _reject("foreign keys not enabled")
        connection.executescript(DDL)
        _insert_rows(connection, "organizations", organizations)
        _insert_rows(connection, "locations", locations)
        _insert_rows(connection, "services", services)
        fk_issues = connection.execute("PRAGMA foreign_key_check").fetchall()
        if fk_issues:
            _reject("foreign key check failed")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            _reject("integrity check failed")
        connection.commit()
    finally:
        connection.close()


def build_receipt(
    *,
    input_records: int,
    organizations: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    services: list[dict[str, Any]],
    located_services: int,
    unlocated_services: int,
    logical_digest: str,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "logical_digest": logical_digest,
        "input_records": input_records,
        "organizations": len(organizations),
        "locations": len(locations),
        "services": len(services),
        "located_services": located_services,
        "unlocated_services": unlocated_services,
        "metadata_status": "declared_not_authenticated",
        "source_validated": False,
        "privacy_certified": False,
        "external_action_authorized": False,
        "post_write_structure_verified": True,
        "software": "community-asset-mapper",
        "software_version": "0.1.0",
    }


def export_snapshot(records: Any, output_directory: str | os.PathLike[str]) -> dict[str, Any]:
    _ensure_builtin_json(records)
    _check_encoded_size(records)
    org_rows, location_rows, service_rows = normalize_records(records)
    logical_digest = compute_logical_digest(org_rows, location_rows, service_rows)
    output_path = Path(output_directory)
    _assert_safe_output_parent(output_path)
    output_path.mkdir(mode=0o700, exist_ok=False)
    db_path = output_path / SNAPSHOT_FILENAME
    receipt_path = output_path / RECEIPT_FILENAME
    with db_path.open("xb"):
        pass
    _write_database(db_path, org_rows, location_rows, service_rows)
    located, unlocated = _verify_sqlite_structure(
        db_path,
        {
            "organizations": len(org_rows),
            "locations": len(location_rows),
            "services": len(service_rows),
        },
        {"organizations": org_rows, "locations": location_rows, "services": service_rows},
    )
    receipt = build_receipt(
        input_records=len(records),
        organizations=org_rows,
        locations=location_rows,
        services=service_rows,
        located_services=located,
        unlocated_services=unlocated,
        logical_digest=logical_digest,
    )
    with receipt_path.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, sort_keys=True, indent=2, ensure_ascii=True)
        handle.write("\n")
    return receipt


def _duplicate_key_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            _reject("duplicate json object key")
        seen.add(key)
        obj[key] = value
    return obj


def load_records_from_json_bytes(data: bytes) -> list[Any]:
    if len(data) > MAX_INPUT_BYTES:
        _reject("input exceeds size limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SnapshotError("invalid utf-8 input") from exc
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_duplicate_key_hook,
            parse_constant=lambda _x: _reject("nonfinite json value"),
        )
    except SnapshotError:
        raise
    except (ValueError, RecursionError) as exc:
        raise SnapshotError("invalid json input") from exc
    if not isinstance(parsed, list):
        _reject("top-level json must be a list")
    _ensure_builtin_json(parsed)
    return parsed


def load_records_from_json_file(path: Path) -> list[Any]:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            _reject("input must be a regular file")
        data = handle.read(MAX_INPUT_BYTES + 1)
    return load_records_from_json_bytes(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="export_portable_snapshot")
    parser.add_argument("input_json")
    parser.add_argument("output_dir")
    args = parser.parse_args(argv)
    try:
        records = load_records_from_json_file(Path(args.input_json))
        receipt = export_snapshot(records, args.output_dir)
    except (SnapshotError, OSError, sqlite3.Error, ValueError, OverflowError, RecursionError):
        print("export failed", file=sys.stderr)
        return 2
    print(json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
