"""VAHAN parsing, district aggregation and growth - PART 4.1, the pure core.

No selenium and no database live here, so every rule below is a unit test away
from proof. The browser scrape (``scripts/scrape_vahan.py``) and the district
resolution + upsert (``app.domain.vahan.store``) are the thin shells around this.

The scrape is written to a **long** CSV - one row per (state, RTO, period, fuel,
vehicle class, count) - rather than a wide one, because VAHAN's category axis is
ragged (a rural RTO shows no buses) and a wide table would carry a shifting set
of columns. Long rows keep the schema stable and map one-to-one onto the tall
``vahan_ev_registrations`` table.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

#: The two VAHAN fuel labels that are all-electric. Everything else on the fuel
#: axis (PETROL, DIESEL, CNG, the hybrids) is not our subject and is dropped at
#: the scrape. Kept here so the one definition of "an EV" is in one place.
EV_FUELS: frozenset[str] = frozenset({"ELECTRIC(BOV)", "PURE EV"})

#: VAHAN's own row-total column. Summed separately from the per-class columns so
#: it is never double-counted with them.
TOTAL_CLASS = "TOTAL"

#: Read-time groupings of VAHAN vehicle-category codes, ADVISORY not structural:
#: the raw class is what is stored, and these say how the console rolls them up.
#: A charging site cares which of these a district's growth is in - a bus depot
#: and a scooter city want different chargers.
TWO_WHEELER = frozenset({"2WIC", "2WN", "2WT"})
THREE_WHEELER = frozenset({"3WN", "3WT", "3WIC"})
FOUR_WHEELER = frozenset({"4WIC", "LMV", "LPV", "LMC"})
BUS = frozenset({"OMNI BUS", "OMNIBUS", "HPV", "MPV"})
GOODS = frozenset({"LGV", "MGV", "HGV", "3WT"})  # 3WT is also a goods carrier


def normalise_class(raw: str) -> str:
    """VAHAN category code, uppercased with inner whitespace collapsed.

    "omni bus" and "OMNI  BUS" become the one key "OMNI BUS", so the same class
    from two RTOs aggregates instead of splitting.
    """
    return " ".join(raw.upper().split())


def _to_int(raw: str) -> int:
    """A VAHAN count cell -> int. "1,237" -> 1237; blanks and dashes -> 0."""
    s = raw.replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


@dataclass(frozen=True)
class RtoClassCount:
    """One (RTO, period, fuel, vehicle class) count, straight from the scrape."""

    state_code: str  # "KL"
    rto: str  # "ADOOR SRTO - KL26"
    period: str  # "2024" | "till_today"
    fuel: str  # "ELECTRIC(BOV)"
    vehicle_class: str  # "2WN" | "OMNI BUS" | "TOTAL"
    count: int


@dataclass(frozen=True)
class DistrictSlice:
    """RTO counts summed into their district - one row for the tall table."""

    lgd_district_code: int | None
    lgd_state_code: int | None
    period: str
    fuel: str
    vehicle_class: str
    count: int
    rto_count: int


#: The long-CSV column order the scraper writes and this module reads.
CSV_FIELDS = ("state_code", "rto", "period", "fuel", "vehicle_class", "count")


def to_csv(rows: Iterable[RtoClassCount]) -> str:
    """Serialise scraped counts to the long CSV the ingest reads back."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_FIELDS)
    for r in rows:
        w.writerow([r.state_code, r.rto, r.period, r.fuel, r.vehicle_class, r.count])
    return buf.getvalue()


def parse_vahan_csv(text: str, *, ev_only: bool = True) -> list[RtoClassCount]:
    """Read the long scrape CSV into typed counts.

    ``ev_only`` keeps only the EV fuel rows - the scrape should already be EV
    only, but a stray non-EV row must never inflate a count, so the guard is
    also enforced here where it can be tested.
    """
    out: list[RtoClassCount] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        fuel = (row.get("fuel") or "").strip()
        if ev_only and fuel not in EV_FUELS:
            continue
        out.append(
            RtoClassCount(
                state_code=(row.get("state_code") or "").strip(),
                rto=(row.get("rto") or "").strip(),
                period=(row.get("period") or "").strip(),
                fuel=fuel,
                vehicle_class=normalise_class(row.get("vehicle_class") or ""),
                count=_to_int(row.get("count") or "0"),
            )
        )
    return out


def aggregate_by_district(
    rows: Iterable[RtoClassCount],
    placement: Mapping[tuple[str, str], tuple[int | None, int | None]],
) -> list[DistrictSlice]:
    """Sum RTO counts into districts.

    ``placement`` maps ``(state_code, rto)`` -> ``(lgd_district_code,
    lgd_state_code)`` - the point-in-polygon result the store computes once per
    RTO. An RTO with no entry (or a ``(None, None)`` one) still aggregates, into
    the unplaced bucket for its state, so nothing is dropped for want of a
    polygon.

    ``rto_count`` counts the DISTINCT RTOs that fed each slice, which is why the
    RTO identity is tracked through the grouping rather than just its count.
    """
    sums: dict[tuple[int | None, int | None, str, str, str], int] = defaultdict(int)
    rtos: dict[tuple[int | None, int | None, str, str, str], set[str]] = defaultdict(set)

    for r in rows:
        district, state = placement.get((r.state_code, r.rto), (None, None))
        key = (district, state, r.period, r.fuel, r.vehicle_class)
        sums[key] += r.count
        rtos[key].add(r.rto)

    out = [
        DistrictSlice(
            lgd_district_code=district,
            lgd_state_code=state,
            period=period,
            fuel=fuel,
            vehicle_class=vclass,
            count=count,
            rto_count=len(rtos[(district, state, period, fuel, vclass)]),
        )
        for (district, state, period, fuel, vclass), count in sums.items()
    ]
    # Deterministic order: a stable output makes tests and diffs legible.
    out.sort(
        key=lambda s: (
            s.lgd_state_code or 0,
            s.lgd_district_code or 0,
            s.period,
            s.fuel,
            s.vehicle_class,
        )
    )
    return out


def annual_growth(by_year: Mapping[str, int]) -> float | None:
    """Year-on-year growth of the two most recent calendar years, as a ratio.

    ``{"2023": 100, "2024": 130}`` -> ``0.30``. Returns ``None`` when there are
    fewer than two years, or the earlier year is zero (growth off a zero base is
    a story about a first arrival, not a rate - the caller should say "new", not
    "+infinity"). Non-numeric period keys such as "till_today" are ignored, so a
    snapshot may safely mix cumulative and per-year rows.
    """
    years = sorted(y for y in by_year if y.isdigit())
    if len(years) < 2:
        return None
    prev, latest = by_year[years[-2]], by_year[years[-1]]
    if prev <= 0:
        return None
    return (latest - prev) / prev
