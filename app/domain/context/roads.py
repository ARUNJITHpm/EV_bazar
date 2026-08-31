"""Road features around a site - PART 2.1, on OpenStreetMap via Overpass.

What the report needs from the road network, in order of how much it moves a
verdict: is the site on or near a major road (and which), how far in metres,
whether that road is a divided carriageway, and how tangled the immediate
network is (junction count as a crude access/exposure proxy).

Same split as every other source in this codebase: ``build_roads_query`` and
``parse_roads`` are pure - the query is a string, the parse is geometry over a
fixture-able JSON body - and only ``fetch_road_features`` touches the network.

**What v0 deliberately does not claim:** the median-access direction (PLAN
2.1's "wrong side of a divided highway loses ~half its addressable traffic").
Judging which side of the median the site sits on needs carriageway-pair
matching we have not built; ``divided`` says the penalty MAY apply and the
report's ledger says it was not assessed. Stating the limit beats guessing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.domain.context.overpass import OverpassClient

#: Major-road classes, in OSM's own vocabulary. trunk|primary is PLAN 2.1's
#: NH/SH filter; motorway (access-controlled expressways) sits above trunk.
MAJOR_CLASSES = ("motorway", "trunk", "primary", "secondary")

#: Search radius for the nearest major road. A site further than this from any
#: major road is genuinely off-network, and None says so.
ROAD_RADIUS_M = 2000

#: PLAN 2.1: junction count within 500 m.
JUNCTION_RADIUS_M = 500

_EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class RoadFeatures:
    """The feature slice PART 2.1 contributes to a site's context vector.

    Every field is Optional: real sites will be missing data (AGENTS.md's
    null-handling rule), and a missing feature must stay visibly missing
    rather than default to a flattering zero.
    """

    nearest_class: str | None
    #: The road's ``ref`` tag ("NH 66") when present, else its ``name``.
    nearest_ref: str | None
    distance_m: float | None
    #: True when the nearest major road is mapped as a carriageway pair
    #: (oneway/dual_carriageway) - the median-access penalty MAY apply.
    divided: bool | None
    junction_count_500m: int | None


def build_roads_query(lat: float, lng: float, *, radius_m: int = ROAD_RADIUS_M) -> str:
    """Overpass QL for every major-class way near the point, with geometry.

    ``out body geom`` returns both node ids (for junction counting - a node
    shared by two ways IS a junction) and per-way coordinate arrays (for the
    distance calculation). One query serves both features.
    """
    classes = "|".join(MAJOR_CLASSES)
    return (
        "[out:json][timeout:45];\n"
        f'way(around:{radius_m},{lat},{lng})["highway"~"^({classes})$"];\n'
        "out body geom;"
    )


def _equirectangular_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Point distance in metres. Equirectangular is centimetre-exact at the
    sub-2 km scales this module works at; haversine would be ceremony."""
    x = math.radians(lng2 - lng1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return math.hypot(x, y) * _EARTH_RADIUS_M


def _point_segment_distance_m(
    lat: float, lng: float, a: tuple[float, float], b: tuple[float, float]
) -> float:
    """Distance from the site to one road segment, in metres, done in a local
    metric projection so the perpendicular foot is geometrically honest."""
    cos_lat = math.cos(math.radians(lat))

    def project(p: tuple[float, float]) -> tuple[float, float]:
        return (
            math.radians(p[1] - lng) * cos_lat * _EARTH_RADIUS_M,
            math.radians(p[0] - lat) * _EARTH_RADIUS_M,
        )

    ax, ay = project(a)
    bx, by = project(b)
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx, ay + t * dy)


def _way_distance_m(lat: float, lng: float, geometry: list[dict[str, Any]]) -> float | None:
    points = [
        (float(g["lat"]), float(g["lon"]))
        for g in geometry
        if isinstance(g, dict) and "lat" in g and "lon" in g
    ]
    if not points:
        return None
    if len(points) == 1:
        return _equirectangular_m(lat, lng, *points[0])
    return min(
        _point_segment_distance_m(lat, lng, a, b) for a, b in zip(points, points[1:], strict=False)
    )


def _is_divided(tags: dict[str, Any]) -> bool:
    """Carriageway-pair heuristic: OSM maps a divided road as two oneway ways
    (or tags dual_carriageway explicitly)."""
    return tags.get("oneway") == "yes" or tags.get("dual_carriageway") == "yes"


def _class_rank(highway: str) -> int:
    try:
        return MAJOR_CLASSES.index(highway)
    except ValueError:
        return len(MAJOR_CLASSES)


def parse_roads(
    payload: Any,
    lat: float,
    lng: float,
    *,
    junction_radius_m: float = JUNCTION_RADIUS_M,
) -> RoadFeatures:
    """The feature slice from one Overpass body. Pure.

    Nearest = smallest distance, ties broken by class rank so a trunk beats a
    secondary at equal distance. Junctions = nodes shared by two or more of
    the fetched ways whose nearest occurrence is within the junction radius.
    An empty or malformed body yields all-None features, never a guess.
    """
    elements = payload.get("elements") if isinstance(payload, dict) else None
    if not isinstance(elements, list):
        return RoadFeatures(None, None, None, None, None)

    best: tuple[float, int, dict[str, Any]] | None = None
    node_owners: dict[int, int] = {}
    node_distance: dict[int, float] = {}

    for el in elements:
        if not isinstance(el, dict) or el.get("type") != "way":
            continue
        tags = el.get("tags") if isinstance(el.get("tags"), dict) else {}
        geometry = el.get("geometry") if isinstance(el.get("geometry"), list) else []
        distance = _way_distance_m(lat, lng, geometry)
        if distance is not None:
            rank = _class_rank(str(tags.get("highway", "")))
            if best is None or (distance, rank) < (best[0], best[1]):
                best = (distance, rank, tags)

        nodes = el.get("nodes") if isinstance(el.get("nodes"), list) else []
        for node_id, g in zip(nodes, geometry, strict=False):
            if not isinstance(node_id, int) or not isinstance(g, dict):
                continue
            node_owners[node_id] = node_owners.get(node_id, 0) + 1
            d = _equirectangular_m(lat, lng, float(g["lat"]), float(g["lon"]))
            node_distance[node_id] = min(d, node_distance.get(node_id, math.inf))

    junctions = sum(
        1
        for node_id, owners in node_owners.items()
        if owners >= 2 and node_distance.get(node_id, math.inf) <= junction_radius_m
    )

    if best is None:
        return RoadFeatures(None, None, None, None, junction_count_500m=junctions)

    distance, _, tags = best
    return RoadFeatures(
        nearest_class=str(tags.get("highway")) if tags.get("highway") else None,
        nearest_ref=str(tags.get("ref") or tags.get("name") or "") or None,
        distance_m=round(distance, 1),
        divided=_is_divided(tags),
        junction_count_500m=junctions,
    )


def fetch_road_features(client: OverpassClient, lat: float, lng: float) -> RoadFeatures:
    """Fetch + parse. The only function here that touches the network."""
    return parse_roads(client.query(build_roads_query(lat, lng)), lat, lng)
