"""The tariff-entry planner - app/domain/tariffs/entry.py.

The numbers in a tariff are the easy part; the DATES are where a careless add
destroys the product's reproduce-history claim. These tests pin the one thing
the entry path exists to get right - a new order SUPERSEDES the current one
(closes it, never edits it) - and pin that everything less clear-cut is refused
rather than guessed. Pure over in-memory rows: no database, no session.
"""

from __future__ import annotations

import datetime as dt

from app.domain.tariffs import Action, plan_insertion
from app.models.tariffs import ElectricityTariff

KERALA = 32


def _row(
    *,
    category: str = "LT-X EV Public Charging Stations",
    energy: int = 715,
    effective_from: dt.date = dt.date(2024, 12, 5),
    effective_to: dt.date | None = None,
    discom: str = "KSEBL",
    order_number: str = "KSERC w.e.f 05.12.2024",
    source_pdf: str = "https://example.org/kserc.pdf",
) -> ElectricityTariff:
    return ElectricityTariff(
        lgd_state_code=KERALA,
        discom=discom,
        consumer_category=category,
        ev_specific=True,
        energy_paise_per_kwh=energy,
        demand_paise_per_kva_month=0,
        fixed_paise_per_month=0,
        duty_bp=0,
        effective_from=effective_from,
        effective_to=effective_to,
        order_number=order_number,
        source_pdf=source_pdf,
    )


# --- the clean cases --------------------------------------------------------


def test_first_row_for_a_state_is_a_clean_insert() -> None:
    plan = plan_insertion([], _row())
    assert plan.action is Action.INSERT
    assert plan.writable
    assert plan.supersedes is None


def test_a_different_category_coexists_rather_than_conflicts() -> None:
    existing = [_row(category="LT-X EV Public Charging Stations")]
    plan = plan_insertion(existing, _row(category="HT-VI EV Charging Stations"))
    # Two categories in one state live side by side - no overlap by series.
    assert plan.action is Action.INSERT


def test_a_historical_row_back_to_back_before_an_open_one_inserts() -> None:
    # An open order from 2025; backfilling the superseded 2023-2025 order that
    # ends exactly where it begins is a clean insert (ends are exclusive).
    existing = [_row(effective_from=dt.date(2025, 1, 1))]
    plan = plan_insertion(
        existing,
        _row(effective_from=dt.date(2023, 1, 1), effective_to=dt.date(2025, 1, 1)),
    )
    assert plan.action is Action.INSERT


# --- supersession, the one automated case -----------------------------------


def test_a_later_order_supersedes_the_current_open_one() -> None:
    current = _row(effective_from=dt.date(2024, 12, 5))  # open
    candidate = _row(effective_from=dt.date(2027, 4, 1), energy=760)
    plan = plan_insertion([current], candidate)
    assert plan.action is Action.SUPERSEDE
    assert plan.writable
    assert plan.supersedes is current
    # The prior row is closed exactly at the new one's start - no gap, no overlap.
    assert plan.close_prior_at == dt.date(2027, 4, 1)


# --- the refusals -----------------------------------------------------------


def test_the_same_start_date_is_a_duplicate_not_a_second_row() -> None:
    existing = [_row(effective_from=dt.date(2024, 12, 5))]
    plan = plan_insertion(existing, _row(effective_from=dt.date(2024, 12, 5), energy=999))
    assert plan.action is Action.DUPLICATE
    assert not plan.writable


def test_overlapping_a_closed_historical_row_is_refused() -> None:
    # A closed 2023-2025 row; a candidate that starts inside it must not be
    # auto-resolved - editing closed history is the human's call.
    existing = [_row(effective_from=dt.date(2023, 1, 1), effective_to=dt.date(2025, 1, 1))]
    plan = plan_insertion(existing, _row(effective_from=dt.date(2024, 6, 1)))
    assert plan.action is Action.REFUSE
    assert not plan.writable


def test_a_candidate_before_the_open_row_it_overlaps_is_refused() -> None:
    # Overlaps the open current row but starts BEFORE it - not a forward
    # supersession, so it is refused rather than silently reordering history.
    existing = [_row(effective_from=dt.date(2024, 12, 5))]  # open
    plan = plan_insertion(existing, _row(effective_from=dt.date(2024, 1, 1), effective_to=None))
    assert plan.action is Action.REFUSE


# --- validation -------------------------------------------------------------


def test_a_nonpositive_energy_rate_is_invalid() -> None:
    plan = plan_insertion([], _row(energy=0))
    assert plan.action is Action.INVALID
    assert "energy_paise_per_kwh" in plan.reason


def test_missing_provenance_is_invalid() -> None:
    plan = plan_insertion([], _row(order_number="  "))
    assert plan.action is Action.INVALID
    assert "provenance" in plan.reason


def test_an_end_before_the_start_is_invalid() -> None:
    plan = plan_insertion(
        [], _row(effective_from=dt.date(2025, 1, 1), effective_to=dt.date(2024, 1, 1))
    )
    assert plan.action is Action.INVALID
    assert "effective_to" in plan.reason
