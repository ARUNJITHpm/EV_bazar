"""VAHAN vehicle counts - PART 4.1, the console read side.

Read-only views over ``vahan_ev_registrations``: how many EVs each state and
district holds, how fast that is growing, and the split by vehicle class. Growth
is the headline, not the absolute - PLAN 4.1 weights the 12-month rate above the
count - so every row that can carries a year-on-year figure, computed by the same
pure ``annual_growth`` the tests pin.

Everything reads the LATEST snapshot only (the current picture); older snapshots
stay in the table as the time series the growth rate is drawn from.

Guarded: mounted on the ``guarded`` router in ``api/internal/__init__.py``.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.vahan.parse import (
    BUS,
    FOUR_WHEELER,
    GOODS,
    THREE_WHEELER,
    TWO_WHEELER,
    annual_growth,
)
from app.models.reference import District, State
from app.models.vahan import VahanEvRegistration

router = APIRouter()

TOTAL_CLASS = "TOTAL"

#: Read-time roll-up of VAHAN class codes into the buckets a site cares about.
#: Order matters only for display; membership is from parse.py's advisory sets.
_CLASS_GROUPS: tuple[tuple[str, frozenset[str]], ...] = (
    ("Two-wheeler", TWO_WHEELER),
    ("Three-wheeler", THREE_WHEELER),
    ("Four-wheeler", FOUR_WHEELER),
    ("Bus", BUS),
    ("Goods", GOODS),
)


def _group_for(vclass: str) -> str:
    for label, members in _CLASS_GROUPS:
        if vclass in members:
            return label
    return "Other"


class StateVahanRow(BaseModel):
    lgd_state_code: int
    state: str
    districts: int
    ev_total: int
    growth_pct: float | None


class DistrictVahanRow(BaseModel):
    lgd_district_code: int | None
    district: str
    state: str
    ev_total: int
    growth_pct: float | None


class ClassRow(BaseModel):
    group: str
    ev_total: int


class VahanOut(BaseModel):
    checked_at: dt.datetime
    #: The capture this whole page reflects. None = nothing ingested yet.
    snapshot_date: dt.date | None
    #: Every window in the latest snapshot, e.g. ["2023","2024","2025"].
    periods: list[str]
    #: The window the totals below are for - the newest calendar year present.
    display_period: str | None
    total_rows: int
    by_state: list[StateVahanRow]
    top_districts: list[DistrictVahanRow]
    by_class: list[ClassRow]


def _year_periods(periods: list[str]) -> list[str]:
    return sorted(p for p in periods if p.isdigit())


@router.get("/vahan", response_model=VahanOut)
def vahan(session: Session = Depends(get_session), limit: int = 12) -> VahanOut:
    checked = dt.datetime.now(dt.UTC)
    total_rows = session.execute(
        select(func.count()).select_from(VahanEvRegistration)
    ).scalar_one()

    latest = session.execute(
        select(func.max(VahanEvRegistration.snapshot_date))
    ).scalar_one_or_none()
    if latest is None:
        return VahanOut(
            checked_at=checked,
            snapshot_date=None,
            periods=[],
            display_period=None,
            total_rows=0,
            by_state=[],
            top_districts=[],
            by_class=[],
        )

    periods = sorted(
        str(p)
        for p in session.execute(
            select(VahanEvRegistration.period)
            .where(VahanEvRegistration.snapshot_date == latest)
            .distinct()
        )
        .scalars()
        .all()
    )
    years = _year_periods(periods)
    display_period = years[-1] if years else (periods[-1] if periods else None)

    # --- district & state EV totals per period, from the TOTAL rows -----------
    # Summed across fuels (ELECTRIC(BOV) + PURE EV), so one number per place/year.
    total_rows_q = session.execute(
        select(
            VahanEvRegistration.lgd_district_code,
            VahanEvRegistration.lgd_state_code,
            VahanEvRegistration.period,
            func.sum(VahanEvRegistration.count),
            District.name,
            State.name,
        )
        .outerjoin(District, District.lgd_district_code == VahanEvRegistration.lgd_district_code)
        .join(State, State.lgd_state_code == VahanEvRegistration.lgd_state_code)
        .where(
            VahanEvRegistration.snapshot_date == latest,
            VahanEvRegistration.vehicle_class == TOTAL_CLASS,
        )
        .group_by(
            VahanEvRegistration.lgd_district_code,
            VahanEvRegistration.lgd_state_code,
            VahanEvRegistration.period,
            District.name,
            State.name,
        )
    ).all()

    # district_code -> {period: ev_total}; plus names
    d_by_year: dict[int | None, dict[str, int]] = defaultdict(dict)
    d_name: dict[int | None, str] = {}
    d_state: dict[int | None, str] = {}
    s_by_year: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    s_name: dict[int, str] = {}
    s_districts: dict[int, set[int | None]] = defaultdict(set)

    for dcode, scode, period, count, dname, sname in total_rows_q:
        c = int(count or 0)
        d_by_year[dcode][str(period)] = c
        d_name[dcode] = str(dname) if dname is not None else "(unplaced)"
        d_state[dcode] = str(sname)
        if scode is not None:
            s_by_year[int(scode)][str(period)] += c
            s_name[int(scode)] = str(sname)
            s_districts[int(scode)].add(dcode)

    def total_for(by_year: dict[str, int]) -> int:
        if display_period is not None and display_period in by_year:
            return by_year[display_period]
        return max(by_year.values()) if by_year else 0

    by_state = sorted(
        (
            StateVahanRow(
                lgd_state_code=scode,
                state=s_name[scode],
                districts=len([d for d in s_districts[scode] if d is not None]),
                ev_total=total_for(dict(years_map)),
                growth_pct=annual_growth(dict(years_map)),
            )
            for scode, years_map in s_by_year.items()
        ),
        key=lambda r: r.ev_total,
        reverse=True,
    )

    top_districts = sorted(
        (
            DistrictVahanRow(
                lgd_district_code=dcode,
                district=d_name[dcode],
                state=d_state[dcode],
                ev_total=total_for(by_year),
                growth_pct=annual_growth(by_year),
            )
            for dcode, by_year in d_by_year.items()
        ),
        key=lambda r: r.ev_total,
        reverse=True,
    )[:limit]

    # --- vehicle-class split for the display period ---------------------------
    by_class: list[ClassRow] = []
    if display_period is not None:
        class_rows = session.execute(
            select(VahanEvRegistration.vehicle_class, func.sum(VahanEvRegistration.count))
            .where(
                VahanEvRegistration.snapshot_date == latest,
                VahanEvRegistration.period == display_period,
                VahanEvRegistration.vehicle_class != TOTAL_CLASS,
            )
            .group_by(VahanEvRegistration.vehicle_class)
        ).all()
        grouped: dict[str, int] = defaultdict(int)
        for vclass, count in class_rows:
            grouped[_group_for(str(vclass))] += int(count or 0)
        order = [g for g, _ in _CLASS_GROUPS] + ["Other"]
        by_class = [
            ClassRow(group=g, ev_total=grouped[g]) for g in order if grouped.get(g)
        ]

    return VahanOut(
        checked_at=checked,
        snapshot_date=latest,
        periods=periods,
        display_period=display_period,
        total_rows=int(total_rows),
        by_state=by_state,
        top_districts=top_districts,
        by_class=by_class,
    )
