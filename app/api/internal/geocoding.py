"""Geocoding console - PART 1.3 L6 and PART C.2.

Two jobs on one screen, because they are the same job:

* the **funnel** - how many addresses each cascade level resolved, and what the
  paid levels cost. This is the evidence for Part 1's exit criteria, and for
  "median cascade cost per address = Rs 0"; without it those are assertions.
* the **manual queue** - the addresses the cascade refused, busiest first, with
  the reason it refused, so an operator can place the point in about twenty
  seconds and never be asked again.

Guarded: mounted on the ``guarded`` router in ``api/internal/__init__.py``, not
by a decorator here (PLAN C.0).
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.internal.console_auth import require_operator
from app.db import get_session
from app.domain.resolution import manual
from app.metering.pricing import billing_month
from app.models.api_usage import ApiUsageEvent
from app.models.geocode import GeocodeCache
from app.models.manual_queue import GeocodeManualQueue, QueueStatus

router = APIRouter()


# --- funnel ----------------------------------------------------------------


class LevelOut(BaseModel):
    """One cascade level's share of the cache."""

    source: str
    resolved: int
    #: Cached misses attributed to this level - it was the last to fail.
    unresolved: int


class SpendOut(BaseModel):
    provider: str
    calls: int
    cost_paise: int


class FunnelOut(BaseModel):
    checked_at: dt.datetime
    billing_month: dt.date
    cached_addresses: int
    resolved: int
    #: Share resolved without any paid level. Part 1 wants >= 0.90.
    free_share: float | None
    levels: list[LevelOut]
    spend: list[SpendOut]
    queue_open: int
    queue_resolved: int
    queue_rejected: int


#: Cascade levels that cost nothing. Everything else is a paid call, and the
#: free share is measured against this set rather than a hardcoded name so a
#: new free provider is counted correctly the day it is added.
FREE_SOURCES = frozenset({"nominatim", manual.MANUAL_SOURCE})


@router.get("/geocoding/funnel", response_model=FunnelOut)
def geocoding_funnel(session: Session = Depends(get_session)) -> FunnelOut:
    now = dt.datetime.now(dt.UTC)
    month = billing_month(now)

    rows = session.execute(
        select(
            GeocodeCache.source,
            func.count().filter(GeocodeCache.lat.isnot(None)),
            func.count().filter(GeocodeCache.lat.is_(None)),
        ).group_by(GeocodeCache.source)
    ).all()

    levels = [LevelOut(source=str(s), resolved=int(r), unresolved=int(u)) for s, r, u in rows]
    resolved = sum(level.resolved for level in levels)
    free = sum(level.resolved for level in levels if level.source in FREE_SOURCES)
    cached = resolved + sum(level.unresolved for level in levels)

    spend_rows = session.execute(
        select(
            ApiUsageEvent.provider,
            func.count(),
            func.coalesce(func.sum(ApiUsageEvent.cost_paise), 0),
        )
        .where(
            ApiUsageEvent.operation == "geocode",
            ApiUsageEvent.billing_month == month,
        )
        .group_by(ApiUsageEvent.provider)
    ).all()

    queue: dict[str, int] = {
        str(status): int(count)
        for status, count in session.execute(
            select(GeocodeManualQueue.status, func.count()).group_by(GeocodeManualQueue.status)
        ).all()
    }

    return FunnelOut(
        checked_at=now,
        billing_month=month,
        cached_addresses=cached,
        resolved=resolved,
        free_share=(free / resolved) if resolved else None,
        levels=sorted(levels, key=lambda level: -level.resolved),
        spend=[
            SpendOut(provider=str(p), calls=int(c), cost_paise=int(paise))
            for p, c, paise in spend_rows
        ],
        queue_open=int(queue.get(QueueStatus.OPEN.value, 0)),
        queue_resolved=int(queue.get(QueueStatus.RESOLVED.value, 0)),
        queue_rejected=int(queue.get(QueueStatus.REJECTED.value, 0)),
    )


# --- the manual queue ------------------------------------------------------


class QueueItemOut(BaseModel):
    id: int
    raw_input: str
    normalised_input: str
    pincode: str | None
    reason: str | None
    hits: int
    status: str
    lat: float | None
    lng: float | None
    created_at: dt.datetime


class QueueOut(BaseModel):
    open_count: int
    items: list[QueueItemOut]


@router.get("/geocoding/queue", response_model=QueueOut)
def geocoding_queue(session: Session = Depends(get_session), limit: int = 100) -> QueueOut:
    """Open jobs, busiest first."""
    jobs = manual.open_jobs(session, limit=min(limit, 500))
    total = session.execute(
        select(func.count())
        .select_from(GeocodeManualQueue)
        .where(GeocodeManualQueue.status == QueueStatus.OPEN.value)
    ).scalar_one()

    return QueueOut(
        open_count=int(total),
        items=[
            QueueItemOut(
                id=job.id,
                raw_input=job.raw_input,
                normalised_input=job.normalised_input,
                pincode=job.pincode,
                reason=job.reason,
                hits=job.hits,
                status=job.status,
                lat=job.lat,
                lng=job.lng,
                created_at=job.created_at,
            )
            for job in jobs
        ],
    )


class ResolveIn(BaseModel):
    #: India's bounding box, roughly. Not a nicety: a transposed lat/lng is the
    #: single most common way a hand-entered point goes wrong, and (76.2, 9.9)
    #: instead of (9.9, 76.2) is a coordinate in Kazakhstan that the district
    #: resolver would simply reject 5 km later with no explanation of why.
    lat: float = Field(ge=6.0, le=37.5)
    lng: float = Field(ge=68.0, le=97.5)
    note: str | None = None


class RejectIn(BaseModel):
    note: str | None = None


@router.post("/geocoding/queue/{queue_id}/resolve", response_model=QueueItemOut)
def resolve_job(
    queue_id: int,
    body: ResolveIn,
    session: Session = Depends(get_session),
    operator: str = Depends(require_operator),
) -> QueueItemOut:
    """Place the point, and write it back into the cache so it stays placed."""
    try:
        job = manual.resolve(
            session, queue_id, lat=body.lat, lng=body.lng, operator=operator, note=body.note
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return QueueItemOut.model_validate(job, from_attributes=True)


@router.post("/geocoding/queue/{queue_id}/reject", response_model=QueueItemOut)
def reject_job(
    queue_id: int,
    body: RejectIn,
    session: Session = Depends(get_session),
    operator: str = Depends(require_operator),
) -> QueueItemOut:
    """A human looked and could not place it. Nothing is written to the cache."""
    try:
        job = manual.reject(session, queue_id, operator=operator, note=body.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return QueueItemOut.model_validate(job, from_attributes=True)
