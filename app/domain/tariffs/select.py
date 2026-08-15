"""Effective-dated selection - PART 3.1's reading half. PURE.

The tables (``app/models/tariffs.py``) hold every row ever written; these
functions decide which row governs a given date. Kept pure and generic over
"anything with effective_from / effective_to" so the same logic serves
tariffs, subsidies and (already) price cards without three copies drifting
apart - and so the report-regeneration property ("last March's report uses
last March's tariff") is a tested function, not a query someone remembers to
write correctly.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Protocol, TypeVar


class EffectiveDated(Protocol):
    effective_from: dt.date
    effective_to: dt.date | None


T = TypeVar("T", bound=EffectiveDated)


def is_effective(row: EffectiveDated, on: dt.date) -> bool:
    """A row governs ``on`` when ``effective_from <= on`` and the range is
    still open or closes after ``on``. ``effective_to`` is EXCLUSIVE - the
    day a new tariff starts, the old one no longer applies."""
    if row.effective_from > on:
        return False
    return row.effective_to is None or on < row.effective_to


def effective_on(rows: Sequence[T], on: dt.date) -> T | None:
    """The single row governing ``on``, or None.

    When ranges overlap (they should not - the loader refuses them - but data
    outlives loaders), the newest ``effective_from`` wins: the later order
    supersedes, which is how SERC orders themselves work.
    """
    candidates = [r for r in rows if is_effective(r, on)]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.effective_from)


def ranges_overlap(
    a_from: dt.date,
    a_to: dt.date | None,
    b_from: dt.date,
    b_to: dt.date | None,
) -> bool:
    """Do two effective ranges claim any day in common? Ends are exclusive,
    so back-to-back ranges (a_to == b_from) do NOT overlap - that is exactly
    how a supersession is supposed to look."""
    a_end = a_to or dt.date.max
    b_end = b_to or dt.date.max
    return a_from < b_end and b_from < a_end


def subsidy_paise(
    *,
    amount_paise: int | None,
    rate_bp: int | None,
    eligible_capex_paise: int,
) -> int:
    """Resolve one subsidy rule to money, mirroring the table's XOR check.

    A percentage rule is basis points of the ELIGIBLE capex - what counts as
    eligible is in the rule's ``conditions`` text and is the human's call
    when filling ROI inputs; this function only does the arithmetic.
    """
    if (amount_paise is None) == (rate_bp is None):
        raise ValueError("exactly one of amount_paise or rate_bp must be set")
    if amount_paise is not None:
        return amount_paise
    assert rate_bp is not None  # noqa: S101 - narrowed by the XOR above
    return round(eligible_capex_paise * rate_bp / 10_000)
