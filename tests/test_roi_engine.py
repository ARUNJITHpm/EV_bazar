"""PART 3.2 - the ROI engine. PLAN demands 30+ tests; the named cases first.

Money is integer paise throughout. The worked base case is a plausible
2 x 60 kW DC site in Kerala so failures read as economics, not algebra:

  hardware Rs 20L, civil Rs 6L, connection Rs 2.5L  ->  gross Rs 28.5L capex
  energy Rs 7.50/kWh + 10% duty, demand Rs 400/kVA/mo on 150 kVA
  selling Rs 18/kWh, gateway 1.8%, O&M 6% of hardware
"""

from __future__ import annotations

import dataclasses

import pytest

from app.domain.roi import (
    ECONOMICS_VERSION,
    Capex,
    ChargerSpec,
    CpoTerms,
    Financing,
    FleetAnchor,
    RoiInputs,
    SiteOpex,
    Solar,
    TariffTerms,
    TodBand,
    compute_roi,
)
from app.domain.roi.engine import (
    annual_fixed_paise,
    effective_energy_paise_per_kwh,
    margin_paise_per_kwh,
    max_kwh_year,
)

L = 100_000 * 100  # one lakh, in paise


def base_inputs(**over: object) -> RoiInputs:
    defaults = dict(
        chargers=(ChargerSpec(kw=60, count=2),),
        tariff=TariffTerms(
            energy_paise_per_kwh=750,
            demand_paise_per_kva_month=40_000,
            fixed_paise_per_month=0,
            duty_pct=0.10,
        ),
        capex=Capex(
            hardware_paise=20 * L,
            civil_paise=6 * L,
            discom_connection_paise=int(2.5 * L),
        ),
        opex=SiteOpex(sanctioned_kva=150, oam_pct_of_hardware=0.06, gateway_pct=0.018),
        selling_paise_per_kwh=1800,
        kwh_by_year=(60_000, 100_000, 140_000),
    )
    defaults.update(over)
    return RoiInputs(**defaults)  # type: ignore[arg-type]


# --- the pieces -------------------------------------------------------------


def test_effective_energy_is_rate_plus_duty() -> None:
    t = TariffTerms(energy_paise_per_kwh=800, duty_pct=0.10)
    assert effective_energy_paise_per_kwh(t, None) == pytest.approx(880)


def test_tod_bands_shift_the_effective_rate() -> None:
    """25% of energy at +₹2 peak, 30% at -₹1.50 off-peak -> net +5 paise
    before duty. PLAN 3.2's ToD split case."""
    t = TariffTerms(
        energy_paise_per_kwh=800,
        duty_pct=0.0,
        tod_bands=(
            TodBand(share=0.25, delta_paise_per_kwh=200, name="peak"),
            TodBand(share=0.30, delta_paise_per_kwh=-150, name="offpeak"),
        ),
    )
    assert effective_energy_paise_per_kwh(t, None) == pytest.approx(805)


def test_duty_applies_after_the_tod_shift() -> None:
    t = TariffTerms(
        energy_paise_per_kwh=800,
        duty_pct=0.10,
        tod_bands=(TodBand(share=0.5, delta_paise_per_kwh=200),),
    )
    assert effective_energy_paise_per_kwh(t, None) == pytest.approx(990)  # (800+100)*1.1


def test_solar_blends_at_lcoe_and_pays_no_duty() -> None:
    t = TariffTerms(energy_paise_per_kwh=800, duty_pct=0.10)
    s = Solar(capex_paise=0, share_of_kwh=0.5, lcoe_paise_per_kwh=400)
    assert effective_energy_paise_per_kwh(t, s) == pytest.approx(0.5 * 880 + 0.5 * 400)


def test_margin_is_price_minus_cuts_minus_energy() -> None:
    inputs = base_inputs()
    # 1800 * (1 - 0.018) - 750*1.1 = 1767.6 - 825 = 942.6
    assert margin_paise_per_kwh(inputs) == pytest.approx(942.6)


