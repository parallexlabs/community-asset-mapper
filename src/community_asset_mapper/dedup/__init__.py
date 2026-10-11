"""Explainable deduplication engine."""

from community_asset_mapper.dedup.engine import (
    DuplicateGroup,
    apply_merges,
    propose_duplicates,
    review_group,
    write_audit_log,
)

__all__ = [
    "DuplicateGroup",
    "apply_merges",
    "propose_duplicates",
    "review_group",
    "write_audit_log",
]
