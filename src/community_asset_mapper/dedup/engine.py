"""Blocking, scoring, and merge workflow for deduplication."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from community_asset_mapper.dedup.scoring import jaro_winkler
from community_asset_mapper.models.records import InternalRecord


@dataclass
class DuplicateGroup:
    record_ids: list[str]
    score: float
    matched_fields: list[str]
    reasons: list[str]
    recommended_action: str = "review"

    def to_dict(self) -> dict[str, object]:
        return {
            "record_ids": self.record_ids,
            "score": self.score,
            "matched_fields": self.matched_fields,
            "reasons": self.reasons,
            "recommended_action": self.recommended_action,
        }


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _postal_key(record: InternalRecord) -> str:
    if record.location.address and record.location.address.postal_code:
        return record.location.address.postal_code[:3].upper()
    return "UNK"


def _blocking_key(record: InternalRecord) -> str:
    name_token = _normalize_name(record.organization.name).split()[:2]
    return f"{_postal_key(record)}:{'-'.join(name_token)}"


def _score_pair(a: InternalRecord, b: InternalRecord) -> tuple[float, list[str], list[str]]:
    matched: list[str] = []
    reasons: list[str] = []
    name_score = jaro_winkler(a.organization.name, b.organization.name)
    if name_score >= 0.85:
        matched.append("organization.name")
        reasons.append(f"name similarity {name_score:.2f}")

    postal_a = a.location.address.postal_code if a.location.address else ""
    postal_b = b.location.address.postal_code if b.location.address else ""
    if postal_a and postal_b and postal_a.upper() == postal_b.upper():
        matched.append("address.postal_code")
        reasons.append("postal code match")

    if (
        a.location.latitude is not None
        and b.location.latitude is not None
        and a.location.longitude is not None
        and b.location.longitude is not None
    ):
        lat_diff = abs(a.location.latitude - b.location.latitude)
        lon_diff = abs(a.location.longitude - b.location.longitude)
        if lat_diff < 0.001 and lon_diff < 0.001:
            matched.append("coordinates")
            reasons.append("coordinate differences below 0.001 degrees")

    weights = {"organization.name": 0.6, "address.postal_code": 0.25, "coordinates": 0.15}
    score = sum(weights.get(f, 0.1) for f in matched)
    if name_score >= 0.85:
        score = max(score, name_score * 0.6 + (0.4 if len(matched) > 1 else 0))
    return min(score, 1.0), matched, reasons


def propose_duplicates(
    records: list[InternalRecord],
    threshold: float = 0.85,
) -> list[DuplicateGroup]:
    """Propose duplicate groups using blocking and Jaro-Winkler scoring."""
    blocks: dict[str, list[InternalRecord]] = {}
    for record in records:
        blocks.setdefault(_blocking_key(record), []).append(record)

    groups: list[DuplicateGroup] = []
    seen_pairs: set[frozenset[str]] = set()

    for block_records in blocks.values():
        if len(block_records) < 2:
            continue
        for i, a in enumerate(block_records):
            for b in block_records[i + 1 :]:
                pair = frozenset({a.service.id, b.service.id})
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                score, matched, reasons = _score_pair(a, b)
                if score >= threshold:
                    action = "merge" if score >= 0.95 else "review"
                    groups.append(
                        DuplicateGroup(
                            record_ids=[a.service.id, b.service.id],
                            score=score,
                            matched_fields=matched,
                            reasons=reasons,
                            recommended_action=action,
                        )
                    )
    return groups


def review_group(group: DuplicateGroup) -> str:
    """Return human-readable review summary for a duplicate group."""
    return (
        f"Group {group.record_ids} score={group.score:.2f} "
        f"action={group.recommended_action}: {', '.join(group.reasons)}"
    )


def apply_merges(
    records: list[InternalRecord],
    groups: list[DuplicateGroup],
    only_merge: bool = True,
) -> tuple[list[InternalRecord], list[dict[str, object]]]:
    """Apply merge recommendations, returning deduplicated records and audit entries."""
    id_map = {r.service.id: r for r in records}
    remove_ids: set[str] = set()
    audit: list[dict[str, object]] = []

    for group in groups:
        if only_merge and group.recommended_action != "merge":
            continue
        if len(group.record_ids) < 2:
            continue
        canonical_id = group.record_ids[0]
        for dup_id in group.record_ids[1:]:
            if dup_id not in id_map or dup_id in remove_ids:
                continue
            remove_ids.add(dup_id)
            audit.append(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "action": "merge",
                    "canonical_id": canonical_id,
                    "merged_id": dup_id,
                    "score": group.score,
                    "matched_fields": group.matched_fields,
                    "reasons": group.reasons,
                }
            )

    kept = [r for r in records if r.service.id not in remove_ids]
    return kept, audit


def write_audit_log(audit_entries: list[dict[str, object]], path: Path) -> None:
    """Append audit entries to a JSONL log file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for entry in audit_entries:
            handle.write(json.dumps(entry) + "\n")