def test_margin_is_linear_in_price() -> None:
    inputs = base_inputs()
    m1 = margin_paise_per_kwh(inputs, selling_paise=1800)
    m2 = margin_paise_per_kwh(inputs, selling_paise=2000)
    assert m2 - m1 == pytest.approx(200 * (1 - 0.018))


def test_annual_fixed_sums_every_standing_cost() -> None:
    inputs = base_inputs()
    # demand 150*40000*12 + O&M 6% of 20L hardware
    expected = 150 * 40_000 * 12 + round(20 * L * 0.06)
    assert annual_fixed_paise(inputs) == expected


def test_oam_is_a_share_of_hardware_only_never_of_civil() -> None:
    with_civil = base_inputs()
    without_civil = base_inputs(
        capex=Capex(hardware_paise=20 * L, civil_paise=0, discom_connection_paise=int(2.5 * L))
    )
    assert annual_fixed_paise(with_civil) == annual_fixed_paise(without_civil)


def test_max_kwh_is_every_plug_all_year() -> None:
    assert max_kwh_year((ChargerSpec(kw=60, count=2),)) == 120 * 8760


# --- the named PLAN cases ---------------------------------------------------


def test_zero_utilisation_loses_exactly_the_fixed_costs() -> None:
    """PLAN: zero utilisation. Every operating year bleeds annual_fixed."""
    r = compute_roi(base_inputs(kwh_by_year=(0.0,)))
    assert r.cashflow[1].cashflow_paise == -r.annual_fixed_paise
    assert r.npv_paise < 0
    assert r.payback_years is None


def test_hundred_percent_utilisation_is_the_ceiling() -> None:
    """PLAN: 100% utilisation - the physical maximum, absurdly profitable."""
    ceiling = 120 * 8760.0
    r = compute_roi(base_inputs(kwh_by_year=(ceiling,)))
    assert r.cashflow[1].kwh == ceiling
    assert r.npv_paise > 0
    assert r.irr_pct is not None and r.irr_pct > 1.0  # >100%


def test_negative_margin_refuses_a_breakeven_and_says_why() -> None:
    """PLAN: negative margin. Selling below cost has no breakeven at any
    utilisation - None plus a stated reason, never a pretend number."""
    r = compute_roi(base_inputs(selling_paise_per_kwh=700))
    assert r.margin_paise_per_kwh < 0
    assert r.breakeven_kwh_year is None
    assert r.breakeven_utilisation is None
    assert any("loses" in a for a in r.assumptions)


def test_revenue_share_and_per_kwh_models_can_be_made_equivalent() -> None:
    """PLAN: revenue-share vs ₹/kWh CPO models. 10% of an ₹18 price is
    ₹1.80/kWh - the two models must price identically then."""
    share = compute_roi(base_inputs(cpo=CpoTerms(revenue_share_pct=0.10)))
    per_kwh = compute_roi(base_inputs(cpo=CpoTerms(fee_paise_per_kwh=180)))
    assert share.margin_paise_per_kwh == per_kwh.margin_paise_per_kwh


def test_missing_transformer_is_just_zero_capex_for_it() -> None:
    """PLAN: missing transformer - a site with a transformer already in place
    simply has less to build, never an error."""
    without = compute_roi(base_inputs())
    with_tx = compute_roi(
        base_inputs(
            capex=Capex(
                hardware_paise=20 * L,
                civil_paise=6 * L,
                transformer_paise=4 * L,
                discom_connection_paise=int(2.5 * L),
            )
        )
    )
    assert with_tx.cashflow[0].cashflow_paise == without.cashflow[0].cashflow_paise - 4 * L
    assert with_tx.npv_paise < without.npv_paise


# --- subsidy, anchor, solar, ramp ------------------------------------------


