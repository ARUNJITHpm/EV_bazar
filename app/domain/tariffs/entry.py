"""PART 3.1 - the tariff-entry path. Adding a state's order, safely.

``seed_tariffs.py`` transcribed the first two states as reviewable Python
literals; this is the discipline for the NEXT state and for every revision,
where the danger is not the numbers but the DATES. A new SERC order does not
replace its predecessor - it SUPERSEDES it: the old row is CLOSED at the new
one's start, never edited or deleted. Overwrite it and the product's whole
claim - regenerate last March's report under last March's tariff - is gone.

``plan_insertion`` is that discipline as a pure function. Given the rows a
state already holds and one candidate, it returns exactly what should change:

    INSERT     no existing row for this category claims any of these dates
    SUPERSEDE  close the current open order at the new start, then add
    DUPLICATE  this exact row is already present - a safe skip on a re-run
    REFUSE     it overlaps history in a way only a human should resolve
    INVALID    the row itself is malformed - fix it and retry

It writes nothing; the caller applies the plan in one transaction. Auto-handling
is deliberately narrow: the ONE unambiguous case - a later order superseding the
current open one - is planned; everything else is refused with its reason.
Refusing to touch closed history is the safe default when the alternative is
silently rewriting the record a customer's bill is checked against.
"""

from __future__ import annotations

import datetime as dt
import enum
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.tariffs.select import ranges_overlap
from app.models.tariffs import ElectricityTariff


class Action(enum.StrEnum):
    INSERT = "insert"  # no conflict; add the row as-is
    SUPERSEDE = "supersede"  # close one open prior at the new start, then add
    DUPLICATE = "duplicate"  # this exact row is already present; skip
    REFUSE = "refuse"  # conflicts with existing data; a human resolves it
    INVALID = "invalid"  # the row itself is malformed; fix it and retry


@dataclass(frozen=True)
class InsertionPlan:
    action: Action
    candidate: ElectricityTariff
    #: For SUPERSEDE: the open row to close, and the date to close it at (the
    #: candidate's effective_from). None for every other action.
    supersedes: ElectricityTariff | None = None
    close_prior_at: dt.date | None = None
    #: Human-readable, always set - why the action is what it is.
    reason: str = ""

    @property
    def writable(self) -> bool:
        """INSERT and SUPERSEDE change the table. DUPLICATE is a safe skip;
        REFUSE and INVALID must never be written."""
        return self.action in (Action.INSERT, Action.SUPERSEDE)


def _series_key(row: ElectricityTariff) -> tuple[int, str | None, str]:
    """What makes two rows the SAME tariff across time: one state, one DISCOM,
    one consumer category. Different categories in a state coexist; the same
    category over time supersedes."""
    return (row.lgd_state_code, row.discom, row.consumer_category)


def validate_candidate(candidate: ElectricityTariff) -> list[str]:
    """Friendly pre-checks mirroring the table's constraints, so a bad row is a
    readable message here rather than an IntegrityError at commit."""
    problems: list[str] = []

    if candidate.energy_paise_per_kwh is None or candidate.energy_paise_per_kwh <= 0:
        problems.append("energy_paise_per_kwh must be a positive integer (paise)")

    ef, et = candidate.effective_from, candidate.effective_to
    if ef is None:
        problems.append("effective_from is required")
    elif et is not None and et <= ef:
        problems.append(
            "effective_to must be AFTER effective_from (it is exclusive), or null for the "
            "current order"
        )

    for field in ("order_number", "source_pdf"):
        value = getattr(candidate, field, None)
        if not (value and str(value).strip()):
            problems.append(f"{field} is required - a tariff without provenance is not data")

    for field in ("demand_paise_per_kva_month", "fixed_paise_per_month", "duty_bp"):
        value = getattr(candidate, field, 0) or 0
        if value < 0:
            problems.append(f"{field} cannot be negative")

    return problems


def plan_insertion(
    existing: Sequence[ElectricityTariff], candidate: ElectricityTariff
) -> InsertionPlan:
    """What adding ``candidate`` to ``existing`` should do. Pure - no session,
    no I/O; construct the rows in memory and this is fully testable."""
    problems = validate_candidate(candidate)
    if problems:
        return InsertionPlan(Action.INVALID, candidate, reason="; ".join(problems))

    series = [r for r in existing if _series_key(r) == _series_key(candidate)]

    # Already present: same series, same start. Re-running a loader is safe.
    if any(r.effective_from == candidate.effective_from for r in series):
        return InsertionPlan(
            Action.DUPLICATE,
            candidate,
            reason=(
                f"a row for this category effective {candidate.effective_from} is already "
                "present - a revision needs a new effective_from"
            ),
        )

    overlapping = [
        r
        for r in series
        if ranges_overlap(
            r.effective_from, r.effective_to, candidate.effective_from, candidate.effective_to
        )
    ]

    if not overlapping:
        return InsertionPlan(
            Action.INSERT,
            candidate,
            reason="no existing row for this category claims any of the candidate's dates",
        )

    if len(overlapping) == 1:
        prior = overlapping[0]
        # The one case worth automating: a later order superseding the current
        # OPEN one. Closing that row at the candidate's start removes the whole
        # overlap and leaves exactly one open row - the new one.
        if prior.effective_to is None and candidate.effective_from > prior.effective_from:
            return InsertionPlan(
                Action.SUPERSEDE,
                candidate,
                supersedes=prior,
                close_prior_at=candidate.effective_from,
                reason=(
                    f"supersedes the current open order (effective {prior.effective_from}), "
                    f"which will be closed at {candidate.effective_from}"
                ),
            )
        return InsertionPlan(
            Action.REFUSE,
            candidate,
            reason=(
                "overlaps an existing row that is not the current open order it cleanly "
                f"follows (existing {prior.effective_from} - {prior.effective_to or 'open'}). "
                "Resolve the effective dates by hand: superseding closed history is never "
                "automatic."
            ),
        )

    return InsertionPlan(
        Action.REFUSE,
        candidate,
        reason=(
            f"overlaps {len(overlapping)} existing rows for this category; the effective "
            "dates must be resolved by hand before it can be added."
        ),
    )
