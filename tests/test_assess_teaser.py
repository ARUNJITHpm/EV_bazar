"""The /assess teaser - PLAN G.2's arithmetic, pure and pinned.

``compute_teaser`` takes a tariff row and the design flow's taps and returns
the one certain number. The properties worth pinning are the honesty rules:
the SPACE tap moves breakeven in the right DIRECTION (more plugs spread fixed
costs, so the bar drops), the transformer taps move only CAPEX and say so
instead of pretending, an unanswered tap is echoed as not provided, and a
negative margin comes back as "no utilisation breaks even" with the engine's
own reason - never as an exception or a softened story.
"""

from __future__ import annotations

import datetime as dt

from app.domain.report.teaser import (
    DEFAULT_CONNECTORS,
    Taps,
    compute_teaser,
)
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
    # The archetype default is a two-connector site.
    assert t.connectors == DEFAULT_CONNECTORS
    # Provenance must survive to the customer: the SERC order, by name.
    assert "OA-XX/2024" in t.tariff_source
    # All four taps unanswered - every echo must say so.
    assert all(not tap.provided for tap in t.taps)
    assert all("not provided" in tap.effect for tap in t.taps)


def test_more_space_means_more_plugs_and_a_lower_breakeven() -> None:
    base = compute_teaser(_tariff(), Taps())
    big = compute_teaser(_tariff(), Taps(space="large"))
    assert base.utilisation is not None and big.utilisation is not None
    # An open site is six connectors, not two.
    assert big.connectors == 6 and base.connectors == DEFAULT_CONNECTORS
    # More plugs spread the fixed costs (demand charge, rent) over a larger
    # ceiling, so the bar drops - never rises.
    assert big.utilisation < base.utilisation
    # And the echo must own the fact that this is the tap that moved it.
    echo = next(tap for tap in big.taps if tap.label == "How much space is there?")
    assert echo.provided
    assert "moved" in echo.effect


def test_transformer_answers_move_capex_not_breakeven() -> None:
    base = compute_teaser(_tariff(), Taps())
    # A big transformer on hand (covers the ~93 kVA managed peak) and a 200 m
    # cabling run: both are capex, which breakeven does not read.
    wired = compute_teaser(_tariff(), Taps(transformer_kva=250.0, transformer_distance_m=200.0))
    assert wired.utilisation == base.utilisation

    tx = next(tap for tap in wired.taps if tap.label == "Transformer near the site?")
    assert tx.provided
    assert "drops out" in tx.effect and "not this breakeven" in tx.effect

    dist = next(tap for tap in wired.taps if tap.label == "How far is the transformer?")
    assert dist.provided
    assert "connection cost" in dist.effect and "not this breakeven" in dist.effect


def test_a_small_transformer_still_needs_a_new_one() -> None:
    # 40 kVA is under the two-connector station's ~93 kVA managed peak, so a
    # new transformer stays in capex - the echo must not claim the cost dropped.
    t = compute_teaser(_tariff(), Taps(transformer_kva=40.0))
    tx = next(tap for tap in t.taps if tap.label == "Transformer near the site?")
    assert tx.provided
    assert "new transformer" in tx.effect and "stays in capex" in tx.effect


def test_intent_is_noted_but_admits_it_moves_no_arithmetic() -> None:
    base = compute_teaser(_tariff(), Taps())
    with_intent = compute_teaser(_tariff(), Taps(intent="income"))
    # Intent feeds the operator match, never the arithmetic - the number must
    # not move, and the echo must own that rather than implying influence.
    assert with_intent.utilisation == base.utilisation
    echo = next(tap for tap in with_intent.taps if tap.label == "What should this site do?")
    assert echo.provided
    assert "not this arithmetic" in echo.effect


def test_negative_margin_is_an_answer_not_an_error() -> None:
    # An energy tariff above the selling price: nothing breaks even, and the
    # teaser says so with the engine's own words rather than raising.
    t = compute_teaser(_tariff(energy_paise=3_000), Taps())
    assert t.utilisation is None
    assert t.kwh_year is None and t.kwh_day is None
    assert any("no utilisation breaks even" in note for note in t.notes)