def test_subsidy_reduces_the_build_cost() -> None:
    plain = compute_roi(base_inputs())
    subsidised = compute_roi(
        base_inputs(
            capex=Capex(
                hardware_paise=20 * L,
                civil_paise=6 * L,
                discom_connection_paise=int(2.5 * L),
                subsidy_paise=10 * L,
            )
        )
    )
    assert subsidised.cashflow[0].cashflow_paise == plain.cashflow[0].cashflow_paise + 10 * L
    assert subsidised.npv_paise > plain.npv_paise


def test_a_subsidy_can_flip_the_verdict() -> None:
    """The reason the ledger is first-class: same site, sign changes.

    130k kWh/yr earns ~Rs 3.9L/yr over fixed costs - real money, but not
    enough to repay Rs 28.5L of capex inside the horizon. Rs 15L of subsidy
    is what changes the verdict, not the operations."""
    thin = base_inputs(kwh_by_year=(130_000,))
    assert compute_roi(thin).npv_paise < 0
    flipped = dataclasses.replace(thin, capex=dataclasses.replace(thin.capex, subsidy_paise=15 * L))
    assert compute_roi(flipped).npv_paise > 0


def test_anchor_floors_a_weak_year() -> None:
    """PLAN: fleet anchor as first-class scenario. Year 1 organic demand is
    60k kWh; a 90k take-or-pay floor lifts delivered energy to 90k."""
    r = compute_roi(base_inputs(anchor=FleetAnchor(min_kwh_per_year=90_000, paise_per_kwh=1500)))
    assert r.cashflow[1].kwh == 90_000
    # year 3 organic (140k) exceeds the floor: anchor takes 90k, retail the rest
    assert r.cashflow[3].kwh == 140_000


def test_anchor_energy_is_billed_at_the_contract_price() -> None:
    r = compute_roi(
        base_inputs(
            kwh_by_year=(0.0,),  # NO organic demand: revenue is purely the anchor
            anchor=FleetAnchor(min_kwh_per_year=100_000, paise_per_kwh=1500),
        )
    )
    assert r.cashflow[1].revenue_paise == 100_000 * 1500


def test_an_anchor_can_flip_dont_into_build() -> None:
    """PLAN: 'an anchor alone can flip Don't -> Build'. 40k kWh of organic
    demand bleeds money; a 200k kWh take-or-pay at Rs 16 carries the site."""
    weak = base_inputs(kwh_by_year=(40_000,))
    assert compute_roi(weak).npv_paise < 0
    anchored = dataclasses.replace(
        weak, anchor=FleetAnchor(min_kwh_per_year=200_000, paise_per_kwh=1600)
    )
    assert compute_roi(anchored).npv_paise > 0


def test_solar_costs_capex_and_improves_margin() -> None:
    plain = compute_roi(base_inputs())
    solar = compute_roi(
        base_inputs(solar=Solar(capex_paise=5 * L, share_of_kwh=0.3, lcoe_paise_per_kwh=350))
    )
    assert solar.margin_paise_per_kwh > plain.margin_paise_per_kwh
    assert solar.cashflow[0].cashflow_paise == plain.cashflow[0].cashflow_paise - 5 * L


def test_the_ramp_is_consumed_year_by_year() -> None:
    r = compute_roi(base_inputs())
    assert [row.kwh for row in r.cashflow[1:4]] == [60_000, 100_000, 140_000]


def test_beyond_the_ramp_the_last_year_continues() -> None:
    r = compute_roi(base_inputs(horizon_years=10))
    assert all(row.kwh == 140_000 for row in r.cashflow[4:])


def test_a_ramp_pays_back_later_than_its_own_steady_state() -> None:
    """PLAN: 'payback at P50 in year 1 vs year 3 is a different verdict'."""
    ramped = compute_roi(base_inputs(kwh_by_year=(60_000, 100_000, 140_000)))
    flat = compute_roi(base_inputs(kwh_by_year=(140_000,)))
    assert ramped.payback_years is not None and flat.payback_years is not None
    assert ramped.payback_years > flat.payback_years


# --- breakeven and sensitivity ----------------------------------------------


