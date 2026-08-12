"""PART C.1 - spend metering.

Every paid client in this codebase goes through ``meter()``. There is no
second path, and adding one is a revert (AGENTS.md constraint 10).

    counter.py   month-to-date sum; refuses at cap
    pricing.py   cost from the effective-dated price card
    meter.py     the context manager that writes the event
"""

from __future__ import annotations

from app.metering.counter import (
    QuotaExceededError,
    QuotaState,
    check_quota,
    quota_state,
    units_used,
)
from app.metering.meter import Measurement, meter
from app.metering.pricing import PriceCard, billing_month, cost_paise

__all__ = [
    "Measurement",
    "PriceCard",
    "QuotaExceededError",
    "QuotaState",
    "billing_month",
    "check_quota",
    "cost_paise",
    "meter",
    "quota_state",
    "units_used",
]
