"""Adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from community_asset_mapper.adapters.bc_hospitals import load_bc_hospitals, row_to_record
from community_asset_mapper.adapters.csv import read_csv
from community_asset_mapper.adapters.excel import read_excel


def test_read_csv(demo_dir: Path) -> None:
    rows = read_csv(demo_dir / "data" / "hospitals.csv")
    assert len(rows) == 10
    assert "FACILITY_NAME" in rows[0]


def test_read_csv_size_limit(tmp_path: Path) -> None:
    path = tmp_path / "big.csv"
    path.write_text("a\n1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exceeds"):
        read_csv(path, max_bytes=1)


def test_read_excel(tmp_path: Path) -> None:
    path = tmp_path / "test.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["FACILITY_NAME", "CITY"])
    ws.append(["Test Hospital", "Vancouver"])
    wb.save(path)
    rows = read_excel(path)
    assert rows[0]["FACILITY_NAME"] == "Test Hospital"


def test_bc_hospitals_mapping(demo_dir: Path) -> None:
    records = load_bc_hospitals(demo_dir / "data" / "hospitals.csv")
    assert len(records) == 10
    assert records[0].organization.name
    assert records[0].location.address is not None
    assert records[0].service.service_type == "hospital"


def test_bc_hospitals_wheelchair() -> None:
    record = row_to_record(
        {"FACILITY_NAME": "X", "WHEELCHAIR_ACCESSIBLE": "Yes", "CITY": "Vancouver"}
    )
    assert record.service.wheelchair_accessible is True


def test_bc_hospitals_alt_columns() -> None:
    record = row_to_record({"Facility Name": "Test", "City": "Victoria"})
    assert record.service.name == "Test"
