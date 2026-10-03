"""PLAN 5's back half - assemble the 7-section payload, store it, serve it.

Context slices that need PostGIS (competitors) or the network (roads, POIs)
are injected as fixtures; VAHAN and the tariff are read from a seeded SQLite
database through the same queries production uses. The properties pinned are
the honesty rules: money only from the engine, margin as pure subtraction,
missing layers degrading to unverified facts, stored payloads served verbatim.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.context.poi import PoiGravity
from app.domain.context.roads import RoadFeatures
from app.domain.cpo.presence import OperatorPresence
from app.domain.demand.synthetic import load_weights
from app.domain.report.assemble import (
    ROAD_FRONTAGE_MEANS,
    CompetitorContext,
    CpoOption,
    NearbyCompetitor,
    ReportSpec,
    assemble_report,
)
from app.domain.report.payload import ReportPayload
from app.domain.report.store import get_payload, save_report
from app.domain.roi.engine import Capex, CpoTerms, RoiInputs
from app.models import Base
from app.models.report import Report
from app.models.tariffs import ElectricityTariff
from app.models.vahan import VahanEvRegistration

SNAPSHOT = dt.date(2026, 8, 18)
DISTRICT, STATE = 565, 32


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            VahanEvRegistration.__table__,
            ElectricityTariff.__table__,
            Report.__table__,
        ],
    )
    with Session(engine) as s:
        _seed(s)
        yield s


def _seed(s: Session) -> None:
    ids = iter(range(1, 100))

    def vahan(period: str, vclass: str, count: int) -> VahanEvRegistration:
        # Explicit ids: SQLite does not autoincrement a BigInteger Identity
        # PK (same shim the conftest applies to the poller's event tables).
        return VahanEvRegistration(
            id=next(ids),
            lgd_district_code=DISTRICT,
            lgd_state_code=STATE,
            snapshot_date=SNAPSHOT,
            period=period,
            fuel_category="PURE EV",
            vehicle_class=vclass,
            count=count,
            source_sha256="0" * 64,
        )

    s.add_all(
        [
            vahan("2024", "TOTAL", 13406),
            vahan("2025", "TOTAL", 17895),
            vahan("2025", "2WN", 14280),
            vahan("2025", "LMV", 2783),
            ElectricityTariff(
                lgd_state_code=STATE,
                discom="KSEB",
                consumer_category="LT EV charging",
                ev_specific=True,
                energy_paise_per_kwh=640,
                demand_paise_per_kva_month=40_000,
                effective_from=dt.date(2024, 4, 1),
                order_number="OA-XX/2024",
                source_pdf="kserc_order.pdf",
            ),
        ]
    )
    s.flush()


SPEC = ReportSpec(
    report_id="TEST-001",
    demo=True,
    name="Test stretch",
    line="NH-66 · Thiruvananthapuram",
    district_name="Thiruvananthapuram",
    lgd_district_code=DISTRICT,
    lgd_state_code=STATE,
    lat=8.567,
    lng=76.873,
    archetype="urban_office_arterial",
    archetype_hand_assigned=True,
    connectors=2,
    rated_kw_each=60.0,
    selling_paise_per_kwh=2200,
    capex=Capex(hardware_paise=120_000_000, civil_paise=30_000_000),
    rent_paise_per_month=4_000_000,
    anchor_kwh_year=200_000.0,
    anchor_paise_per_kwh=1800,
    cpo_options=(
        CpoOption("chargeMOD", True, CpoTerms(0.10, 0, 100_000), True),
        CpoOption("Self-operate", False, CpoTerms(), False),
    ),
)

COMPETITORS = CompetitorContext(
    within_3km=8,
    within_5km=10,
    dc_fast_within_3km=3,
    nearest=(NearbyCompetitor("Akshaya EV", "chargeMOD", 246, 30.0, 2),),
    source="fixture",
)
#: One network on the table has a real footprint here, the other row is not a
#: network at all - the two paths section 06 has to keep apart. Injected for
#: the same reason COMPETITORS is: the query behind it is PostGIS.
PRESENCE = {
    "chargeMOD": OperatorPresence(
        canonical="chargeMOD",
        stations_district=14,
        stations_state=96,
        own_within_3km=2,
        own_within_10km=5,
    )
}

ROADS = RoadFeatures("trunk", "NH 66", 40.0, True, 3)
POIS = PoiGravity(
    counts={500: {"food": 2}, 1000: {"food": 4}, 3000: {"food": 9}},
    dwell_anchor_score=5.5,
    dwell_anchors=("Technopark Mall",),
)


def _assemble(session: Session, **overrides: object) -> ReportPayload:
    kwargs: dict[str, object] = {
        "roads": ROADS,
        "pois": POIS,
        "competitors": COMPETITORS,
        "presence": PRESENCE,
    }
    kwargs.update(overrides)
    return assemble_report(session, SPEC, load_weights(), **kwargs).payload  # type: ignore[arg-type]


def test_the_margin_is_p10_minus_breakeven_and_drives_the_verdict(session: Session) -> None:
    p = _assemble(session)
    assert p.breakeven.utilisation > 0
    expected = round((p.predicted.p10 - p.breakeven.utilisation) * 100, 1)
    assert p.margin_of_safety_pp == expected
    if p.margin_of_safety_pp >= 0:
        assert p.verdict.value == "build"
    else:
        assert p.verdict.value in ("conditional", "dont")


def test_the_band_is_ordered_and_flagged_modelled(session: Session) -> None:
    p = _assemble(session)
    assert p.predicted.p10 < p.predicted.p50 < p.predicted.p90
    assert p.predicted.model_version == "synthetic_v0"
    assert p.predicted.modelled_not_measured is True


def test_scenarios_order_with_utilisation(session: Session) -> None:
    """More energy through the same cost structure can never mean less NPV -
    if it does, the assembler mangled what the engine returned."""
    p = _assemble(session)
    npvs = [s.npv_paise for s in p.financials.scenarios]
    assert npvs == sorted(npvs)
    assert len(p.financials.scenarios) == 3


def test_cpo_table_ranks_on_irr_and_keeps_ours_unprivileged(session: Session) -> None:
    p = _assemble(session)
    # No return (None) ranks below any return; it is never dressed as 0%.
    irrs = [-1.0 if c.irr_p50_pct is None else c.irr_p50_pct for c in p.cpo]
    assert irrs == sorted(irrs, reverse=True)
    assert any(c.ours for c in p.cpo)


def test_operator_presence_lands_on_the_row_and_unknown_is_not_zero(session: Session) -> None:
    p = _assemble(session)
    ours = next(c for c in p.cpo if c.operator == "chargeMOD")
    assert (ours.stations_district, ours.own_within_3km, ours.own_within_10km) == (14, 2, 5)
    assert "2 stations of their own within 3 km" in ours.presence_note
    assert "14 in this district and 96 in the state" in ours.presence_note

    # "Self-operate" is not a network we failed to match, and must not read as
    # one - nor may its counts render as zero stations.
    self_run = next(c for c in p.cpo if c.operator == "Self-operate")
    assert self_run.stations_district is None
    assert self_run.own_within_3km is None
    assert "yourself" in self_run.presence_note
    assert "unknown" not in self_run.presence_note


def test_presence_never_moves_the_money(session: Session) -> None:
    """Counts sit beside the return; they are never blended into it."""
    with_presence = _assemble(session)
    without = _assemble(session, presence={})
    assert [c.irr_p50_pct for c in with_presence.cpo] == [c.irr_p50_pct for c in without.cpo]
    assert [c.margin_of_safety_pp for c in with_presence.cpo] == [
        c.margin_of_safety_pp for c in without.cpo
    ]
    assert [c.operator for c in with_presence.cpo] == [c.operator for c in without.cpo]
    # And with no inventory at all, the footprint is unknown rather than zero.
    assert all(c.stations_district is None for c in without.cpo)


def test_synthetic_band_is_a_flagged_ledger_row(session: Session) -> None:
    p = _assemble(session)
    row = next(r for r in p.ledger if r.item == "Utilisation band")
    assert row.unverified is True
    assert "synthetic_v0" in row.value


def test_vahan_context_reads_from_the_database(session: Session) -> None:
    p = _assemble(session)
    assert p.demand.district_ev_2025 == 17895
    assert p.demand.district_growth_yoy_pct == pytest.approx(33.5, abs=0.1)
    assert p.demand.two_wheeler_share_pct == pytest.approx(84, abs=1)


def test_missing_road_layer_degrades_to_an_unverified_fact(session: Session) -> None:
    """A context layer that could not be fetched must surface as ⚠ 'pending',
    never as an invented road."""
    p = _assemble(session, roads=None, pois=None)
    road = next(f for f in p.site_facts if f.label == "Road frontage")
    assert road.unverified is True
    assert road.value == "not assessed"


def test_stored_payload_is_served_verbatim(session: Session) -> None:
    p = _assemble(session)
    save_report(session, p, site_id=None, model_version="synthetic_v0", economics_version="0.1.0")
    assert get_payload(session, p.report_id) == p.model_dump()


def test_a_non_demo_report_refuses_overwrite(session: Session) -> None:
    p = _assemble(session).model_copy(update={"demo": False, "report_id": "CUST-1"})
    save_report(session, p, site_id=None, model_version="synthetic_v0", economics_version="0.1.0")
    with pytest.raises(ValueError, match="never an overwrite"):
        save_report(
            session, p, site_id=None, model_version="synthetic_v0", economics_version="0.1.0"
        )


def test_a_demo_report_may_regenerate_in_place(session: Session) -> None:
    p = _assemble(session)
    save_report(session, p, site_id=None, model_version="synthetic_v0", economics_version="0.1.0")
    p2 = p.model_copy(update={"margin_of_safety_pp": -1.0})
    save_report(session, p2, site_id=None, model_version="synthetic_v0", economics_version="0.1.0")
    stored = get_payload(session, p.report_id)
    assert stored is not None and stored["margin_of_safety_pp"] == -1.0


def test_every_site_fact_carries_a_heading_and_a_direction(session: Session) -> None:
    """The factors table is the anti-bias mechanism: every row lands on one
    side of the argument, under a heading, and the favourable ones on a
    rejected site are counted at equal weight."""
    p = _assemble(session)
    assert len(p.site_facts) >= 12
    groups = {f.group for f in p.site_facts}
    assert {"Access and geometry", "Demand", "Power and tariff", "Competition"} <= groups
    directions = {f.direction for f in p.site_facts}
    assert directions <= {"favours", "against", "neutral"}
    assert None not in directions
    # A crowded corridor (8 within 3 km, nearest 246 m) argues against.
    nearest = next(f for f in p.site_facts if f.label == "Nearest charger")
    assert nearest.direction == "against"
    three = next(f for f in p.site_facts if f.label == "Stations within 3 km")
    assert three.direction == "against"
    # And the trunk road 40 m away argues for - shown at equal weight.
    road = next(f for f in p.site_facts if f.label == "Road frontage")
    assert road.direction == "favours"
    assert p.competitors.within_5km == 10
    assert p.competitors.dc_fast_within_3km == 3


def test_every_site_fact_says_what_it_means(session: Session) -> None:
    """Section 04's third column (Track B - R4).

    A reading with no sentence beside it is a number the reader has to take
    on trust, so ``means`` is required at every ``add()`` call site rather
    than optional. The sentence is a property of the CHECK, not of this
    site's value - which is what lets one wording serve every site, and is
    also why a value appearing inside it would be a bug.
    """
    p = _assemble(session)
    missing = [f.label for f in p.site_facts if not f.means]
    assert missing == [], f"checks with no what-it-means sentence: {missing}"
    for f in p.site_facts:
        assert f.means is not None
        assert f.means.endswith("."), f.label
        assert f.value not in f.means, f"{f.label} explains this site, not the check"
    # One wording per check, whichever branch produced the row: the road
    # fact is assembled two different ways and must not explain itself twice.
    road = next(f for f in p.site_facts if f.label == "Road frontage")
    assert road.means == ROAD_FRONTAGE_MEANS


def test_plain_money_reconciles_with_the_case_it_sits_beside(session: Session) -> None:
    """Section 02's plain figures and section 05's finance figures describe
    the same case (Track B - R6). If they can drift, the document argues
    with itself four pages apart - the exact failure R5 was asked to remove.
    """
    p = _assemble(session)
    for s in p.financials.scenarios:
        assert s.plain is not None, s.label
        m = s.plain
        # What comes in, minus what goes out, is what is left. Exactly.
        assert m.revenue_paise_year - m.running_cost_paise_year - m.fixed_cost_paise_year == (
            m.cash_paise_year
        )
        # Year 0 is the build and is always negative; the running total then
        # moves by the year's own cashflow, never by a re-derived average.
        assert len(m.cumulative_paise) == RoiInputs.horizon_years + 1
        assert m.cumulative_paise[0] == -p.financials.capex_paise
        assert m.cumulative_paise[-1] - m.cumulative_paise[-2] == m.cash_paise_year
        # A case that pays back inside the horizon must have a year where the
        # running total actually turns, and one that does not must not.
        turns = any(c >= 0 for c in m.cumulative_paise)
        assert turns is (s.payback_years is not None), s.label


def test_the_ramp_is_visible_rather_than_averaged_away(session: Session) -> None:
    """The annual figures are the STEADY year, and the cumulative row is the
    ramp. Both are true; printing only the first would not be."""
    p = _assemble(session)
    central = next(s for s in p.financials.scenarios if s.label.startswith("P50"))
    assert central.plain is not None
    steps = [
        b - a
        for a, b in zip(
            central.plain.cumulative_paise[1:],
            central.plain.cumulative_paise[2:],
            strict=False,  # offset slices: the last year has no successor
        )
    ]
    assert steps == sorted(steps), "demand ramps, so each year's cash is at least the last"
    assert steps[0] < steps[-1], "a flat series here means the ramp was lost"
    assert steps[-1] == central.plain.cash_paise_year


def test_the_working_adds_up_to_the_headline_it_explains(session: Session) -> None:
    """Section 05 prints three sums. Each has to reach the number printed
    beside it, or the section is showing working for a different report."""
    p = _assemble(session)
    f = p.financials
    assert f.capex_lines is not None
    assert sum(line.paise for line in f.capex_lines) == f.capex_paise

    assert f.unit_economics is not None
    u = f.unit_economics
    assert u.selling_paise_kwh == f.selling_price_paise_kwh
    assert u.selling_paise_kwh - sum(d.paise for d in u.deductions) == u.margin_paise_kwh

    assert f.fixed_costs is not None
    fc = f.fixed_costs
    assert sum(line.paise for line in fc.lines) == fc.total_paise_year
    assert fc.total_paise_year == next(
        s.plain.fixed_cost_paise_year for s in f.scenarios if s.plain is not None
    )
    # A reader who divides the printed bills by the printed margin must land
    # on the printed breakeven. Not to the kWh - the margin is shown rounded
    # to whole paise, which moves the quotient by about 0.03% - but to every
    # digit the document actually prints: the daily figure and the
    # utilisation. If that ever stops holding, section 05 is showing working
    # for a threshold section 03 does not have.
    by_hand = fc.total_paise_year / u.margin_paise_kwh
    assert round(by_hand / 365) == round(p.breakeven.kwh_day)
    assert round(by_hand / p.breakeven.kwh_year * p.breakeven.utilisation, 4) == round(
        p.breakeven.utilisation, 4
    )


def test_the_two_thresholds_differ_by_exactly_the_term_section_09_prints(
    session: Session,
) -> None:
    """Track B - R7. Section 09 prints both divisions side by side and says
    'one extra term is the whole difference between the two rules'. That
    sentence is only worth printing if it is true of the payload rather than
    of the prose, so this is the same arithmetic the reader is invited to do.

    Held to the precision the document prints - the daily figure - for the
    reason R6 recorded: the margin is shown rounded to whole paise, which
    moves the quotient by a fraction of a unit.
    """
    p = _assemble(session)
    u = p.financials.unit_economics
    fc = p.financials.fixed_costs
    assert u is not None and fc is not None
    recovery = p.breakeven.full_cost_recovery_paise_year
    assert recovery is not None
    assert p.breakeven.full_cost_kwh_year is not None

    bills_line = fc.total_paise_year / u.margin_paise_kwh
    build_line = (fc.total_paise_year + recovery) / u.margin_paise_kwh
    assert round(bills_line / 365) == round(p.breakeven.kwh_day)
    assert round(build_line / 365) == round(p.breakeven.full_cost_kwh_day or 0)
    # The harder line is harder, and the gap IS the recovery figure.
    assert build_line > bills_line
    assert round(build_line - bills_line) == round(recovery / u.margin_paise_kwh)


def test_the_recovery_figure_is_absent_only_when_the_line_it_explains_is(
    session: Session,
) -> None:
    """Section 09 prints the formula or omits it whole. A payload carrying
    half of one would invite a reader into arithmetic they cannot finish."""
    p = _assemble(session)
    assert (p.breakeven.full_cost_recovery_paise_year is None) == (
        p.breakeven.full_cost_kwh_year is None
    )


def test_the_headline_operators_cash_is_the_cash_section_02_prints(session: Session) -> None:
    """Section 06's money column and section 02's headline are the same run.

    Both come from the steady year of the same cashflow, so the row for the
    operator section 02 is about must carry section 02's own rupees. If the
    two ever part company the document is quoting one site's cash under two
    operators' names, four pages apart (Track B - R9).
    """
    p = _assemble(session)
    headline = next(c for c in p.cpo if c.operator == "chargeMOD")
    central = next(s for s in p.financials.scenarios if s.label.startswith("P50"))
    assert central.plain is not None
    assert headline.cash_p50_paise_year == central.plain.cash_paise_year


def test_an_operator_that_takes_more_leaves_less(session: Session) -> None:
    """Not a ranking claim - an arithmetic one. Section 06 prints the terms
    and the cash side by side, so the cash has to move the way the terms say
    it does or the reader can see the contradiction without leaving the row."""
    p = _assemble(session)
    for a in p.cpo:
        for b in p.cpo:
            dearer = (
                a.revenue_share_pct >= b.revenue_share_pct
                and a.platform_fee_paise_year >= b.platform_fee_paise_year
                and (
                    a.revenue_share_pct > b.revenue_share_pct
                    or a.platform_fee_paise_year > b.platform_fee_paise_year
                )
            )
            if not dearer:
                continue
            assert a.cash_p50_paise_year is not None
            assert b.cash_p50_paise_year is not None
            assert a.cash_p50_paise_year < b.cash_p50_paise_year
            assert a.margin_of_safety_pp < b.margin_of_safety_pp


def test_signed_service_terms_are_absent_rather_than_invented(session: Session) -> None:
    """Repair target and tie-in period wait on cpo_terms (PLAN 2.3).

    Every row carries None until that table exists, and section 06 drops both
    columns rather than printing one dash per operator. The day the columns
    start rendering is the day this test starts failing, which is the point.
    """
    p = _assemble(session)
    assert p.cpo
    assert all(c.repair_hours is None for c in p.cpo)
    assert all(c.tie_in_years is None for c in p.cpo)


def test_the_engines_own_assumptions_reach_the_page(session: Session) -> None:
    """engine.py has written every default into RoiResult.assumptions since it
    was built, and its docstring said 'the report's assumption ledger consumes
    it verbatim'. That was untrue until R10: two ledgers existed and only the
    hand-written one was printed, so only the generated one could go stale.
    """
    p = _assemble(session)
    assert p.model_assumptions
    # Verbatim, from the CENTRAL run - the one every headline comes from.
    assert any(a.startswith("economics_version ") for a in p.model_assumptions)
    assert any("discount rate" in a for a in p.model_assumptions)
    assert any("utilisation ceiling" in a for a in p.model_assumptions)


def test_the_two_ledgers_do_not_repeat_each_other(session: Session) -> None:
    """One page, one statement (Track B - R6). The model's choices and the
    provenance of each input are different things; if the same fact lands in
    both, section 10 is teaching the reader its halves are interchangeable."""
    p = _assemble(session)
    items = {row.item.lower() for row in p.ledger}
    assert "discount rate" not in items
    assert "horizon" not in items
    assert any("discount rate" in a for a in p.model_assumptions)


def test_the_ledger_carries_the_recovery_figure_section_09_prints(session: Session) -> None:
    """R7 published the annual build-cost recovery so section 09 could print
    the full-cost formula term by term. R10 gives it a home in the assumption
    ledger as well - and it has to be the SAME number, or the document offers
    two answers to what the build costs per year."""
    p = _assemble(session)
    recovery = p.breakeven.full_cost_recovery_paise_year
    assert recovery is not None
    line = next(a for a in p.model_assumptions if a.startswith("full-cost breakeven"))
    assert f"{recovery / 100_000_00:.2f} lakh a year" in line


def test_a_report_knows_the_day_it_was_made(session: Session) -> None:
    """Until R10 the document carried no date anywhere - not on the cover, not
    in the chrome. Section 11 exists so an old report can defend itself, and a
    document with no date on it cannot. It is baked in at assembly because the
    payload is served verbatim (Rule 9); read at render time it would be the
    date of the reading."""
    p = _assemble(session)
    assert p.generated_at == dt.date.today().isoformat()


def test_todays_assembler_leaves_only_the_gaps_we_know_about(session: Session) -> None:
    """The console's coverage readout is only worth reading if a NEW gap is
    news (Track B - R12).

    ``domain/report/coverage.py`` reports what each section cannot print from
    a payload. Three sections have documented gaps and are excluded here -
    04 is short of the other 18 site checks, 06 waits on `cpo_terms`, 07 on
    the poller. Any OTHER section reporting a gap means the assembler quietly
    stopped filling something, which is exactly the failure the readout
    exists to make visible and would otherwise show up as a shorter document
    nobody could account for.
    """
    from app.domain.report.coverage import coverage

    payload = _assemble(session).model_dump()
    gaps = {s.id: s.dropped for s in coverage(payload) if s.dropped}
    unexplained = {k: v for k, v in gaps.items() if k not in {"site", "operators", "competitors"}}
    assert unexplained == {}, f"the assembler stopped filling something: {unexplained}"
