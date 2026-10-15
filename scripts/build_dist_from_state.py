"""Build dist/ from .cam/state.json without loading the full CLI."""

from __future__ import annotations

import json
from pathlib import Path

from community_asset_mapper.models.records import InternalRecord
from community_asset_mapper.site.generator import SiteConfig, build_site


def main() -> None:
    state_path = Path(".cam/state.json")
    records = [
        InternalRecord.model_validate(item)
        for item in json.loads(state_path.read_text(encoding="utf-8"))
    ]
    out = Path("dist")
    path = build_site(records, out, SiteConfig(no_tiles=True))
    print(path)


if __name__ == "__main__":
    main()
