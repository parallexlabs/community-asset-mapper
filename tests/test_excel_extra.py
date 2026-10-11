"""Additional Excel adapter tests."""

from pathlib import Path

from openpyxl import Workbook

from community_asset_mapper.adapters.excel import read_excel


def test_read_excel_empty_sheet(tmp_path: Path) -> None:
    path = tmp_path / "empty.xlsx"
    wb = Workbook()
    wb.save(path)
    assert read_excel(path) == []


def test_read_excel_named_sheet(tmp_path: Path) -> None:
    path = tmp_path / "named.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["COL"])
    ws.append(["val"])
    wb.save(path)
    rows = read_excel(path, sheet="Data")
    assert rows[0]["COL"] == "val"
