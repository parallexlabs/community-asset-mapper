"""Network timeout helpers."""

from __future__ import annotations

DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_TIMEOUT_SECONDS = 120.0


def bounded_timeout(seconds: float, maximum: float = MAX_TIMEOUT_SECONDS) -> float:
    """Return a timeout bounded to a safe maximum."""
    if seconds <= 0:
        raise ValueError("Timeout must be positive")
    return min(seconds, maximum)
