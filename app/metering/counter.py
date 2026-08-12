"""The client-side counter - PART C.1, and the second half of constraint 7.

``config.py`` declares a ``monthly_cap``. Until this module existed, nothing
counted against it, so the cap was decoration. This is what makes it real.

The rule is **refuse, do not warn**. At cap the call does not happen. Warning
and proceeding is how a runaway loop costs Rs 40,000 while writing a tidy log
about it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import PaidProvider
from app.models.api_usage import BILLABLE_STATUSES, ApiUsageEvent


class QuotaExceededError(RuntimeError):
    """Raised instead of making a call that would exceed the configured cap.

    Callers in the geocoding cascade should catch this and fall through to
    the next level, so a capped Google key degrades to the manual queue
    rather than failing the request outright.
    """

    def __init__(self, provider: str, used: int, cap: int) -> None:
        super().__init__(
            f"metering: {provider} monthly cap reached ({used}/{cap}). "
            "Call refused. Raise the cap deliberately or wait for the window to roll."
        )
        self.provider = provider
        self.used = used
        self.cap = cap


@dataclass(frozen=True)
class QuotaState:
    provider: str
    used: int
    cap: int | None
    billing_month: dt.date

    @property
    def remaining(self) -> int | None:
        return None if self.cap is None else max(0, self.cap - self.used)

    @property
    def fraction_used(self) -> float | None:
        if self.cap is None or self.cap == 0:
            return None
        return self.used / self.cap

    @property
    def at_cap(self) -> bool:
        return self.cap is not None and self.used >= self.cap

    @property
    def should_alert(self) -> bool:
        """80% of cap. PLAN C.1 asks for a warning before the hard stop."""
        f = self.fraction_used
        return f is not None and f >= 0.8


def units_used(session: Session, provider: str, month: dt.date) -> int:
    """Billable input units consumed this window.

    Cache hits and self-inflicted refusals are excluded: neither cost money,
    and counting them would make the meter throttle us for being efficient.
    Errors and rate-limits ARE counted - providers bill for those.
    """
    stmt = select(func.coalesce(func.sum(ApiUsageEvent.units_in), 0)).where(
        ApiUsageEvent.provider == provider,
        ApiUsageEvent.billing_month == month,
        ApiUsageEvent.status.in_([s.value for s in BILLABLE_STATUSES]),
    )
    return int(session.execute(stmt).scalar_one())


def quota_state(
    session: Session, provider: str, config: PaidProvider, month: dt.date
) -> QuotaState:
    return QuotaState(
        provider=provider,
        used=units_used(session, provider, month),
        cap=config.monthly_cap,
        billing_month=month,
    )


def check_quota(
    session: Session,
    provider: str,
    config: PaidProvider,
    month: dt.date,
    *,
    units_requested: int = 1,
) -> QuotaState:
    """Raise ``QuotaExceededError`` if this call would cross the cap.

    Checked *before* the call, and inclusive of the units the call is about
    to consume - a cap of 1000 must not be crossed by the request that takes
    the total to 1001.
    """
    state = quota_state(session, provider, config, month)
    if state.cap is not None and state.used + units_requested > state.cap:
        raise QuotaExceededError(provider, state.used, state.cap)
    return state
