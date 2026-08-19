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
from app.domain.demand.synthetic import load_weights
from app.domain.report.assemble import (
    CompetitorContext,
    CpoOption,
    NearbyCompetitor,
    ReportSpec,
    assemble_report,
)
from app.domain.report.payload import ReportPayload
from app.domain.report.store import get_payload, save_report
from app.domain.roi.engine import Capex, CpoTerms
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
ROADS = RoadFeatures("trunk", "NH 66", 40.0, True, 3)
POIS = PoiGravity(
    counts={500: {"food": 2}, 1000: {"food": 4}, 3000: {"food": 9}},
    dwell_anchor_score=5.5,
    dwell_anchors=("Technopark Mall",),
)


def _assemble(session: Session, **overrides: object) -> ReportPayload:
    kwargs: dict[str, object] = {"roads": ROADS, "pois": POIS, "competitors": COMPETITORS}
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
    irrs = [c.irr_p50_pct for c in p.cpo]
    assert irrs == sorted(irrs, reverse=True)
    assert any(c.ours for c in p.cpo)


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
