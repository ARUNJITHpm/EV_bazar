"""Comparison with similar stations - shown only when there are enough of them.

Pure. A peer is another owner's station of the same charger type and state, on
its own meter, that agreed to anonymous averaging; the caller filters on those
and hands in one ``PeerRow`` per (station, billed month). Energy is compared per
kW of connector so a 60 kW and a 120 kW station are not scored against each
other's size.

**The threshold is the privacy rule.** Owners agreed to be published only as
averages of ``MIN_PEERS`` or more stations, so below that this module returns
nothing at all - not a thin average, not a percentile - and the page falls back
to the labelled model curve (``forecast.peer_median_kwh``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

MIN_PEERS = 10
#: A peer counts as "similar age" when its bill is within this many months of
#: the age being compared.
AGE_WINDOW = 3


@dataclass(frozen=True)
class PeerRow:
    station_id: int
    age_months: int
    kwh_per_kw: float


@dataclass(frozen=True)
class PeerStat:
    n: int
    p10: float
    p50: float
    p90: float


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def _one_per_station(rows: Sequence[PeerRow], age: int, window: int) -> list[float]:
    """Each peer's bill nearest to ``age`` (ties: the earlier), within the window."""
    nearest: dict[int, tuple[int, float]] = {}
    for row in rows:
        gap = abs(row.age_months - age)
        if gap > window:
            continue
        held = nearest.get(row.station_id)
        if held is None or gap < held[0]:
            nearest[row.station_id] = (gap, row.kwh_per_kw)
    return sorted(v for _, v in nearest.values())


def cohort_size(rows: Sequence[PeerRow], age: int, window: int = AGE_WINDOW) -> int:
    return len(_one_per_station(rows, age, window))


def cohort_stat(rows: Sequence[PeerRow], age: int, window: int = AGE_WINDOW) -> PeerStat | None:
    """P10/P50/P90 of the peers at this age, or None below ``MIN_PEERS``."""
    values = _one_per_station(rows, age, window)
    if len(values) < MIN_PEERS:
        return None
    return PeerStat(
        n=len(values),
        p10=_quantile(values, 0.10),
        p50=_quantile(values, 0.50),
        p90=_quantile(values, 0.90),
    )


def percentile_rank(
    value_per_kw: float, rows: Sequence[PeerRow], age: int, window: int = AGE_WINDOW
) -> float | None:
    """Share of peers (0-100) this station is ahead of, or None below ``MIN_PEERS``."""
    values = _one_per_station(rows, age, window)
    if len(values) < MIN_PEERS:
        return None
    return round(100.0 * sum(1 for v in values if v < value_per_kw) / len(values), 1)
