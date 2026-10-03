"""Only the allowlisted district/month aggregate can leave the private runner."""

from __future__ import annotations

import datetime as dt
from collections import Counter

import numpy as np

from app.domain.analytics.inputs import Bill, Station
from app.domain.demand.owner_mixed import age

PUBLIC_FIELDS = (
    "lgd_code",
    "month",
    "stations_known",
    "stations_with_data",
    "kwh_per_charger_p10",
    "kwh_per_charger_p50",
    "kwh_per_charger_p90",
    "district_total_p10",
    "district_total_p50",
    "district_total_p90",
    "note",
)


def publication_gate(
    stations: list[Station], observed: dict[str, Bill], month: dt.date, *, validation_passed: bool
) -> tuple[bool, str]:
    by_public = {station.public_id: station for station in stations}
    if any(
        key not in by_public
        or not by_public[key].consent
        or by_public[key].meter_type != "separate"
        or by_public[key].owner_station_id != bill.station_id
        or not bill.confirmed
        or not bill.full_calendar_month_verified
        or bill.month != month
        for key, bill in observed.items()
    ):
        return False, "Not enough data yet"
    if not validation_passed or len(observed) < 10:
        return False, "Not enough data yet"
    values = [bill.kwh for bill in observed.values()]
    total = sum(values)
    if total <= 0 or max(values) > total / 3:
        return False, "Not enough data yet"
    types = Counter(
        {
            "AC": sum(station.connectors_ac for station in stations),
            "DC": sum(station.connectors_dc for station in stations),
        }
    )
    uploaded = [station for station in stations if station.public_id in observed]
    covered = set()
    for station in uploaded:
        if station.connectors_ac:
            covered.add("AC")
        if station.connectors_dc:
            covered.add("DC")
    if sum(types[kind] for kind in covered) / sum(types.values()) < 0.7:
        return False, "Not enough data yet"
    other = [station for station in stations if station.public_id not in observed]
    flags = []
    if other:

        def shares(group: list[Station]) -> tuple[float, float]:
            return sum(station.connectors_dc for station in group) / sum(
                station.connectors for station in group
            ), sum(station.road_class == "national_highway" for station in group) / len(group)

        if any(
            abs(left - right) > 0.2
            for left, right in zip(shares(uploaded), shares(other), strict=True)
        ):
            flags.append("Volunteer connector/road mix differs from the listed inventory")
        uploaded_ages = [
            age(station, month) for station in uploaded if station.opened_month is not None
        ]
        other_ages = [age(station, month) for station in other if station.opened_month is not None]
        if (
            not other_ages
            or abs(float(np.median(uploaded_ages)) - float(np.median(other_ages)))
            / max(float(np.median(other_ages)), 1)
            > 0.5
        ):
            flags.append("Volunteer opening ages differ or age coverage is incomplete")
    imputed = sum(station.opened_month is None for station in stations) / len(stations)
    note = "; ".join(
        [
            *flags,
            f"Opening age imputed for {imputed:.0%} of listed stations. "
            "Inventory coverage is incomplete; these estimates are not "
            "the entire district's charging energy.",
        ]
    )
    return True, note


def aggregate(
    stations: list[Station],
    observed: dict[str, Bill],
    simulated_monthly: dict[str, np.ndarray],
    month: dt.date,
    *,
    validation_passed: bool,
) -> dict[str, object]:
    allowed, note = publication_gate(stations, observed, month, validation_passed=validation_passed)
    code = stations[0].lgd_code
    if any(station.lgd_code != code for station in stations):
        raise ValueError("A published group must be a single district")
    if not allowed:
        return dict(
            zip(
                PUBLIC_FIELDS,
                [
                    code,
                    month.isoformat()[:7],
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "Not enough data yet",
                ],
                strict=True,
            )
        )
    if set(observed) | set(simulated_monthly) != {station.public_id for station in stations} or set(
        observed
    ) & set(simulated_monthly):
        raise ValueError("Every listed station must contribute exactly once")
    lengths = {len(draws) for draws in simulated_monthly.values()}
    if lengths and (len(lengths) != 1 or min(lengths) < 1000):
        raise ValueError("Aligned simulations are required")
    count = next(iter(lengths), 1000)
    total = np.full(count, sum(bill.kwh for bill in observed.values()))
    for draws in simulated_monthly.values():
        if not np.isfinite(draws).all() or (draws < 0).any():
            raise ValueError("Invalid energy simulations")
        total += draws
    p10, p50, p90 = [float(value) for value in np.quantile(total, [0.1, 0.5, 0.9])]
    return dict(
        zip(
            PUBLIC_FIELDS,
            [
                code,
                month.isoformat()[:7],
                len(stations),
                len(observed),
                p10 / len(stations),
                p50 / len(stations),
                p90 / len(stations),
                p10,
                p50,
                p90,
                note,
            ],
            strict=True,
        )
    )
