"""The wrapper every paid client goes through - PART C.1.

AGENTS.md constraint 10: every metered external call writes an
``api_usage_events`` row **before its response is used**, including retries,
errors, and cache hits.

Usage::

    with meter(session, provider="google_maps", operation="geocode",
               config=settings.google_maps, caused_by="cascade_l5") as m:
        response = httpx.get(...)
        m.record(units_in=1)
    # row is written on exit, whether or not the block raised

The context manager shape is deliberate: there is no path out of the block
that skips the write. A decorator or a "remember to log" convention both
leave a way to forget, and forgetting is exactly the failure this table
exists to prevent.
"""

from __future__ import annotations

import datetime as dt
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.config import PaidProvider
from app.metering.counter import QuotaExceededError, check_quota
from app.metering.pricing import PriceCard, billing_month, cost_paise
from app.models.api_usage import ApiUsageEvent, UsageStatus


@dataclass
class Measurement:
    """Mutable handle the caller fills in during the call."""

    units_in: int = 0
    units_out: int = 0
    status: UsageStatus = UsageStatus.OK
    detail: dict[str, Any] = field(default_factory=dict)

    def record(
        self,
        *,
        units_in: int = 1,
        units_out: int = 0,
        status: UsageStatus = UsageStatus.OK,
        **detail: Any,
    ) -> None:
        self.units_in = units_in
        self.units_out = units_out
        self.status = status
        if detail:
            self.detail.update(detail)


@contextmanager
def meter(
    session: Session,
    *,
    provider: str,
    operation: str,
    config: PaidProvider,
    card: PriceCard,
    caused_by: str | None = None,
    site_id: uuid.UUID | None = None,
    model: str | None = None,
    units_expected: int = 1,
    now: dt.datetime | None = None,
) -> Iterator[Measurement]:
    """Meter one external call.

    Raises ``QuotaExceededError`` *before* yielding if the call would cross the
    configured cap - and writes a ``capped`` row so the refusal is itself
    visible in the console. A cap that silently swallows demand looks
    identical to a provider outage otherwise.
    """
    moment = now or dt.datetime.now(dt.UTC)
    month = billing_month(moment)
    measurement = Measurement()

    try:
        check_quota(session, provider, config, month, units_requested=units_expected)
    except QuotaExceededError:
        _write(
            session,
            provider=provider,
            operation=operation,
            model=model,
            measurement=Measurement(units_in=0, status=UsageStatus.CAPPED),
            card=card,
            month=month,
            caused_by=caused_by,
            site_id=site_id,
            latency_ms=0,
            error="refused by client-side cap",
            used_before=0,
        )
        raise

    used_before = 0
    if card.free_units_per_month:
        from app.metering.counter import units_used

        used_before = units_used(session, provider, month)

    started = time.perf_counter()
    error: str | None = None
    try:
        yield measurement
    except Exception as exc:
        measurement.status = UsageStatus.ERROR
        error = f"{exc.__class__.__name__}: {exc}"
        raise
    finally:
        _write(
            session,
            provider=provider,
            operation=operation,
            model=model,
            measurement=measurement,
            card=card,
            month=month,
            caused_by=caused_by,
            site_id=site_id,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error=error,
            used_before=used_before,
        )


def _write(
    session: Session,
    *,
    provider: str,
    operation: str,
    model: str | None,
    measurement: Measurement,
    card: PriceCard,
    month: dt.date,
    caused_by: str | None,
    site_id: uuid.UUID | None,
    latency_ms: int,
    error: str | None,
    used_before: int,
) -> None:
    # A cache hit costs nothing, but we still price it - the avoided cost is
    # what evidences Part 1's "median cascade cost per address = Rs 0".
    priced = cost_paise(
        card,
        measurement.units_in,
        measurement.units_out,
        units_already_used_this_month=used_before,
    )
    billed = 0 if measurement.status in (UsageStatus.CACHE_HIT, UsageStatus.CAPPED) else priced

    detail = dict(measurement.detail)
    if measurement.status is UsageStatus.CACHE_HIT:
        detail["cost_avoided_paise"] = priced

    session.add(
        ApiUsageEvent(
            provider=provider,
            operation=operation,
            model=model,
            units_in=measurement.units_in,
            units_out=measurement.units_out or None,
            cost_paise=billed,
            price_card_version=card.version,
            billing_month=month,
            status=measurement.status.value,
            caused_by=caused_by,
            site_id=site_id,
            latency_ms=latency_ms,
            detail=detail or None,
            error=error,
        )
    )
    session.flush()
