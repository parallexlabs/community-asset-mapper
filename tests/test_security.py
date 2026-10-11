"""Security module tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from community_asset_mapper.security import (
    bounded_timeout,
    escape_csv_cell,
    escape_html,
    safe_path,
    safe_yaml_load,
    validate_url,
)


def test_validate_url_accepts_https() -> None:
    assert validate_url("https://example.com/path") == "https://example.com/path"


def test_validate_url_rejects_javascript() -> None:
    with pytest.raises(ValueError, match="javascript"):
        validate_url("javascript:alert(1)")


def test_validate_url_rejects_data() -> None:
    with pytest.raises(ValueError, match="data"):
        validate_url("data:text/html,<script>alert(1)</script>")


def test_validate_url_rejects_protocol_relative() -> None:
    with pytest.raises(ValueError, match="Protocol-relative"):
        validate_url("//evil.com/path")


def test_validate_url_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate_url("   ")


def test_validate_url_rejects_unknown_scheme() -> None:
    with pytest.raises(ValueError, match="scheme"):
        validate_url("ftp://example.com")


def test_escape_html() -> None:
    assert escape_html("<script>") == "&lt;script&gt;"


def test_escape_csv_cell_formula_injection() -> None:
    assert escape_csv_cell("=SUM(A1)").startswith("'")


def test_escape_csv_cell_plus_prefix() -> None:
    assert escape_csv_cell("+1234").startswith("'")


def test_escape_csv_cell_minus_prefix() -> None:
    assert escape_csv_cell("-1234").startswith("'")


def test_escape_csv_cell_at_prefix() -> None:
    assert escape_csv_cell("@cmd").startswith("'")


def test_escape_csv_cell_quotes_commas() -> None:
    assert escape_csv_cell('a,b') == '"a,b"'


def test_safe_path_allows_child(tmp_path: Path) -> None:
    child = safe_path(tmp_path, "subdir/file.txt")
    assert child == (tmp_path / "subdir" / "file.txt").resolve()


def test_safe_path_blocks_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes"):
        safe_path(tmp_path, "../outside.txt")


def test_safe_yaml_load(tmp_path: Path) -> None:
    path = tmp_path / "test.yaml"
    path.write_text(yaml.dump({"key": "value"}), encoding="utf-8")
    assert safe_yaml_load(path) == {"key": "value"}


def test_safe_yaml_load_size_limit(tmp_path: Path) -> None:
    path = tmp_path / "big.yaml"
    path.write_text("x" * 100, encoding="utf-8")
    with pytest.raises(ValueError, match="exceeds"):
        safe_yaml_load(path, max_bytes=10)


def test_bounded_timeout_caps() -> None:
    assert bounded_timeout(200.0) == 120.0


def test_bounded_timeout_rejects_zero() -> None:
    with pytest.raises(ValueError):
        bounded_timeout(0)
