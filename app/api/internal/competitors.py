"""Competitor inventory - PART 2.3, the console read side.

Read-only views over ``competitor_stations``: the totals, who the networks are,
and how they split by state. This is the denominator panel - "how much
competition exists, and whose" - and the surface that will gain observed
occupancy once the poller runs.

Guarded: mounted on the ``guarded`` router in ``api/internal/__init__.py``.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.competitors import CompetitorStation
from app.models.reference import State

router = APIRouter()


class OperatorRow(BaseModel):
    operator: str
    stations: int
    #: How many carry any DC-fast connector (>= 50 kW). The threat that competes
    #: for a fast-charging site, distinct from AC points.
    dc_fast: int


class StateRow(BaseModel):
    lgd_state_code: int
    state: str
    stations: int


class CompetitorsOut(BaseModel):
    checked_at: dt.datetime
    total: int
    #: Stations no district polygon contained (offshore slivers, bad coords).
    unplaced: int
    fetched_from: list[str]
    by_state: list[StateRow]
    top_operators: list[OperatorRow]


#: The power at or above which a connector is "DC fast" for competition purposes.
_DC_FAST_KW = 50.0


@router.get("/competitors", response_model=CompetitorsOut)
def competitors(session: Session = Depends(get_session), limit: int = 15) -> CompetitorsOut:
    total = session.execute(select(func.count()).select_from(CompetitorStation)).scalar_one()
    unplaced = session.execute(
        select(func.count())
        .select_from(CompetitorStation)
        .where(CompetitorStation.lgd_district_code.is_(None))
    ).scalar_one()

    sources = [
        str(s)
        for s in session.execute(
            select(CompetitorStation.source).distinct().order_by(CompetitorStation.source)
        )
        .scalars()
        .all()
    ]

    by_state = [
        StateRow(lgd_state_code=int(code), state=str(name), stations=int(n))
        for code, name, n in session.execute(
            select(State.lgd_state_code, State.name, func.count(CompetitorStation.id))
            .join(CompetitorStation, CompetitorStation.lgd_state_code == State.lgd_state_code)
            .group_by(State.lgd_state_code, State.name)
            .order_by(func.count(CompetitorStation.id).desc())
        ).all()
    ]

    dc_fast = func.count().filter(CompetitorStation.max_power_kw >= _DC_FAST_KW)
    top_operators = [
        OperatorRow(operator=str(op or "(unattributed)"), stations=int(n), dc_fast=int(fast))
        for op, n, fast in session.execute(
            select(CompetitorStation.operator, func.count(CompetitorStation.id), dc_fast)
            .group_by(CompetitorStation.operator)
            .order_by(func.count(CompetitorStation.id).desc())
            .limit(min(limit, 50))
        ).all()
    ]

    return CompetitorsOut(
        checked_at=dt.datetime.now(dt.UTC),
        total=int(total),
        unplaced=int(unplaced),
        fetched_from=sources,
        by_state=by_state,
        top_operators=top_operators,
    )