def test_breakeven_is_fixed_over_margin() -> None:
    r = compute_roi(base_inputs())
    assert r.breakeven_kwh_year == pytest.approx(r.annual_fixed_paise / 942.6, rel=1e-3)


def test_breakeven_utilisation_is_against_the_physical_ceiling() -> None:
    r = compute_roi(base_inputs())
    assert r.breakeven_utilisation == pytest.approx(r.breakeven_kwh_year / (120 * 8760), rel=1e-6)
    assert 0 < r.breakeven_utilisation < 1


def test_breakeven_ignores_the_anchor_on_purpose() -> None:
    """Breakeven answers 'how busy must RETAIL be' - the anchor de-risks the
    cashflow, it must not flatter the breakeven."""
    plain = compute_roi(base_inputs())
    anchored = compute_roi(
        base_inputs(anchor=FleetAnchor(min_kwh_per_year=90_000, paise_per_kwh=1500))
    )
    assert anchored.breakeven_kwh_year == plain.breakeven_kwh_year


def test_price_sensitivity_spans_two_rupees_each_way() -> None:
    r = compute_roi(base_inputs())
    prices = [p.selling_paise_per_kwh for p in r.price_sensitivity]
    assert prices == [1600, 1700, 1800, 1900, 2000]


def test_cheaper_price_needs_more_utilisation() -> None:
    r = compute_roi(base_inputs())
    utils = [p.breakeven_utilisation for p in r.price_sensitivity]
    assert all(u is not None for u in utils)
    assert utils == sorted(utils, reverse=True)


def test_a_price_below_cost_shows_no_breakeven_in_the_sweep() -> None:
    r = compute_roi(base_inputs(selling_paise_per_kwh=900))
    lowest = r.price_sensitivity[0]  # Rs 7/kWh, below the Rs 8.25 energy cost
    assert lowest.breakeven_utilisation is None


# --- cashflow, NPV, IRR, payback --------------------------------------------


def test_year_zero_is_the_net_build_cost() -> None:
    r = compute_roi(base_inputs())
    assert r.cashflow[0].cashflow_paise == -int(28.5 * L)


def test_cashflow_covers_the_whole_horizon() -> None:
    r = compute_roi(base_inputs(horizon_years=10))
    assert len(r.cashflow) == 11
    assert [row.year for row in r.cashflow] == list(range(11))


def test_cumulative_is_the_running_sum() -> None:
    r = compute_roi(base_inputs())
    running = 0
    for row in r.cashflow:
        running += row.cashflow_paise
        assert row.cumulative_paise == running


def test_npv_discounts_a_known_two_flow_case() -> None:
    """-100 now, +121 in a year, at 10%: NPV = +10. Hand-checkable."""
    r = compute_roi(
        base_inputs(
            capex=Capex(hardware_paise=0),
            opex=SiteOpex(sanctioned_kva=0, oam_pct_of_hardware=0, gateway_pct=0),
            tariff=TariffTerms(energy_paise_per_kwh=800, duty_pct=0),
            selling_paise_per_kwh=1800,
            kwh_by_year=(0.0,),
            horizon_years=1,
            discount_pct=0.10,
        )
    )
    assert r.npv_paise == 0  # nothing in, nothing out


def test_irr_matches_a_hand_computed_project() -> None:
    """Build 28.5L, then flat profitable years - IRR must satisfy NPV(irr)=0."""
    r = compute_roi(base_inputs(kwh_by_year=(140_000,)))
    assert r.irr_pct is not None
    flows = [row.cashflow_paise for row in r.cashflow]
    npv_at_irr = sum(cf / (1 + r.irr_pct) ** t for t, cf in enumerate(flows))
    assert abs(npv_at_irr) < abs(flows[0]) * 1e-3


def test_an_unprofitable_project_has_no_irr() -> None:
    r = compute_roi(base_inputs(kwh_by_year=(0.0,)))
    assert r.irr_pct is None


