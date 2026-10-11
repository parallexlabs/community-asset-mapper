"""Data source adapters."""

from community_asset_mapper.adapters.bc_hospitals import load_bc_hospitals
from community_asset_mapper.adapters.csv import read_csv
from community_asset_mapper.adapters.excel import read_excel

__all__ = ["load_bc_hospitals", "read_csv", "read_excel"]
