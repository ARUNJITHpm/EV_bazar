"""Peer comparison and next-month energy band for a station owner.

Pure: no DB, no clock, no config. Months are integers (``year * 12 + month0``)
so age arithmetic never touches a calendar.

**Energy only (AGENTS.md rule 1).** Everything here is kWh per month. There is
no rupee figure, no payback and no revenue - those come from ``roi_engine``
if a later step ever needs them.

**Bands, never points (rule 6).** Every output is P10/P50/P90.

**``owner_peer_v0`` is an assumption, not a fit.** The peer curve (a plateau
per power tier, approaching it with a 7-month time constant) and the 0.46
lognormal spread are the prototype's placeholders. They are stamped on every
result so a stored forecast can be told apart from one made after the curve is
calibrated on real submissions.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

MODEL_VERSION = "owner_peer_v0"

PEER_SIGMA = 0.46  # lognormal spread across peer stations
RAMP_MONTHS = 7.0  # time constant of the utilisation ramp
HOURS_PER_MONTH_MAX = 744  # 31 days; the physical ceiling on kWh per kW
Z90 = 1.2816  # one-sided 90th percentile of the standard normal


@dataclass(frozen=True)
class ForecastBand:
    p10: float
    p50: float
    p90: float


@dataclass(frozen=True)
class OwnerForecast:
    model_version: str
    readings_used: int
    next_month: int
    age_months: int
    #: The owner's own next-month expectation.
    band: ForecastBand
    #: What comparable stations of the same age and power do, that month.
    peer_band: ForecastBand
    #: Geometric mean of owner / peer over the readings. 1.0 = on the peer line.
    relative_to_peers: float
    #: Where the owner's latest month sits among peers, 0-100.
    peer_percentile: float


def plateau_kwh(power_kw: float) -> float:
    """Mature monthly energy of one connector, by power tier."""
    if power_kw >= 50:
        return 2100.0
    if power_kw >= 25:
        return 1300.0
    return 260.0


def peer_median_kwh(connector_kw: Sequence[float], age_months: int) -> float:
    """Median monthly kWh peers of this connector mix deliver at this age."""
    ramp = 1.0 - math.exp(-(max(age_months, 0) + 0.5) / RAMP_MONTHS)
    return sum(plateau_kwh(kw) * ramp for kw in connector_kw)


def model_band(connector_kw: Sequence[float], age_months: int) -> ForecastBand:
    """The model's expected P10/P50/P90 for this connector mix at this age.

    Shown when there are too few real peers, and always labelled as a model
    estimate: it is the ``owner_peer_v0`` curve, not a measurement.
    """
    return _band(peer_median_kwh(connector_kw, age_months), PEER_SIGMA)


def max_monthly_kwh(connector_kw: Sequence[float]) -> float:
    return sum(kw * HOURS_PER_MONTH_MAX for kw in connector_kw)


def expand_connectors(connectors: Iterable[Mapping[str, Any]] | None) -> list[float]:
    """Flatten ``[{"power_kw": 60, "quantity": 2}, ...]`` to one kW per connector.

    The owner picks connectors by position in this list, so the order must be
    the stored order. A row with no power is dropped: it cannot be compared.
    """
    out: list[float] = []
    for row in connectors or []:
        kw = row.get("power_kw")
        if kw is None:
            continue
        qty = row.get("quantity") or 1
        out.extend([float(kw)] * max(int(qty), 1))
    return out


def valid_readings(
    readings: Mapping[int, float], install_month: int, connector_kw: Sequence[float]
) -> list[tuple[int, float]]:
    """Readings that are physically possible, oldest first.

    Drops months before the station went live, non-positive values, and
    anything above what the connectors could deliver running flat out - the
    usual signs of a shared meter or a typo.
    """
    ceiling = max_monthly_kwh(connector_kw)
    return sorted(
        (m, float(v)) for m, v in readings.items() if m >= install_month and 0 < v <= ceiling
    )


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _band(mid: float, sd: float) -> ForecastBand:
    return ForecastBand(p10=mid * math.exp(-Z90 * sd), p50=mid, p90=mid * math.exp(Z90 * sd))


def forecast(
    connector_kw: Sequence[float],
    install_month: int,
    readings: Mapping[int, float],
) -> OwnerForecast | None:
    """Next-month band from the owner's readings, or None if none are usable."""
    used = valid_readings(readings, install_month, connector_kw)
    if not used or not connector_kw:
        return None
    n = len(used)
    last_month, last_value = used[-1]
    next_month = last_month + 1
    age = next_month - install_month

    log_rel = [math.log(v / peer_median_kwh(connector_kw, m - install_month)) for m, v in used]
    rel = math.exp(sum(log_rel) / n)
    # More months of evidence -> lean further on the owner's own level.
    trust = 0.5 + 0.4 * min(n, 6) / 6
    mid = peer_median_kwh(connector_kw, age) * rel**trust
    sd = 0.08 + 0.25 / math.sqrt(n)

    peer_last = peer_median_kwh(connector_kw, last_month - install_month)
    z = math.log(last_value / peer_last) / PEER_SIGMA
    return OwnerForecast(
        model_version=MODEL_VERSION,
        readings_used=n,
        next_month=next_month,
        age_months=age,
        band=_band(mid, sd),
        peer_band=_band(peer_median_kwh(connector_kw, age), PEER_SIGMA),
        relative_to_peers=rel,
        peer_percentile=round(100.0 * _phi(z), 1),
    )


class Forecaster(Protocol):
    """The seam the real cluster model plugs into.

    A forecaster gets the station's connector powers, the month it went live
    and its confirmed monthly kWh, and returns the next month's P10/P50/P90 (or
    None with nothing usable). ``PeerBlendForecaster`` below is the placeholder
    until a fitted model replaces it; the stored ``model_version`` on every
    forecast says which one produced it.
    """

    model_version: str

    def __call__(
        self,
        connector_kw: Sequence[float],
        install_month: int,
        readings: Mapping[int, float],
    ) -> OwnerForecast | None: ...


class PeerBlendForecaster:
    """Peer growth curve by power tier and age, blended with the station's own bills.

    The blend leans further on the station's own history as months arrive
    (``trust``), and the range narrows with each month (``sd``) - both inside
    ``forecast``.
    """

    model_version = MODEL_VERSION

    def __call__(
        self,
        connector_kw: Sequence[float],
        install_month: int,
        readings: Mapping[int, float],
    ) -> OwnerForecast | None:
        return forecast(connector_kw, install_month, readings)


DEFAULT_FORECASTER: Forecaster = PeerBlendForecaster()
