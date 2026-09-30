"""What an owner's electricity bill can tell us, and whether it is believable.

Every field is optional except the billing period and the units consumed.
Nothing here reaches a database, a clock or a config value: ``today`` is passed
in, so the checks are the same in a test as in production.

**Extraction is an interface.** ``BillExtractor`` reads an uploaded image or PDF
and *proposes* values. The first implementation, ``ManualExtractor``, proposes
nothing: the owner reads the bill beside the image and types the fields. Either
way the values are stored only after the owner confirms them (the endpoint
requires ``confirmed: true``) - an extractor's output is never saved by itself.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Protocol

HOURS_PER_MONTH_MAX = 744  # 31 days x 24 h
HISTORY_MAX_MONTHS = 12
_EV_TARIFF = re.compile(r"\b(ev|electric vehicle|charging)\b", re.IGNORECASE)


@dataclass(frozen=True)
class BillFields:
    period: dt.date  # first day of the billed month
    kwh: float
    history: tuple[tuple[dt.date, float], ...] = ()
    tariff_category: str | None = None
    contract_demand: float | None = None
    recorded_demand: float | None = None
    demand_unit: str | None = None  # "kVA" | "kW" - never converted between
    power_factor: float | None = None
    pf_effect: str | None = None  # "penalty" | "incentive"
    pf_amount_paise: int | None = None
    tod_peak_kwh: float | None = None
    tod_normal_kwh: float | None = None
    tod_offpeak_kwh: float | None = None
    board: str | None = None
    consumer_number: str | None = None


@dataclass(frozen=True)
class ExtractedBill:
    """An extractor's proposal. Every field may be missing; none is trusted."""

    fields: dict[str, object] = field(default_factory=dict)
    extractor: str = "manual"


class BillExtractor(Protocol):
    def extract(self, content: bytes, content_type: str) -> ExtractedBill: ...


class ManualExtractor:
    """First version: propose nothing. The owner types what the bill says."""

    def extract(self, content: bytes, content_type: str) -> ExtractedBill:
        return ExtractedBill()


def indian_grouping(n: float) -> str:
    """12,34,567 - the grouping an owner reads on their own bill."""
    whole = f"{round(n):d}"
    if len(whole) <= 3:
        return whole
    head, tail = whole[:-3], whole[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join([*groups, tail])


def kwh_limit(total_kw: float) -> float:
    return total_kw * HOURS_PER_MONTH_MAX


def mask_consumer_number(raw: str | None) -> str | None:
    """Last four characters only. The full number is never stored."""
    if not raw:
        return None
    cleaned = re.sub(r"\s+", "", raw)
    return cleaned[-4:] if len(cleaned) >= 4 else None


def implies_separate_meter(tariff_category: str | None) -> bool:
    """An EV-charging tariff category is billed on its own meter."""
    return bool(tariff_category and _EV_TARIFF.search(tariff_category))


def resolve_meter(tariff_category: str | None, answer: str | None) -> str:
    """separate | shared | unsure. The tariff settles it; otherwise the answer."""
    if implies_separate_meter(tariff_category):
        return "separate"
    return answer if answer in ("separate", "shared", "unsure") else "unsure"


def validate(
    bill: BillFields,
    *,
    total_kw: float,
    went_live: dt.date | None,
    today: dt.date,
) -> list[str]:
    """Every reason this bill cannot be saved, in plain words. Empty = fine."""
    errors: list[str] = []
    limit = kwh_limit(total_kw)
    if bill.kwh <= 0 or bill.kwh > limit:
        errors.append(
            f"Units must be above 0 and no more than {indian_grouping(limit)} kWh: your "
            f"connectors total {total_kw:g} kW x {HOURS_PER_MONTH_MAX} hours in a month."
        )
    if bill.period.day != 1:
        errors.append("The billing period must be a month.")
    if bill.period > today.replace(day=1):
        errors.append("The billing period cannot be in the future.")
    if went_live and bill.period < went_live.replace(day=1):
        errors.append("That month is before the station went live.")
    if len(bill.history) > HISTORY_MAX_MONTHS:
        errors.append(f"At most {HISTORY_MAX_MONTHS} months of past consumption.")
    for period, kwh in bill.history:
        if kwh <= 0 or kwh > limit:
            errors.append(
                f"Past consumption for {period:%b %Y} must be above 0 and no more than "
                f"{indian_grouping(limit)} kWh."
            )
    for name, value in (
        ("Contract demand", bill.contract_demand),
        ("Recorded maximum demand", bill.recorded_demand),
    ):
        if value is not None and value <= 0:
            errors.append(f"{name} must be above 0.")
    if (bill.contract_demand is not None or bill.recorded_demand is not None) and (
        bill.demand_unit not in ("kVA", "kW")
    ):
        errors.append("Say whether demand is in kVA or kW.")
    if bill.power_factor is not None and not 0 < bill.power_factor <= 1:
        errors.append("Power factor must be between 0 and 1.")
    if bill.pf_amount_paise is not None and (
        bill.pf_amount_paise < 0 or bill.pf_effect not in ("penalty", "incentive")
    ):
        errors.append("Say whether the power factor amount is a penalty or an incentive.")
    tod = [bill.tod_peak_kwh, bill.tod_normal_kwh, bill.tod_offpeak_kwh]
    if any(v is not None and v < 0 for v in tod):
        errors.append("Time-of-day units cannot be negative.")
    elif sum(v for v in tod if v is not None) > bill.kwh * 1.02:
        errors.append("Peak, normal and off-peak units add up to more than the units consumed.")
    return errors
