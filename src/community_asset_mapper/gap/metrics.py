"""Service counts and crude population rates per demo geography."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from shapely.geometry import Point, shape

from community_asset_mapper.models.records import InternalRecord

MAUP_LIMITATIONS = (
    "Point-in-polygon assignment ignores service catchment areas.",
    "No population allocation or travel-time accessibility model is implemented.",
    "Modifiable Areal Unit Problem (MAUP) affects rates at small geographies.",
    "Geocoder positional error may mis-assign edge cases.",
)


@dataclass
class GeographyMetric:
    geography_id: str
    geography_type: str
    service_count: int
    population: int
    population_source: str
    population_date: str
    rate_per_1000: float
    weighted_population: float | None = None


@dataclass
class GapReport:
    metrics: list[GeographyMetric] = field(default_factory=lambda: list[GeographyMetric]())
    metadata: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": [m.__dict__ for m in self.metrics],
            "metadata": self.metadata,
        }


def _load_geojson(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    features = data.get("features", [])
    result: list[dict[str, Any]] = []
    for feature in features:
        props = feature.get("properties", {})
        geom = shape(feature["geometry"])
        geo_id = str(props.get("DAUID") or props.get("CSDUID") or props.get("id", ""))
        geo_type = "da" if "DAUID" in props or props.get("type") == "da" else "csd"
        result.append({"id": geo_id, "type": geo_type, "geometry": geom, "properties": props})
    return result


def _load_population(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"DAUID", "population", "source", "date"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Population CSV missing columns: {missing}")
    return df


def _service_points(records: list[InternalRecord]) -> list[Point]:
    points: list[Point] = []
    for record in records:
        lat = record.location.latitude
        lon = record.location.longitude
        if lat is not None and lon is not None:
            points.append(Point(lon, lat))
    return points


def compute_gap_metrics(
    records: list[InternalRecord],
    da_boundaries: Path,
    csd_boundaries: Path | None,
    population_csv: Path,
    geography: str = "da",
) -> GapReport:
    """Compute service counts and crude rates per geography."""
    population_df = _load_population(population_csv)
    pop_lookup: dict[str, dict[str, int | str]] = {}
    for _, row in population_df.iterrows():
        pop_lookup[str(row["DAUID"])] = {
            "population": int(row["population"]),
            "source": str(row["source"]),
            "date": str(row["date"]),
        }

    boundaries_path = da_boundaries if geography == "da" else (csd_boundaries or da_boundaries)
    polygons = _load_geojson(boundaries_path)
    points = _service_points(records)

    metrics: list[GeographyMetric] = []
    for poly in polygons:
        geo_id = poly["id"]
        geom = poly["geometry"]
        count = sum(1 for pt in points if geom.contains(pt))
        pop_info = pop_lookup.get(geo_id, {"population": 0, "source": "unknown", "date": "unknown"})
        population = int(pop_info["population"])
        rate = (count / population * 1000) if population > 0 else 0.0
        metrics.append(
            GeographyMetric(
                geography_id=geo_id,
                geography_type=geography,
                service_count=count,
                population=population,
                population_source=str(pop_info["source"]),
                population_date=str(pop_info["date"]),
                rate_per_1000=round(rate, 4),
                weighted_population=None,
            )
        )

    return GapReport(
        metrics=metrics,
        metadata={
            "geography": geography,
            "maup_limitations": list(MAUP_LIMITATIONS),
            "population_source": (
                population_df["source"].iloc[0] if len(population_df) else "unknown"
            ),
            "population_date": population_df["date"].iloc[0] if len(population_df) else "unknown",
            "method": "point-in-polygon counts and crude population rates",
        },
    )
