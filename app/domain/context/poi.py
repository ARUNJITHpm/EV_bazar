"""POI gravity around a site - PART 2.2, on OpenStreetMap via Overpass.

Counts of the place types that generate charging demand, in the 500 m / 1 km /
3 km rings PLAN 2.2 specifies, plus the **dwell-anchor score**: does anything
near the site hold a driver for 30-45 minutes? A DC fast charger next to
nothing is a charger nobody waits at - that sentence is the whole feature.

``build_poi_query`` and ``parse_pois`` are pure; only ``fetch_poi_gravity``
touches the network. One query at the outer ring serves all three rings - the
parse buckets each hit by its distance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.context.overpass import OverpassClient
from app.domain.context.roads import _equirectangular_m

#: PLAN 2.2's rings, metres, inner to outer.
RINGS_M = (500, 1000, 3000)

#: Category -> the OSM tag filters that mean it. Kept explicit and small: a
#: category we cannot name is a category the report cannot explain.
CATEGORY_FILTERS: dict[str, tuple[str, ...]] = {
    "food": ('["amenity"~"^(restaurant|cafe|fast_food|food_court)$"]',),
    "retail": ('["shop"]["shop"!~"^(mall)$"]',),
    "hotel": ('["tourism"~"^(hotel|guest_house|resort)$"]',),
    "hospital": ('["amenity"~"^(hospital|clinic)$"]',),
    "office": ('["office"]',),
    "mall": ('["shop"="mall"]',),
    "fuel": ('["amenity"="fuel"]',),
}

#: What plausibly holds a driver 30-45 min. A mall or food court anchors a
#: fast-charge session outright; food, hotels and hospitals hold some visits;
#: a fuel station holds nobody but marks a forecourt habit. Weights are the
#: v0 editorial call, stated here so they can be argued with.
DWELL_WEIGHTS: dict[str, float] = {
    "mall": 3.0,
    "food": 1.0,
    "hotel": 1.5,
    "hospital": 1.5,
    "office": 0.5,
    "retail": 0.25,
    "fuel": 0.0,
}

#: Dwell is judged inside this ring - a mall 3 km away anchors nobody's session.
DWELL_RING_M = 1000


@dataclass(frozen=True)
class PoiGravity:
    """PART 2.2's slice of the context vector.

    ``counts`` is ``{ring_m: {category: n}}`` with every ring and category
    present (zero-filled) once a response parsed at all - a missing *response*
    is represented by None at the caller, never by fake zeros.
    """

    counts: dict[int, dict[str, int]]
    dwell_anchor_score: float
    #: Named anchors inside the dwell ring, best first - the report shows
    #: these, because "Technopark campus, 2 hotels" persuades where a score
    #: cannot.
    dwell_anchors: tuple[str, ...]


def build_poi_query(lat: float, lng: float, *, radius_m: int = RINGS_M[-1]) -> str:
    """One Overpass QL query for every tracked category at the outer ring.

    ``out center`` collapses ways/relations (a mall is a building outline) to
    one representative point, which is all the ring-bucketing needs.
    """
    clauses = []
    for filters in CATEGORY_FILTERS.values():
        for f in filters:
            clauses.append(f"nwr(around:{radius_m},{lat},{lng}){f};")
    body = "\n  ".join(clauses)
    return f"[out:json][timeout:45];\n(\n  {body}\n);\nout center tags;"


def _element_point(el: dict[str, Any]) -> tuple[float, float] | None:
    if "lat" in el and "lon" in el:
        return float(el["lat"]), float(el["lon"])
    center = el.get("center")
    if isinstance(center, dict) and "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None


def _element_category(tags: dict[str, Any]) -> str | None:
    amenity = str(tags.get("amenity") or "")
    if amenity in ("restaurant", "cafe", "fast_food", "food_court"):
        return "food"
    if amenity in ("hospital", "clinic"):
        return "hospital"
    if amenity == "fuel":
        return "fuel"
    if str(tags.get("shop") or "") == "mall":
        return "mall"
    if tags.get("shop"):
        return "retail"
    if str(tags.get("tourism") or "") in ("hotel", "guest_house", "resort"):
        return "hotel"
    if tags.get("office"):
        return "office"
    return None


def parse_pois(payload: Any, lat: float, lng: float) -> PoiGravity | None:
    """Ring-bucketed counts + the dwell score from one Overpass body. Pure.

    None for a malformed body (the fetch failed to mean anything); zero-filled
    counts for a well-formed empty one (OSM genuinely has nothing mapped
    there - which for India is itself worth a ledger line, but it is a true
    zero, not an unknown).
    """
    elements = payload.get("elements") if isinstance(payload, dict) else None
    if not isinstance(elements, list):
        return None

    counts: dict[int, dict[str, int]] = {
        ring: dict.fromkeys(CATEGORY_FILTERS, 0) for ring in RINGS_M
    }
    dwell_score = 0.0
    anchors: list[tuple[float, str]] = []
    seen: set[tuple[str, int]] = set()

    for el in elements:
        if not isinstance(el, dict):
            continue
        key = (str(el.get("type")), int(el.get("id", 0)))
        if key in seen:  # the union query can return one element twice
            continue
        seen.add(key)

        tags = el.get("tags") if isinstance(el.get("tags"), dict) else {}
        category = _element_category(tags)
        point = _element_point(el)
        if category is None or point is None:
            continue

        distance = _equirectangular_m(lat, lng, *point)
        for ring in RINGS_M:
            if distance <= ring:
                counts[ring][category] += 1

        if distance <= DWELL_RING_M:
            weight = DWELL_WEIGHTS.get(category, 0.0)
            dwell_score += weight
            if weight >= 1.0:
                anchors.append((weight, str(tags.get("name") or category)))

    anchors.sort(key=lambda a: a[0], reverse=True)
    return PoiGravity(
        counts=counts,
        dwell_anchor_score=round(dwell_score, 2),
        dwell_anchors=tuple(name for _, name in anchors[:5]),
    )


def fetch_poi_gravity(client: OverpassClient, lat: float, lng: float) -> PoiGravity | None:
    """Fetch + parse. The only function here that touches the network."""
    return parse_pois(client.query(build_poi_query(lat, lng)), lat, lng)
