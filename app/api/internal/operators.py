"""Who is in the charger inventory, and how much of it we can name - PLAN C.4.

The CPO panel next door answers *are we allowed to poll this network*. This
answers *whose chargers do we actually hold, and which names defeated the alias
table* - the list a human has to work through, because an unresolved operator
name is one missing line in ``domain/cpo/identity.py`` and nothing fixes it by
itself.

Guarded: mounted on the ``guarded`` router in ``api/internal/__init__.py``.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.cpo.identity import CANONICAL
from app.domain.cpo.inventory import operator_inventory

router = APIRouter()

#: Ours. Surfaced so the panel can mark it, never so it can be treated
#: differently (OVERVIEW.md §6.3).
OUR_NETWORK = "chargeMOD"


class OperatorOut(BaseModel):
    canonical: str
    ours: bool
    #: Distinct stations after folding source duplicates within ~55 m.
    stations: int
    #: Rows before that fold. The gap is feed overlap, not extra chargers.
    raw_rows: int
    dc_fast: int
    districts: int
    states: int


class UnresolvedOut(BaseModel):
    raw: str
    rows: int


class OperatorsOut(BaseModel):
    checked_at: dt.datetime
    total_rows: int
    resolved_rows: int
    unattributed_rows: int
    coverage_pct: float
    #: Names the alias table knows about, whether or not any are in stock.
    canonical_known: int
    operators: list[OperatorOut]
    unresolved: list[UnresolvedOut]


@router.get("/operators", response_model=OperatorsOut)
def operators(session: Session = Depends(get_session)) -> OperatorsOut:
    """The inventory folded by network, plus the names that defeated it."""
    inv = operator_inventory(session)
    return OperatorsOut(
        checked_at=dt.datetime.now(dt.UTC),
        total_rows=inv.total_rows,
        resolved_rows=inv.resolved_rows,
        unattributed_rows=inv.unattributed_rows,
        coverage_pct=inv.coverage_pct,
        canonical_known=len(CANONICAL),
        operators=[
            OperatorOut(**{**row.__dict__, "ours": row.canonical == OUR_NETWORK})
            for row in inv.operators
        ],
        unresolved=[UnresolvedOut(raw=raw, rows=n) for raw, n in inv.unresolved],
    )
