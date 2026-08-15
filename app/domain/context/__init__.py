"""PART 2 - feature vector per site: roads, POI gravity, competitors, grid, archetypes.

    competitors.py   pure parse + HTTP fetch of the competitor inventory (2.3)
    store.py         resolve each station to a district and upsert (2.3, I/O)

Only 2.3 (competitors) is built so far; roads/POI/grid/archetypes follow.
"""

from __future__ import annotations

from app.domain.context.competitors import (
    OCM_BASE_URL,
    CompetitorStationData,
    Connector,
    FetchResult,
    dedupe,
    fetch_ocm,
    map_access,
    parse_connections,
    parse_ocm_poi,
    tile_bbox,
)
from app.domain.context.store import StoreResult, store_stations

__all__ = [
    "OCM_BASE_URL",
    "CompetitorStationData",
    "Connector",
    "FetchResult",
    "StoreResult",
    "dedupe",
    "fetch_ocm",
    "map_access",
    "parse_connections",
    "parse_ocm_poi",
    "store_stations",
    "tile_bbox",
]
