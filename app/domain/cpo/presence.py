"""How much of each network already sits around a site - PART 6.

The 34 site factors answer *should anything be built here*. Every one of them
is a property of the land and is identical whichever operator signs. This
module answers the other half: **the same neighbouring charger means a
different thing depending on who you sign with.**

A charger a kilometre away run by network A is competition for everybody. Sign
with network A yourself and it is competition *and a split*: A's app now has
two places to send the same drivers, one of which is yours. Sign with B and
that neighbour goes back to being ordinary competition. ``competitors_near``
in ``report/assemble.py`` counts neighbours once, operator-blind, and so
cannot say this - it is the right count for report section 07 and the wrong
one for section 06.

Four counts per network, and nothing else:

    stations_district   the local installed base - drivers who already have
                        this operator's app on their phone
    stations_state      service depth; three sites in a state means no
                        engineer within reach of a fault
    own_within_3km      the split, near
    own_within_10km     the split, wide

**No score is computed here and none should be.** These are counts that sit
beside the money in the report and are never blended into it (OVERVIEW.md §8,
AGENTS.md constraint 1). The weighting between "pays more" and "brings more
drivers" belongs to the site owner.

The DB half is one query; the arithmetic half is ``fold_presence``, which is
pure and carries every decision worth testing.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.cpo.identity import canonical_operator

#: The two radii. 3 km is the radius report section 07 already treats as
#: "on top of you"; 10 km is wide enough to catch a station a driver would
#: still be routed to and narrow enough that it is not simply the district.
OWN_NEAR_M = 3_000
OWN_WIDE_M = 10_000

#: Degrees of latitude that two records of the same physical station may
#: differ by and still be folded into one. ~55 m at Indian latitudes.
#:
#: Necessary because ``competitor_stations`` is upserted by ``(source,
#: source_id)`` and the same charger seen through Open Charge Map and through
#: the operator's own feed is deliberately two rows until the PLAN 2.3 dedupe.
#: Counting rows would double-count exactly the operators we cover best.
#:
#: This is a COARSE, WITHIN-OPERATOR dedupe and not that dedupe: it never
#: merges stations more than ~55 m apart, and two records of one station that
#: straddle a cell boundary stay two. The residual error therefore always
#: over-counts, never under-counts - it can make a network look more present
#: than it is, and never hides a station that would argue against it.
GRID_DEG = 0.0005


@dataclass(frozen=True)
class StationRow:
    """One row of ``competitor_stations``, already filtered to what matters."""

    operator: str | None
    lat: float
    lng: float
    in_district: bool
    in_state: bool
    within_near: bool
    within_wide: bool


@dataclass(frozen=True)
class OperatorPresence:
    """One network's footprint around one site. Counts only."""

    canonical: str
    stations_district: int
    stations_state: int
    own_within_3km: int
    own_within_10km: int


def cell_of(lat: float, lng: float) -> tuple[int, int]:
    """The grid cell a point falls in. Two records in one cell are one station."""
    return round(lat / GRID_DEG), round(lng / GRID_DEG)


def fold_presence(rows: Iterable[StationRow]) -> dict[str, OperatorPresence]:
    """Fold raw station rows into one entry per canonical network. Pure.

    Rows whose operator does not resolve to a canonical network are dropped
    here rather than bucketed under their raw name: an unmatched name is a gap
    in ``identity.OPERATOR_ALIASES``, and reporting it as though it were a
    network would put a count next to a name nobody can act on. The gap itself
    is reported separately, by ``identity.coverage``.
    """
    buckets: dict[str, dict[str, set[tuple[int, int]]]] = {}
    for row in rows:
        match = canonical_operator(row.operator)
        if match.canonical is None:
            continue
        seen = buckets.setdefault(
            match.canonical, {"district": set(), "state": set(), "near": set(), "wide": set()}
        )
        cell = cell_of(row.lat, row.lng)
        if row.in_district:
            seen["district"].add(cell)
        if row.in_state:
            seen["state"].add(cell)
        if row.within_near:
            seen["near"].add(cell)
        if row.within_wide:
            seen["wide"].add(cell)

    return {
        name: OperatorPresence(
            canonical=name,
            stations_district=len(seen["district"]),
            stations_state=len(seen["state"]),
            own_within_3km=len(seen["near"]),
            own_within_10km=len(seen["wide"]),
        )
        for name, seen in buckets.items()
    }


#: Everything in the state, plus everything within the wide radius - the
#: second disjunct matters at a district edge, where a station 4 km away can
#: sit in the next state. Distances on ``::geography``, per the geometry
#: convention; the point is built once in a CTE rather than three times.
_PRESENCE_SQL = text(f"""
    WITH pin AS (
        SELECT ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography AS g
    )
    SELECT c.operator,
           c.lat,
           c.lng,
           COALESCE(c.lgd_district_code = :district, FALSE) AS in_district,
           COALESCE(c.lgd_state_code = :state, FALSE)       AS in_state,
           ST_DWithin(c.geom::geography, pin.g, {OWN_NEAR_M}) AS within_near,
           ST_DWithin(c.geom::geography, pin.g, {OWN_WIDE_M}) AS within_wide
    FROM competitor_stations c, pin
    WHERE COALESCE(c.lgd_state_code = :state, FALSE)
       OR ST_DWithin(c.geom::geography, pin.g, {OWN_WIDE_M})
""")


def operator_presence(
    session: Session,
    *,
    lat: float,
    lng: float,
    lgd_district_code: int,
    lgd_state_code: int,
) -> dict[str, OperatorPresence]:
    """Every network's footprint around this point. One query, then a fold."""
    rows = session.execute(
        _PRESENCE_SQL,
        {"lat": lat, "lng": lng, "district": lgd_district_code, "state": lgd_state_code},
    ).all()
    return fold_presence(
        StationRow(
            operator=operator,
            lat=float(row_lat),
            lng=float(row_lng),
            in_district=bool(in_district),
            in_state=bool(in_state),
            within_near=bool(within_near),
            within_wide=bool(within_wide),
        )
        for operator, row_lat, row_lng, in_district, in_state, within_near, within_wide in rows
    )
