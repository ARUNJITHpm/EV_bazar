"""The pure VAHAN core - PART 4.1.

Parsing, district aggregation and growth are a function of their inputs and
nothing else, so they are pinned here without a browser or a database. What is
worth guarding: a non-EV fuel row can never inflate a count, an RTO that failed
to place still keeps its state total, and growth off a zero base is refused
rather than reported as infinite.
"""

from __future__ import annotations

from app.domain.vahan.parse import (
    EV_FUELS,
    RtoClassCount,
    aggregate_by_district,
    annual_growth,
    normalise_class,
    parse_vahan_csv,
    to_csv,
)

# KL=32, TN=33 in LGD; two Ernakulam RTOs to prove they merge into one district.
_LONG_CSV = """state_code,rto,period,fuel,vehicle_class,count
KL,ERNAKULAM RTO - KL7,2024,ELECTRIC(BOV),2WN,"1,000"
KL,ERNAKULAM RTO - KL7,2024,ELECTRIC(BOV),OMNI BUS,10
KL,ERNAKULAM RTO - KL7,2024,ELECTRIC(BOV),TOTAL,"1,010"
KL,ERNAKULAM RTO - KL7,2024,PETROL,2WN,"9,999"
KL,TRIPUNITHURA RTO - KL39,2024,ELECTRIC(BOV),2WN,500
KL,TRIPUNITHURA RTO - KL39,2024,ELECTRIC(BOV),TOTAL,500
"""


def test_normalise_class_collapses_case_and_spacing() -> None:
    assert normalise_class("omni  bus") == "OMNI BUS"
    assert normalise_class(" 2wn ") == "2WN"


def test_parse_drops_non_ev_fuels() -> None:
    rows = parse_vahan_csv(_LONG_CSV)
    assert all(r.fuel in EV_FUELS for r in rows)
    # the PETROL 2WN row is gone; the EV rows survive
    assert not any(r.fuel == "PETROL" for r in rows)
    assert any(r.vehicle_class == "2WN" and r.count == 1000 for r in rows)


def test_parse_reads_thousands_separators() -> None:
    rows = parse_vahan_csv(_LONG_CSV)
    total = next(r for r in rows if r.rto.startswith("ERNAKULAM") and r.vehicle_class == "TOTAL")
    assert total.count == 1010


def test_aggregate_sums_rtos_into_one_district() -> None:
    rows = parse_vahan_csv(_LONG_CSV)
    # both Ernakulam RTOs place into district 302 (Ernakulam), state 32 (KL)
    placement = {
        ("KL", "ERNAKULAM RTO - KL7"): (302, 32),
        ("KL", "TRIPUNITHURA RTO - KL39"): (302, 32),
    }
    slices = aggregate_by_district(rows, placement)
    twn = next(s for s in slices if s.vehicle_class == "2WN")
    assert twn.lgd_district_code == 302
    assert twn.count == 1500  # 1000 + 500
    assert twn.rto_count == 2  # two distinct RTOs fed it
    # the bus class came from only one RTO
    bus = next(s for s in slices if s.vehicle_class == "OMNI BUS")
    assert bus.count == 10
    assert bus.rto_count == 1


def test_unplaced_rto_keeps_its_state_total() -> None:
    rows = parse_vahan_csv(_LONG_CSV)
    # Ernakulam places; Tripunithura fails point-in-polygon (None district) but
    # its state is still known.
    placement = {
        ("KL", "ERNAKULAM RTO - KL7"): (302, 32),
        ("KL", "TRIPUNITHURA RTO - KL39"): (None, 32),
    }
    slices = aggregate_by_district(rows, placement)
    unplaced = [s for s in slices if s.lgd_district_code is None]
    assert unplaced, "the unplaced RTO must still produce a slice"
    assert all(s.lgd_state_code == 32 for s in unplaced)
    assert any(s.vehicle_class == "2WN" and s.count == 500 for s in unplaced)


def test_missing_placement_falls_to_unplaced_not_dropped() -> None:
    rows = parse_vahan_csv(_LONG_CSV)
    slices = aggregate_by_district(rows, placement={})  # nobody placed
    assert slices, "no placement must not mean no data"
    assert all(s.lgd_district_code is None for s in slices)


def test_csv_round_trips() -> None:
    original = [
        RtoClassCount("KL", "ADOOR SRTO - KL26", "2024", "PURE EV", "2WN", 727),
        RtoClassCount("TN", "CHENNAI (EAST) - TN01", "2023", "ELECTRIC(BOV)", "OMNI BUS", 4),
    ]
    reparsed = parse_vahan_csv(to_csv(original))
    assert reparsed == original


def test_annual_growth_two_years() -> None:
    assert annual_growth({"2023": 100, "2024": 130}) == 0.30


def test_annual_growth_needs_two_years() -> None:
    assert annual_growth({"2024": 100}) is None


def test_annual_growth_refuses_zero_base() -> None:
    # a first arrival is "new", not an infinite rate
    assert annual_growth({"2023": 0, "2024": 42}) is None


def test_annual_growth_ignores_non_year_periods() -> None:
    # a snapshot may mix per-year rows and a cumulative "till_today" row
    assert annual_growth({"2023": 100, "2024": 150, "till_today": 9999}) == 0.50
