"""PART 3.1 - the tariff domain. Time-bounded rows, never overwritten.

    select.py   which effective-dated row governs a date. PURE.
    entry.py    what adding one order should do - insert vs supersede. PURE.
    parse/      one parser per SERC order, when extraction lands (3.1 later).

The tables live in ``app/models/tariffs.py``; the ROI engine (``domain/roi``)
never sees either - a human or a thin shell reads the governing row and types
its numbers into ``TariffTerms``, which keeps the engine pure and the tariff's
provenance a conscious step rather than an implicit join.
"""

from __future__ import annotations

from app.domain.tariffs.entry import (
    Action,
    InsertionPlan,
    plan_insertion,
    validate_candidate,
)
from app.domain.tariffs.select import (
    EffectiveDated,
    effective_on,
    is_effective,
    ranges_overlap,
    subsidy_paise,
)

__all__ = [
    "Action",
    "EffectiveDated",
    "InsertionPlan",
    "effective_on",
    "is_effective",
    "plan_insertion",
    "ranges_overlap",
    "subsidy_paise",
    "validate_candidate",
]
