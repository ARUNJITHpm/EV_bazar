"""Bill validation and the small rules around it: the kWh ceiling, masking, the meter."""

from __future__ import annotations

import datetime as dt

from app.domain.owner.bill import (
    BillFields,
    ManualExtractor,
    implies_separate_meter,
    indian_grouping,
    kwh_limit,
    mask_consumer_number,
    resolve_meter,
    validate,
)

TODAY = dt.date(2026, 9, 30)
LIVE = dt.date(2026, 1, 1)
JUNE = dt.date(2026, 6, 1)


def _errors(bill: BillFields, kw: float = 120.0, live: dt.date | None = LIVE) -> list[str]:
    return validate(bill, total_kw=kw, went_live=live, today=TODAY)


def test_a_plain_bill_with_period_and_kwh_is_fine() -> None:
    assert _errors(BillFields(period=JUNE, kwh=4200)) == []


def test_kwh_must_be_above_zero() -> None:
    assert _errors(BillFields(period=JUNE, kwh=0))
    assert _errors(BillFields(period=JUNE, kwh=-5))


def test_kwh_ceiling_is_total_kw_times_744_and_the_message_names_it() -> None:
    limit = kwh_limit(120.0)
    assert limit == 120 * 744 == 89_280
    assert _errors(BillFields(period=JUNE, kwh=limit)) == []
    [msg] = _errors(BillFields(period=JUNE, kwh=limit + 1))
    # the specific limit, in Indian grouping, and where it came from
    assert "89,280 kWh" in msg
    assert "120 kW" in msg and "744" in msg


def test_ceiling_follows_the_connectors_not_a_fixed_number() -> None:
    small = BillFields(period=JUNE, kwh=6000)
    assert _errors(small, kw=7.4)  # 7.4 x 744 = 5,505.6
    assert _errors(small, kw=60) == []


def test_indian_grouping() -> None:
    assert indian_grouping(950) == "950"
    assert indian_grouping(89_280) == "89,280"
    assert indian_grouping(1_234_567) == "12,34,567"


def test_period_cannot_be_in_the_future_or_before_go_live() -> None:
    assert _errors(BillFields(period=dt.date(2026, 11, 1), kwh=100))
    assert _errors(BillFields(period=dt.date(2025, 12, 1), kwh=100))
    assert _errors(BillFields(period=dt.date(2025, 12, 1), kwh=100), live=None) == []


def test_history_is_capped_at_twelve_months_and_checked_like_a_bill() -> None:
    twelve = tuple((dt.date(2025, m, 1), 500.0) for m in range(1, 13))
    assert _errors(BillFields(period=JUNE, kwh=100, history=twelve), live=None) == []
    assert _errors(BillFields(period=JUNE, kwh=100, history=(*twelve, (JUNE, 1.0))), live=None)
    bad = ((dt.date(2026, 3, 1), 10_000_000.0),)
    assert _errors(BillFields(period=JUNE, kwh=100, history=bad))


def test_demand_needs_a_unit_and_a_positive_value() -> None:
    assert _errors(BillFields(period=JUNE, kwh=100, contract_demand=90))
    assert _errors(BillFields(period=JUNE, kwh=100, contract_demand=90, demand_unit="kVA")) == []
    assert _errors(BillFields(period=JUNE, kwh=100, recorded_demand=0, demand_unit="kW"))


def test_power_factor_range_and_penalty_direction() -> None:
    assert _errors(BillFields(period=JUNE, kwh=100, power_factor=1.2))
    assert _errors(BillFields(period=JUNE, kwh=100, power_factor=0.92)) == []
    assert _errors(BillFields(period=JUNE, kwh=100, pf_amount_paise=1500_00))  # which way?
    ok = BillFields(period=JUNE, kwh=100, pf_amount_paise=1500_00, pf_effect="penalty")
    assert _errors(ok) == []


def test_time_of_day_units_cannot_exceed_the_bill() -> None:
    fine = BillFields(
        period=JUNE, kwh=1000, tod_peak_kwh=300, tod_normal_kwh=500, tod_offpeak_kwh=200
    )
    assert _errors(fine) == []
    over = BillFields(period=JUNE, kwh=1000, tod_peak_kwh=600, tod_normal_kwh=600)
    assert _errors(over)


def test_consumer_number_keeps_only_the_last_four() -> None:
    assert mask_consumer_number("1145 8890 2233") == "2233"
    assert mask_consumer_number("12") is None
    assert mask_consumer_number(None) is None


def test_ev_tariff_category_settles_the_meter_question() -> None:
    assert implies_separate_meter("LT-VI EV Charging")
    assert implies_separate_meter("EV")
    assert not implies_separate_meter("LT-IV Commercial")
    assert resolve_meter("HT EV charging station", "shared") == "separate"
    assert resolve_meter("LT-IV Commercial", "shared") == "shared"
    assert resolve_meter(None, None) == "unsure"


def test_the_first_extractor_proposes_nothing() -> None:
    proposed = ManualExtractor().extract(b"%PDF-1.4", "application/pdf")
    assert proposed.fields == {}
    assert proposed.extractor == "manual"