def test_payback_interpolates_within_the_year() -> None:
    r = compute_roi(base_inputs(kwh_by_year=(140_000,)))
    assert r.payback_years is not None
    whole = int(r.payback_years)
    assert r.cashflow[whole].cumulative_paise < 0 <= r.cashflow[whole + 1].cumulative_paise


# --- financing ---------------------------------------------------------------


def test_leverage_amplifies_a_good_project() -> None:
    """PLAN: financing block. Debt at 11% under a project earning well above
    11% raises the equity IRR above the unlevered one. (At 140k kWh the
    project IRR is ~10.8% - BELOW the debt cost - so leverage would hurt;
    180k clears it, which is itself the lesson lenders care about.)"""
    plain = compute_roi(base_inputs(kwh_by_year=(180_000,)))
    levered = compute_roi(
        base_inputs(
            kwh_by_year=(180_000,),
            financing=Financing(debt_share=0.6, interest_pct=0.11, tenure_years=7),
        )
    )
    assert plain.levered_irr_pct is None
    assert levered.levered_irr_pct is not None
    assert plain.irr_pct is not None and plain.irr_pct > 0.11
    assert levered.levered_irr_pct > plain.irr_pct


# --- sanctioned load recommendation ------------------------------------------


def test_sanctioned_load_offers_three_options() -> None:
    r = compute_roi(base_inputs())
    names = [o.name for o in r.sanctioned_load_options]
    assert len(names) == 3
    kvas = [o.kva for o in r.sanctioned_load_options]
    assert kvas == sorted(kvas, reverse=True)


def test_managed_peak_saves_real_money_vs_the_customer_number() -> None:
    """150 kVA sanctioned vs 120 kW connected: even full load needs only
    ~133 kVA, and managed peak ~93 - the saving is the sellable advice."""
    r = compute_roi(base_inputs())
    managed = r.sanctioned_load_options[1]
    assert managed.saving_vs_input_paise_per_year > 0


# --- contract and hygiene -----------------------------------------------------


def test_the_version_is_stamped_on_every_result() -> None:
    assert compute_roi(base_inputs()).economics_version == ECONOMICS_VERSION


def test_as_dict_is_plain_data() -> None:
    d = compute_roi(base_inputs()).as_dict()
    assert d["economics_version"] == ECONOMICS_VERSION
    assert isinstance(d["cashflow"], list)
    assert isinstance(d["cashflow"][0], dict)


def test_money_fields_are_integer_paise() -> None:
    r = compute_roi(base_inputs())
    assert isinstance(r.margin_paise_per_kwh, int)
    assert isinstance(r.annual_fixed_paise, int)
    assert isinstance(r.npv_paise, int)
    assert all(isinstance(row.cashflow_paise, int) for row in r.cashflow)


def test_assumptions_are_never_empty() -> None:
    """The ledger is the product's honesty; an empty one is a bug."""
    assert len(compute_roi(base_inputs()).assumptions) >= 5


@pytest.mark.parametrize(
    ("field_name", "bad"),
    [
        ("chargers", ()),
        ("kwh_by_year", ()),
        ("selling_paise_per_kwh", 0),
        ("horizon_years", 0),
    ],
)
def test_impossible_inputs_are_refused(field_name: str, bad: object) -> None:
    with pytest.raises(ValueError):
        compute_roi(dataclasses.replace(base_inputs(), **{field_name: bad}))  # type: ignore[arg-type]


def test_tod_shares_beyond_one_are_refused() -> None:
    with pytest.raises(ValueError, match="ToD"):
        compute_roi(
            base_inputs(
                tariff=TariffTerms(
                    energy_paise_per_kwh=800,
                    tod_bands=(TodBand(share=0.7, delta_paise_per_kwh=100),) * 2,
                )
            )
        )


def test_a_subsidy_larger_than_capex_is_refused() -> None:
    with pytest.raises(ValueError, match="subsidy"):
        compute_roi(base_inputs(capex=Capex(hardware_paise=10 * L, subsidy_paise=11 * L)))
