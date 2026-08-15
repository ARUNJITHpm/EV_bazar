"""L6 - the manual queue's behaviour. PART 1.3.

Three operations, and the third is the one that pays for the other two.

``enqueue``
    A cascade MISS becomes a job. Idempotent on the normalised key, so the same
    address asked fifty times is one job with ``hits = 50`` - and a queue sorted
    by hits spends the operator's twenty seconds where they buy the most.

``resolve``
    The human's click. It writes the point into ``geocode_cache`` with
    ``source='manual'`` **and** closes the job, in one transaction. If it only
    closed the job, the next lookup of that address would miss again and
    re-queue it, and the queue would refill with work already done.

``reject``
    A human looked and could not place it either. Counted apart from "nobody
    has looked yet", because the two need completely different responses: one
    is a backlog, the other is a data-quality finding about our input.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.resolution.geocode import GeocodeOutcome, GeocodeStatus
from app.models.geocode import GeocodeCache
from app.models.manual_queue import GeocodeManualQueue, QueueStatus

#: What ``source`` a manually placed point carries in the cache. Distinct from
#: every geocoder name so a spend or accuracy report can separate "a human did
#: this" from "a machine did this" without a join.
MANUAL_SOURCE = "manual"


def enqueue(session: Session, outcome: GeocodeOutcome) -> GeocodeManualQueue | None:
    """Queue a cascade MISS for a human. Returns the row, or None if not a miss.

    A resolved job that misses again is **reopened** rather than duplicated: it
    means the human's coordinates were dropped from the cache, or the address
    changed, and either way it is the same job.
    """
    if outcome.status is not GeocodeStatus.MISS:
        return None

    key = outcome.normalised.cache_key
    row = session.execute(
        select(GeocodeManualQueue).where(GeocodeManualQueue.normalised_input == key)
    ).scalar_one_or_none()

    reason = "; ".join(outcome.reasons) or None

    if row is None:
        row = GeocodeManualQueue(
            normalised_input=key,
            raw_input=outcome.normalised.raw,
            pincode=outcome.normalised.pincode,
            reason=reason,
            hits=1,
            status=QueueStatus.OPEN.value,
        )
        session.add(row)
    else:
        row.hits += 1
        row.reason = reason
        if row.status == QueueStatus.RESOLVED.value:
            row.status = QueueStatus.OPEN.value
            row.resolved_by = None
            row.resolved_at = None

    session.flush()
    return row


def resolve(
    session: Session,
    queue_id: int,
    *,
    lat: float,
    lng: float,
    operator: str,
    note: str | None = None,
    now: dt.datetime | None = None,
) -> GeocodeManualQueue:
    """Record the human's point, and make it permanent in the cache."""
    row = session.get(GeocodeManualQueue, queue_id)
    if row is None:
        raise LookupError(f"manual queue: no job {queue_id}")

    moment = now or dt.datetime.now(dt.UTC)
    row.lat = lat
    row.lng = lng
    row.note = note
    row.status = QueueStatus.RESOLVED.value
    row.resolved_by = operator
    row.resolved_at = moment

    # The write-back. Without this the queue refills with work already done.
    cache = session.get(GeocodeCache, row.normalised_input)
    if cache is None:
        cache = GeocodeCache(normalised_input=row.normalised_input)
        session.add(cache)
    cache.lat = lat
    cache.lng = lng
    cache.source = MANUAL_SOURCE
    # A human who looked at a map and clicked a building is the best evidence
    # this cascade can produce. Nothing above L6 earns `high` this cheaply.
    cache.confidence = "high"
    cache.display_name = note or row.raw_input
    cache.raw_response = {
        "manual": True,
        "operator": operator,
        "resolved_at": moment.isoformat(),
        "raw_input": row.raw_input,
        "note": note,
    }
    cache.fetched_at = moment

    session.flush()
    return row


def reject(
    session: Session,
    queue_id: int,
    *,
    operator: str,
    note: str | None = None,
    now: dt.datetime | None = None,
) -> GeocodeManualQueue:
    """A human could not place it either.

    Nothing is written to the cache: the address stays a miss, because it *is*
    one. Recording a rejection as a cached point would be inventing a location,
    which is the one thing this whole package exists not to do.
    """
    row = session.get(GeocodeManualQueue, queue_id)
    if row is None:
        raise LookupError(f"manual queue: no job {queue_id}")

    row.status = QueueStatus.REJECTED.value
    row.note = note
    row.resolved_by = operator
    row.resolved_at = now or dt.datetime.now(dt.UTC)
    session.flush()
    return row


def open_jobs(session: Session, *, limit: int = 100) -> list[GeocodeManualQueue]:
    """Busiest first - most-asked addresses are worth the operator's time."""
    stmt = (
        select(GeocodeManualQueue)
        .where(GeocodeManualQueue.status == QueueStatus.OPEN.value)
        .order_by(GeocodeManualQueue.hits.desc(), GeocodeManualQueue.id)
        .limit(limit)
    )
    return list(session.execute(stmt).scalars())
