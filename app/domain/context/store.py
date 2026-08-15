"""Persisting competitor stations - PART 2.3, the I/O shell.

Kept apart from ``competitors.py`` (the pure parse/fetch) so the district
resolution and the upsert - the only parts that touch the database - are in
one place, and the layer contract stays clean: this imports ``app.models`` and
PostGIS; the parser imports neither.

**District resolution is bulk, not per-row.** A state import is hundreds of
stations, and the database is a network hop away, so resolving each point with
the full PLAN 1.4 cascade (several queries each) would be minutes of round
trips. Instead every point is placed in ONE query via ``ST_Contains`` over an
``unnest`` of the coordinates. That is containment-only - a station just off a
coastal polygon lands ``unplaced`` (NULL district) rather than snapping to the
nearest - which is the right trade for an inventory import: a competitor we
cannot place is kept, and its NULL says so.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from app.domain.context.competitors import CompetitorStationData
from app.models.competitors import CompetitorStation


@dataclass
class StoreResult:
    inserted: int = 0
    updated: int = 0
    unplaced: int = 0  # stored, but no district polygon contained the point


_BULK_CONTAIN = text("""
    SELECT t.idx, d.lgd_district_code, d.lgd_state_code
    FROM unnest(CAST(:lats AS double precision[]), CAST(:lngs AS double precision[]))
         WITH ORDINALITY AS t(lat, lng, idx)
    LEFT JOIN LATERAL (
        SELECT lgd_district_code, lgd_state_code
        FROM districts
        WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(t.lng, t.lat), 4326))
        LIMIT 1
    ) d ON true
""").bindparams(bindparam("lats"), bindparam("lngs"))


def bulk_resolve_districts(
    session: Session, points: list[tuple[float, float]]
) -> list[tuple[int | None, int | None]]:
    """Place many (lat, lng) points in their district in a single query.

    Returns one ``(district_code, state_code)`` per input point, in order;
    ``(None, None)`` where no polygon contained the point.
    """
    if not points:
        return []
    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    out: list[tuple[int | None, int | None]] = [(None, None)] * len(points)
    for idx, dcode, scode in session.execute(_BULK_CONTAIN, {"lats": lats, "lngs": lngs}).all():
        # ORDINALITY is 1-based.
        out[int(idx) - 1] = (
            int(dcode) if dcode is not None else None,
            int(scode) if scode is not None else None,
        )
    return out


def store_stations(
    session: Session,
    stations: list[CompetitorStationData],
    *,
    resolve_districts: bool = True,
    now: dt.datetime | None = None,
) -> StoreResult:
    """Upsert by ``(source, source_id)``, resolving each point to its district.

    ``resolve_districts=False`` skips the point-in-polygon step - useful in a
    test with no PostGIS, where every row simply lands with a NULL district.
    """
    result = StoreResult()
    if not stations:
        return result

    districts: list[tuple[int | None, int | None]]
    if resolve_districts:
        districts = bulk_resolve_districts(session, [(s.lat, s.lng) for s in stations])
    else:
        districts = [(None, None)] * len(stations)

    for s, (district_code, state_code) in zip(stations, districts, strict=True):
        if resolve_districts and district_code is None:
            result.unplaced += 1

        row = session.execute(
            select(CompetitorStation).where(
                CompetitorStation.source == s.source,
                CompetitorStation.source_id == s.source_id,
            )
        ).scalar_one_or_none()

        if row is None:
            row = CompetitorStation(source=s.source, source_id=s.source_id)
            session.add(row)
            result.inserted += 1
        else:
            result.updated += 1

        row.name = s.name
        row.operator = s.operator
        row.lat = s.lat
        row.lng = s.lng
        row.town = s.town
        row.postcode = s.postcode
        row.access = s.access
        row.is_operational = s.is_operational
        row.number_of_points = s.number_of_points
        row.max_power_kw = s.max_power_kw
        row.connectors = s.connectors_json()
        row.data_provider = s.data_provider
        row.source_last_status_update = s.source_last_status_update
        if resolve_districts:
            row.lgd_district_code = district_code
            row.lgd_state_code = state_code
        if now is not None:
            row.fetched_at = now

    session.flush()
    return result
