"""The /assess teaser - PLAN G.2's arithmetic, pure and pinned.

``compute_teaser`` takes a tariff row and the five taps and returns the one
certain number. The properties worth pinning are the honesty rules: taps that
move fixed costs move breakeven in the right DIRECTION, taps that move only
capex say so instead of pretending, an unanswered tap is echoed as not
provided, and a negative margin comes back as "no utilisation breaks even"
with the engine's own reason - never as an exception or a softened story.
"""

from __future__ import annotations

import datetime as dt

from app.domain.report.teaser import Taps, compute_teaser
from app.models.tariffs import ElectricityTariff


def _tariff(energy_paise: int = 640) -> ElectricityTariff:
    # A row shaped like the seeded KSERC order; no database needed - the
    # function is pure over the row object.
    return ElectricityTariff(
        lgd_state_code=32,
        discom="KSEB",
        consumer_category="LT EV charging",
        ev_specific=True,
        energy_paise_per_kwh=energy_paise,
        demand_paise_per_kva_month=40_000,
        fixed_paise_per_month=0,
        duty_bp=0,
        effective_from=dt.date(2024, 4, 1),
        order_number="OA-XX/2024",
        source_pdf="kserc_order.pdf",
    )


def test_defaults_produce_a_defensible_breakeven() -> None:
    t = compute_teaser(_tariff(), Taps())
    assert t.utilisation is not None and 0 < t.utilisation < 0.5
    assert t.kwh_day is not None and t.kwh_day > 0
    # Provenance must survive to the customer: the SERC order, by name.
    assert "OA-XX/2024" in t.tariff_source
    # All five taps unanswered - every echo must say so.
    assert all(not tap.provided for tap in t.taps)
    assert all("not provided" in tap.effect for tap in t.taps)


def test_owned_land_lowers_breakeven_and_supplied_kva_is_priced() -> None:
    base = compute_teaser(_tariff(), Taps())
    owned = compute_teaser(_tariff(), Taps(land_owned=True))
    assert owned.utilisation is not None and base.utilisation is not None
    # Rent is a fixed cost; dropping it must lower the bar, never raise it.
    assert owned.utilisation < base.utilisation

    heavy = compute_teaser(_tariff(), Taps(sanctioned_kva=400.0))
    assert heavy.sanctioned_kva == 400.0
    assert heavy.utilisation is not None
    # A fatter sanctioned load means fatter demand charges: a higher bar than
    # the managed-peak kVA the engine recommends when the tap is unanswered.
    assert heavy.utilisation > base.utilisation
    assert base.sanctioned_kva < 400.0  # the recommendation, not the ceiling


def test_capex_taps_admit_they_do_not_move_breakeven() -> None:
    base = compute_teaser(_tariff(), Taps())
    trimmed = compute_teaser(_tariff(), Taps(existing_connection=True, transformer_on_site=True))
    # Connection and transformer are capex; breakeven reads fixed costs and
    # margin only. The number must NOT move - and the echo must say why.
    assert trimmed.utilisation == base.utilisation
    for label in ("Existing electricity connection?", "Transformer on site?"):
        echo = next(tap for tap in trimmed.taps if tap.label == label)
        assert echo.provided
        assert "not breakeven" in echo.effect


def test_negative_margin_is_an_answer_not_an_error() -> None:
    # An energy tariff above the selling price: nothing breaks even, and the
    # teaser says so with the engine's own words rather than raising.
    t = compute_teaser(_tariff(energy_paise=3_000), Taps())
    assert t.utilisation is None
    assert t.kwh_year is None and t.kwh_day is None
    assert any("no utilisation breaks even" in note for note in t.notes)
