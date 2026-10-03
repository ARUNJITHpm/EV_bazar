"""VAHAN month-wise registrations - the pure core.

The dashboard's X-axis can be "Month Wise": for one calendar year it renders a
column per month (JAN ... DEC) plus a row TOTAL, against whichever Y-axis was
chosen. Two Y-axes are useful to us:

  * ``vehicle_category`` - read per RTO and summed into districts. In this
    view the dashboard spells categories out ("LIGHT GOODS VEHICLE"), unlike
    the yearly table's codes ("LGV"); they are stored as spelled, not mapped;
  * ``maker`` - the manufacturer ("ATHER ENERGY LTD", "TATA MOTORS PASSENGER
    VEHICLES LTD" ...), read once per state. VAHAN stops at the maker: there is
    no model or variant axis, and no individual vehicle records.

The fuel is NOT on the table in this mode - it is a side-panel filter. The
scraper ticks the EV fuels (``EV_FUELS``) before every read, so each count is
"all-electric registrations", recorded under ``EV_FUEL_SCOPE``.

These are registrations IN each month, read directly - never derived by
subtracting two cumulative snapshots. Late RTO uploads land in the month they
belong to, and a missed run loses nothing that a later run cannot re-read. The
latest months keep being revised, so a reader should prefer the newest
snapshot and treat the snapshot's own month as partial (``is_partial``).

Kept apart from ``parse.py`` so the yearly table, and every reader of it, is
untouched by this mode. No selenium and no database here.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from app.domain.vahan.parse import EV_FUELS, _to_int, normalise_class

#: The breakdowns the scraper can read month-wise, keyed by our name, with the
#: dashboard's Y-axis label each one selects.
BREAKDOWNS: dict[str, str] = {"vehicle_category": "Vehicle Category", "maker": "Maker"}

#: Recorded on every monthly row: the side-panel fuel filter that produced it.
#: Spelled out from ``EV_FUELS`` so a change to that set changes the label too.
EV_FUEL_SCOPE = "+".join(sorted(EV_FUELS))

#: RTO placeholder for a state-wide read (the dashboard's "All ... Office").
ALL_RTOS = "ALL"

#: Label of a resume marker row: the (RTO, year) was read and had no EV rows.
#: Written so a relaunch does not re-fight it; dropped on ingest.
NO_ROWS = "__NONE__"

_MONTHS = {
    name: number
    for number, names in enumerate(
        (
            ("JAN", "JANUARY"),
            ("FEB", "FEBRUARY"),
            ("MAR", "MARCH"),
            ("APR", "APRIL"),
            ("MAY",),
            ("JUN", "JUNE"),
            ("JUL", "JULY"),
            ("AUG", "AUGUST"),
            ("SEP", "SEPT", "SEPTEMBER"),
            ("OCT", "OCTOBER"),
            ("NOV", "NOVEMBER"),
            ("DEC", "DECEMBER"),
        ),
        start=1,
    )
    for name in names
}


def month_number(header: str) -> int | None:
    """A month column header -> 1..12, or None for anything else ("TOTAL")."""
    return _MONTHS.get(header.strip().upper().rstrip("."))


@dataclass(frozen=True)
class MonthlyCount:
    """One (RTO or whole state, month, breakdown label) count from the scrape."""

    state_code: str  # "KL"
    rto: str  # "ADOOR SRTO - KL26" | ALL_RTOS
    month: dt.date  # first day of the month
    breakdown: str  # a BREAKDOWNS key
    label: str  # "LIGHT GOODS VEHICLE" | "ATHER ENERGY LTD"
    count: int


def parse_month_table(
    header: Sequence[str],
    rows: Iterable[Sequence[str]],
    *,
    state_code: str,
    rto: str,
    year: int,
    breakdown: str,
) -> list[MonthlyCount]:
    """A rendered month-wise table -> counts.

    ``header`` is the column-label row: [S No, <Y-axis name>, JAN, ..., DEC,
    TOTAL] - months the dashboard has no data for yet may be absent, so columns
    are matched by name, never by position. Body rows are [S No, label, counts
    ...]. Each body row's TOTAL is ignored: it is the sum of its own months, and
    storing it would double-count. A table with no month columns is refused
    rather than read as zero, because that means the X-axis was not applied.

    No TOTAL rows are produced: a month's total is the sum of its labels, and
    storing both would invite double counting.
    """
    if breakdown not in BREAKDOWNS:
        raise ValueError(f"unknown breakdown {breakdown!r}")
    rows = [list(r) for r in rows]
    # A grouped header puts the month names on their own row, without the
    # leading S No / label cells; right-align it to the body's width.
    width = max((len(r) for r in rows), default=len(header))
    header = [""] * max(0, width - len(header)) + list(header)
    months = {i: m for i, h in enumerate(header) if (m := month_number(h)) is not None}
    if not months:
        raise ValueError(f"no month columns in table header {list(header)!r}")
    out: list[MonthlyCount] = []
    for cells in rows:
        if len(cells) < 2:
            continue
        label = " ".join(cells[1].upper().split())
        if not label or label in {"TOTAL", "GRAND TOTAL"}:
            continue
        if breakdown == "vehicle_category":
            label = normalise_class(label)
        for index, month in months.items():
            if index >= len(cells):
                continue
            raw = cells[index].replace(",", "").strip()
            if not raw.lstrip("-").isdigit():
                continue
            out.append(
                MonthlyCount(state_code, rto, dt.date(year, month, 1), breakdown, label, int(raw))
            )
    return out


#: The long-CSV column order the monthly scrape writes and ingest reads. A
#: different header from the yearly CSV, so the two can never be confused.
CSV_FIELDS = ("state_code", "rto", "month", "breakdown", "label", "fuel_scope", "count")


def is_monthly_csv(text: str) -> bool:
    """True when the CSV's header is the monthly one."""
    first = text.lstrip("﻿").split("\n", 1)[0].strip()
    return tuple(first.split(",")) == CSV_FIELDS


