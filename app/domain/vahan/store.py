"""Persisting VAHAN registrations - PART 4.1, the I/O shell.

Kept apart from ``parse.py`` (which touches neither selenium nor the database)
so district resolution and the upsert - the only steps that reach out - are in
one place. Two jobs:

  * place each RTO's office coordinate in its district with ONE point-in-polygon
    query (the same bulk helper the competitor import uses - resolving hundreds
    of points one-by-one over a remote database would be minutes of round
    trips);
  * upsert the aggregated district slices, keyed on the snapshot so a re-run of
    the same day is idempotent while a new day appends a fresh reading.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.context.store import bulk_resolve_districts
from app.domain.vahan.parse import RtoClassCount, aggregate_by_district
from app.models.vahan import VahanEvRegistration

#: VAHAN's two-letter state code -> LGD state code, for the focus states. Used
#: only as the fallback state for an RTO whose point failed to place: the state
#: is known from the RTO itself even when no district polygon contained it.
STATE_CODE_TO_LGD: dict[str, int] = {"KL": 32, "TN": 33}


@dataclass(frozen=True)
class RtoRef:
    """One RTO from the seed: its identity and its office coordinate."""

    state_code: str
    rto: str
    lat: float | None
    lng: float | None


@dataclass
class IngestResult:
    rtos: int = 0
    placed: int = 0
    unplaced: int = 0
    slices: int = 0
    inserted: int = 0
    updated: int = 0


def resolve_rto_districts(
    session: Session, refs: list[RtoRef]
) -> dict[tuple[str, str], tuple[int | None, int | None]]:
    """Place every RTO office coordinate in its district, in one query.

    Returns ``(state_code, rto) -> (lgd_district_code, lgd_state_code)``. An RTO
    with no coordinate, or one no polygon contained, gets ``(None, <known LGD
    state>)`` - the district is lost but the state is not, because it comes from
    the RTO's own two-letter code, not from the point.
    """
    placeable = [r for r in refs if r.lat is not None and r.lng is not None]
    resolved = bulk_resolve_districts(
        session,
        [(float(r.lat), float(r.lng)) for r in placeable],  # type: ignore[arg-type]
    )

    out: dict[tuple[str, str], tuple[int | None, int | None]] = {}
    # start everyone at "unplaced, but state known", then overwrite the placeable
    for r in refs:
        out[(r.state_code, r.rto)] = (None, STATE_CODE_TO_LGD.get(r.state_code))
    for r, (district, state) in zip(placeable, resolved, strict=True):
        # PIP state wins when the point placed (it is the district's true state,
        # which can differ from the RTO's code near a border); the known state
        # is the fallback when it did not.
        out[(r.state_code, r.rto)] = (
            district,
            state if state is not None else STATE_CODE_TO_LGD.get(r.state_code),
        )
    return out


def ingest(
    session: Session,
    counts: list[RtoClassCount],
    refs: list[RtoRef],
    *,
    snapshot_date: dt.date,
    source_sha256: str,
    resolve_districts: bool = True,
    now: dt.datetime | None = None,
) -> IngestResult:
    """Resolve, aggregate and upsert a whole scrape.

    ``resolve_districts=False`` skips the point-in-polygon step - for a test with
    no PostGIS, where every RTO lands in the unplaced (state-only) bucket.
    """
    result = IngestResult(rtos=len(refs))

    if resolve_districts:
        placement = resolve_rto_districts(session, refs)
    else:
        placement = {
            (r.state_code, r.rto): (None, STATE_CODE_TO_LGD.get(r.state_code)) for r in refs
        }
    result.placed = sum(1 for d, _ in placement.values() if d is not None)
    result.unplaced = result.rtos - result.placed

    slices = aggregate_by_district(counts, placement)
    result.slices = len(slices)

    for s in slices:
        row = session.execute(
            select(VahanEvRegistration).where(
                VahanEvRegistration.lgd_district_code.is_(s.lgd_district_code)
                if s.lgd_district_code is None
                else VahanEvRegistration.lgd_district_code == s.lgd_district_code,
                VahanEvRegistration.snapshot_date == snapshot_date,
                VahanEvRegistration.period == s.period,
                VahanEvRegistration.fuel_category == s.fuel,
                VahanEvRegistration.vehicle_class == s.vehicle_class,
            )
        ).scalar_one_or_none()

        if row is None:
            row = VahanEvRegistration(
                lgd_district_code=s.lgd_district_code,
                snapshot_date=snapshot_date,
                period=s.period,
                fuel_category=s.fuel,
                vehicle_class=s.vehicle_class,
            )
            session.add(row)
            result.inserted += 1
        else:
            result.updated += 1

        row.lgd_state_code = s.lgd_state_code
        row.count = s.count
        row.rto_count = s.rto_count
        row.source_sha256 = source_sha256
        if now is not None:
            row.ingested_at = now

    session.flush()
    return result
