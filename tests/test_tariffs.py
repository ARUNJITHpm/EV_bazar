"""PART 3.1 - effective-dated selection and the subsidy arithmetic. Pure."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pytest

from app.domain.tariffs import effective_on, is_effective, ranges_overlap, subsidy_paise


@dataclass(frozen=True)
class Row:
    effective_from: dt.date
    effective_to: dt.date | None
    label: str = ""


APRIL = dt.date(2025, 4, 1)
OCTOBER = dt.date(2025, 10, 1)


def test_an_open_ended_row_governs_everything_after_its_start() -> None:
    row = Row(APRIL, None)
    assert not is_effective(row, dt.date(2025, 3, 31))
    assert is_effective(row, APRIL)
    assert is_effective(row, dt.date(2030, 1, 1))


def test_effective_to_is_exclusive() -> None:
    """The day a new tariff starts, the old one no longer applies - a bill
    for October 1st under the September order double-charges the change."""
    row = Row(APRIL, OCTOBER)
    assert is_effective(row, dt.date(2025, 9, 30))
    assert not is_effective(row, OCTOBER)


def test_selection_picks_the_governing_row() -> None:
    old = Row(APRIL, OCTOBER, "old")
    new = Row(OCTOBER, None, "new")
    assert effective_on([old, new], dt.date(2025, 6, 1)).label == "old"
    assert effective_on([old, new], dt.date(2025, 12, 1)).label == "new"


def test_last_march_regenerates_under_last_march_rows() -> None:
    """THE property the whole table exists for."""
    rows = [Row(dt.date(2024, 4, 1), dt.date(2025, 4, 1), "fy24"), Row(APRIL, None, "fy25")]
    assert effective_on(rows, dt.date(2025, 3, 15)).label == "fy24"


def test_nothing_effective_is_none_not_a_guess() -> None:
    assert effective_on([Row(APRIL, None)], dt.date(2024, 1, 1)) is None


def test_overlapping_rows_resolve_to_the_newest_start() -> None:
    """Should not happen (the loader refuses it) but data outlives loaders:
    the later order supersedes, as SERC orders themselves do."""
    sloppy = [Row(APRIL, None, "april"), Row(dt.date(2025, 6, 1), None, "june")]
    assert effective_on(sloppy, dt.date(2025, 7, 1)).label == "june"


def test_back_to_back_ranges_do_not_overlap() -> None:
    """a_to == b_from is exactly what a clean supersession looks like."""
    assert not ranges_overlap(APRIL, OCTOBER, OCTOBER, None)


def test_containment_and_partial_overlap_are_caught() -> None:
    assert ranges_overlap(APRIL, None, OCTOBER, None)  # both open-ended
    assert ranges_overlap(APRIL, OCTOBER, dt.date(2025, 6, 1), dt.date(2025, 7, 1))
    assert ranges_overlap(dt.date(2025, 9, 1), dt.date(2025, 11, 1), APRIL, OCTOBER)


def test_disjoint_ranges_do_not_overlap() -> None:
    assert not ranges_overlap(APRIL, dt.date(2025, 5, 1), OCTOBER, None)


# --- subsidy arithmetic ------------------------------------------------------


def test_a_fixed_grant_is_itself() -> None:
    assert (
        subsidy_paise(amount_paise=500_000_00, rate_bp=None, eligible_capex_paise=1) == 500_000_00
    )


def test_a_rate_is_basis_points_of_eligible_capex() -> None:
    # 30% of Rs 20L
    assert (
        subsidy_paise(amount_paise=None, rate_bp=3000, eligible_capex_paise=20_00_000_00)
        == 6_00_000_00
    )


def test_both_or_neither_is_refused() -> None:
    with pytest.raises(ValueError):
        subsidy_paise(amount_paise=1, rate_bp=1, eligible_capex_paise=1)
    with pytest.raises(ValueError):
        subsidy_paise(amount_paise=None, rate_bp=None, eligible_capex_paise=1)
