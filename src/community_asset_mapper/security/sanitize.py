"""HTML, CSV, and URL sanitization."""

from __future__ import annotations

import html
from urllib.parse import urlparse

_DANGEROUS_SCHEMES = frozenset({"javascript", "data", "vbscript"})
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def validate_url(value: str) -> str:
    """Validate a URL; reject dangerous schemes and protocol-relative URLs."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("URL must not be empty")
    if stripped.startswith("//"):
        raise ValueError("Protocol-relative URLs are not allowed")
    parsed = urlparse(stripped)
    if not parsed.scheme:
        raise ValueError("URL must include a scheme")
    scheme = parsed.scheme.lower()
    if scheme in _DANGEROUS_SCHEMES:
        raise ValueError(f"URL scheme '{scheme}' is not allowed")
    if scheme not in {"http", "https", "mailto", "tel"}:
        raise ValueError(f"URL scheme '{scheme}' is not allowed")
    return stripped


def escape_html(value: str) -> str:
    """Escape HTML special characters."""
    return html.escape(value, quote=True)


def escape_csv_cell(value: str) -> str:
    """Escape CSV cell content and neutralize spreadsheet formula injection."""
    if not value:
        return value
    if value[0] in _CSV_FORMULA_PREFIXES:
        value = "'" + value
    if any(ch in value for ch in ('"', ",", "\n", "\r")):
        return '"' + value.replace('"', '""') + '"'
    return value
