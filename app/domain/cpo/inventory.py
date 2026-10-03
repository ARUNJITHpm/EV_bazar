"""What the charger inventory says about each network - the console's read side.

``presence.py`` answers "how much of each network sits around THIS site".
This answers the flatter question the console needs: **who is in the inventory
at all, and how much of it can we actually name?**

It exists because ``identity.coverage`` is only useful if a human sees its
misses. An unresolved operator name is one missing line in
``identity.OPERATOR_ALIASES``, and nothing fixes itself: the console is where
that list has to appear, or the alias table quietly rots as new feeds land.

Same dedupe as ``presence.py`` and for the same reason - one charger seen
through Open Charge Map and through the operator's own feed is two rows by
design, so ``stations`` and ``raw_rows`` are both reported and the gap between
them is how much overlap the two feeds have.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.cpo.identity import UNATTRIBUTED, canonical_operator
from app.domain.cpo.presence import cell_of

#: At or above this, a connector competes for a fast-charging site. Matches
#: ``report/assemble.py``'s DC_FAST_KW; duplicated rather than imported, so the
#: cpo package does not depend on the report package.
DC_FAST_KW = 50.0


@dataclass(frozen=True)
class InventoryRow:
    """One row of ``competitor_stations``, reduced to what this module folds."""

    operator: str | None
    lat: float
    lng: float
    max_power_kw: float | None
    lgd_district_code: int | None
    lgd_state_code: int | None


@dataclass(frozen=True)
class OperatorRow:
    canonical: str
    #: Distinct stations after folding source duplicates within ~55 m.
    stations: int
    #: Rows before that fold. The gap is feed overlap, not new chargers.
    raw_rows: int
    dc_fast: int
    districts: int
    states: int


@dataclass(frozen=True)
class OperatorInventory:
    total_rows: int
    resolved_rows: int
    #: Rows the source itself declined to attribute. Not a gap in the alias
    #: table - there is nothing to look up - so it is counted separately.
    unattributed_rows: int
    operators: tuple[OperatorRow, ...]
    #: Raw name -> row count, for names we could not place. THE list to act on.
    unresolved: tuple[tuple[str, int], ...]

    @property
    def coverage_pct(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return round(100 * self.resolved_rows / self.total_rows, 1)


def fold_inventory(rows: Iterable[InventoryRow]) -> OperatorInventory:
    """Group the inventory by canonical network. Pure."""
    cells: dict[str, set[tuple[int, int]]] = {}
    raw: dict[str, int] = {}
    fast: dict[str, set[tuple[int, int]]] = {}
    districts: dict[str, set[int]] = {}
    states: dict[str, set[int]] = {}
    unresolved: dict[str, int] = {}
    total = 0
    resolved = 0
    unattributed = 0

    for row in rows:
        total += 1
        match = canonical_operator(row.operator)
        if match.canonical is None:
            if match.raw == UNATTRIBUTED:
                unattributed += 1
            elif match.confidence == "unresolved":
                unresolved[match.raw] = unresolved.get(match.raw, 0) + 1
            continue

        resolved += 1
        name = match.canonical
        cell = cell_of(row.lat, row.lng)
        cells.setdefault(name, set()).add(cell)
        raw[name] = raw.get(name, 0) + 1
        if (row.max_power_kw or 0) >= DC_FAST_KW:
            fast.setdefault(name, set()).add(cell)
        if row.lgd_district_code is not None:
            districts.setdefault(name, set()).add(row.lgd_district_code)
        if row.lgd_state_code is not None:
            states.setdefault(name, set()).add(row.lgd_state_code)

    operators = tuple(
        sorted(
            (
                OperatorRow(
                    canonical=name,
                    stations=len(seen),
                    raw_rows=raw[name],
                    dc_fast=len(fast.get(name, ())),
                    districts=len(districts.get(name, ())),
                    states=len(states.get(name, ())),
                )
                for name, seen in cells.items()
            ),
            key=lambda r: (-r.stations, r.canonical),
        )
    )
    return OperatorInventory(
        total_rows=total,
        resolved_rows=resolved,
        unattributed_rows=unattributed,
        operators=operators,
        unresolved=tuple(sorted(unresolved.items(), key=lambda kv: (-kv[1], kv[0]))),
    )


_INVENTORY_SQL = text("""
    SELECT operator, lat, lng, max_power_kw, lgd_district_code, lgd_state_code
    FROM competitor_stations
""")


def operator_inventory(session: Session) -> OperatorInventory:
    """The whole inventory, folded by network. One query, then a pure fold."""
    return fold_inventory(
        InventoryRow(
            operator=operator,
            lat=float(lat),
            lng=float(lng),
            max_power_kw=None if kw is None else float(kw),
            lgd_district_code=None if district is None else int(district),
            lgd_state_code=None if state is None else int(state),
        )
        for operator, lat, lng, kw, district, state in session.execute(_INVENTORY_SQL).all()
    )