def csv_row(c: MonthlyCount) -> tuple[str, str, str, str, str, str, int]:
    return (c.state_code, c.rto, c.month.isoformat(), c.breakdown, c.label, EV_FUEL_SCOPE, c.count)


def parse_monthly_csv(text: str) -> list[MonthlyCount]:
    """Read the monthly scrape CSV back. Rows of another fuel scope are refused."""
    out: list[MonthlyCount] = []
    for line, row in enumerate(csv.DictReader(io.StringIO(text.lstrip("﻿"))), start=2):
        scope = (row.get("fuel_scope") or "").strip()
        if scope != EV_FUEL_SCOPE:
            raise ValueError(f"line {line}: fuel scope {scope!r} is not {EV_FUEL_SCOPE!r}")
        breakdown = (row.get("breakdown") or "").strip()
        if breakdown not in BREAKDOWNS:
            raise ValueError(f"line {line}: unknown breakdown {breakdown!r}")
        month = dt.date.fromisoformat((row.get("month") or "").strip())
        if month.day != 1:
            raise ValueError(f"line {line}: month must be the first day, got {month}")
        if (row.get("label") or "").strip() == NO_ROWS:
            continue
        out.append(
            MonthlyCount(
                state_code=(row.get("state_code") or "").strip(),
                rto=(row.get("rto") or "").strip(),
                month=month,
                breakdown=breakdown,
                label=" ".join((row.get("label") or "").upper().split()),
                count=_to_int(row.get("count") or "0"),
            )
        )
    return out


@dataclass(frozen=True)
class MonthlySlice:
    """Counts summed to one place - a district, or a whole state."""

    geography: str  # "district" | "state"
    lgd_district_code: int | None
    lgd_state_code: int | None
    month: dt.date
    breakdown: str
    label: str
    count: int
    rto_count: int


def aggregate_monthly(
    counts: Iterable[MonthlyCount],
    placement: Mapping[tuple[str, str], tuple[int | None, int | None]],
    state_codes: Mapping[str, int],
) -> list[MonthlySlice]:
    """Sum per-RTO counts into districts; state-wide reads stay state rows.

    A per-RTO count goes to the district its office point fell in (``placement``,
    as for the yearly table); an RTO with no placement lands in its state's
    unplaced bucket, district NULL. A state-wide read (``rto == ALL_RTOS``) is
    kept as a ``state`` row with district NULL, never mixed into that bucket.
    """
    sums: dict[tuple[str, int | None, int | None, dt.date, str, str], int] = defaultdict(int)
    rtos: dict[tuple[str, int | None, int | None, dt.date, str, str], set[str]] = defaultdict(set)
    for c in counts:
        if c.rto == ALL_RTOS:
            geography, district, state = "state", None, state_codes.get(c.state_code)
        else:
            geography = "district"
            district, state = placement.get((c.state_code, c.rto), (None, None))
            state = state if state is not None else state_codes.get(c.state_code)
        key = (geography, district, state, c.month, c.breakdown, c.label)
        sums[key] += c.count
        rtos[key].add(c.rto)
    out = [
        MonthlySlice(geography, district, state, month, breakdown, label, count, len(rtos[key]))
        for key, count in sums.items()
        for geography, district, state, month, breakdown, label in [key]
    ]
    out.sort(
        key=lambda s: (
            s.geography,
            s.lgd_state_code or 0,
            s.lgd_district_code or 0,
            s.month,
            s.breakdown,
            s.label,
        )
    )
    return out


def is_partial(month: dt.date, snapshot_date: dt.date) -> bool:
    """A month still being filled in when the snapshot was taken."""
    return (month.year, month.month) >= (snapshot_date.year, snapshot_date.month)
