"""Assembling the 7-section payload - PART 5's composer.

One function, ``assemble_report``, pulls every layer together in the order the
architecture draws it (OVERVIEW.md §2):

    context (VAHAN, competitors, roads, POI)  ->  demand (synthetic_v0 band)
        ->  roi_engine (every financial number)  ->  the payload

Division of honesty, enforced here because this is where the layers meet:

* **Money comes only from ``compute_roi``** (AGENTS.md rule 1). This module
  never does financial arithmetic beyond subtracting two utilisations for the
  margin of safety - which is a difference of fractions, not money.
* **The demand band is stamped with its model_version** and flows to the
  ledger and the hero as modelled-not-measured while that model is synthetic.
* **A context layer that could not be fetched degrades to an unverified fact**
  ("OSM layer pending"), never to an invented number.

Every context slice arrives through a small dataclass that a caller may inject
- the demo generator injects live fetches, tests inject fixtures, and neither
path is special. The session is used only for VAHAN, competitor and tariff
reads; Overpass fetching happens in the *caller* so this function stays
deterministic for a given set of inputs.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.domain.context.poi import PoiGravity
from app.domain.context.roads import MAJOR_CLASSES, RoadFeatures
from app.domain.cpo.identity import canonical_operator
from app.domain.cpo.presence import OperatorPresence, operator_presence
from app.domain.demand.synthetic import (
    SyntheticInputs,
    SyntheticPrediction,
    SyntheticWeights,
    predict,
)
from app.domain.public_reference import PublicReference
from app.domain.report.payload import (
    AnchorNote,
    BreakevenPayload,
    CompetitorRow,
    CompetitorsPayload,
    CostLine,
    CpoRow,
    DemandPayload,
    Direction,
    FinancialsPayload,
    FixedCosts,
    HardwarePayload,
    LedgerRow,
    PlainMoney,
    PriceSensitivityPoint,
    ProvenanceRow,
    ReportPayload,
    SanctionedLoad,
    Scenario,
    SiteFact,
    SitePayload,
    UnitEconomics,
    UtilisationBand,
    VerdictPayload,
)
from app.domain.report.public_context import enrich_public_context, load_report_reference
from app.domain.roi.engine import (
    Capex,
    ChargerSpec,
    CpoTerms,
    FleetAnchor,
    RoiInputs,
    RoiResult,
    SiteOpex,
    TariffTerms,
    compute_roi,
)
from app.domain.tariffs.select import effective_on
from app.domain.vahan.parse import TWO_WHEELER, annual_growth
from app.models.tariffs import ElectricityTariff
from app.models.vahan import VahanEvRegistration

TOTAL_CLASS = "TOTAL"
POWER_FACTOR = 0.9
DC_FAST_KW = 50.0


# ---------------------------------------------------------------------------
# The spec - what the caller decides; everything else is looked up or derived
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CpoOption:
    operator: str
    ours: bool
    terms: CpoTerms
    ocpi_roaming: bool


@dataclass(frozen=True)
class ReportSpec:
    report_id: str
    demo: bool
    name: str
    line: str
    district_name: str
    lgd_district_code: int
    lgd_state_code: int
    lat: float
    lng: float
    archetype: str
    archetype_hand_assigned: bool

    connectors: int
    rated_kw_each: float
    selling_paise_per_kwh: int
    capex: Capex
    rent_paise_per_month: int

    anchor_kwh_year: float
    anchor_paise_per_kwh: int

    #: First entry is the headline arrangement the hero economics assume -
    #: stated in the ledger, because it is a choice, not a fact.
    cpo_options: tuple[CpoOption, ...] = field(default_factory=tuple)
    data_tier: int = 1


# ---------------------------------------------------------------------------
# Context slices - fetched here from the DB, injectable by tests
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VahanContext:
    ev_latest_year: int
    latest_year: str
    growth: float | None
    two_wheeler_share: float | None
    snapshot_date: dt.date


@dataclass(frozen=True)
class NearbyCompetitor:
    name: str
    operator: str
    distance_m: int
    max_power_kw: float
    points: int


@dataclass(frozen=True)
class CompetitorContext:
    within_3km: int
    within_5km: int
    dc_fast_within_3km: int
    nearest: tuple[NearbyCompetitor, ...]
    source: str


def district_vahan(session: Session, lgd_district_code: int) -> VahanContext | None:
    """The district's EV story from the latest snapshot: level, growth, mix."""
    latest = session.execute(
        select(func.max(VahanEvRegistration.snapshot_date)).where(
            VahanEvRegistration.lgd_district_code == lgd_district_code
        )
    ).scalar_one_or_none()
    if latest is None:
        return None

    rows = session.execute(
        select(
            VahanEvRegistration.period,
            VahanEvRegistration.vehicle_class,
            func.sum(VahanEvRegistration.count),
        )
        .where(
            VahanEvRegistration.lgd_district_code == lgd_district_code,
            VahanEvRegistration.snapshot_date == latest,
        )
        .group_by(VahanEvRegistration.period, VahanEvRegistration.vehicle_class)
    ).all()

    totals_by_year: dict[str, int] = {}
    class_latest: dict[str, int] = {}
    years = sorted({str(p) for p, _, _ in rows if str(p).isdigit()})
    if not years:
        return None
    latest_year = years[-1]

    for period, vclass, count in rows:
        period_s, count_i = str(period), int(count or 0)
        if vclass == TOTAL_CLASS and period_s.isdigit():
            totals_by_year[period_s] = totals_by_year.get(period_s, 0) + count_i
        elif vclass != TOTAL_CLASS and period_s == latest_year:
            class_latest[str(vclass)] = class_latest.get(str(vclass), 0) + count_i

    class_sum = sum(class_latest.values())
    two_w = sum(c for k, c in class_latest.items() if k in TWO_WHEELER)
    return VahanContext(
        ev_latest_year=totals_by_year.get(latest_year, 0),
        latest_year=latest_year,
        growth=annual_growth(totals_by_year),
        two_wheeler_share=(two_w / class_sum) if class_sum else None,
        snapshot_date=latest,
    )


_NEAR_SQL = text("""
    SELECT name, operator, max_power_kw, number_of_points,
           ST_Distance(geom::geography,
                       ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS m
    FROM competitor_stations
    WHERE ST_DWithin(geom::geography,
                     ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, 5000)
    ORDER BY m
""")


def competitors_near(session: Session, lat: float, lng: float) -> CompetitorContext:
    """Inventory within 5 km, on ``::geography`` per the geometry convention."""
    rows = session.execute(_NEAR_SQL, {"lat": lat, "lng": lng}).all()
    nearest = tuple(
        NearbyCompetitor(
            name=str(name or "(unnamed)"),
            operator=str(operator or "(unknown)"),
            distance_m=round(float(m)),
            max_power_kw=float(kw or 0),
            points=int(points or 0),
        )
        for name, operator, kw, points, m in rows
    )
    return CompetitorContext(
        within_3km=sum(1 for c in nearest if c.distance_m <= 3000),
        within_5km=len(nearest),
        dc_fast_within_3km=sum(
            1 for c in nearest if c.distance_m <= 3000 and c.max_power_kw >= DC_FAST_KW
        ),
        nearest=nearest[:5],
        source="competitor_stations · OCM + GoEC + Zeon",
    )


def state_ev_tariff(session: Session, lgd_state_code: int, on: dt.date) -> ElectricityTariff | None:
    """The EV-specific tariff row governing ``on`` - PART 3.1's selection."""
    rows = (
        session.execute(
            select(ElectricityTariff).where(
                ElectricityTariff.lgd_state_code == lgd_state_code,
                ElectricityTariff.ev_specific.is_(True),
            )
        )
        .scalars()
        .all()
    )
    return effective_on(rows, on)


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssembledReport:
    payload: ReportPayload
    #: What the caller writes to ``predictions`` (Rule 5 - never skipped).
    prediction: SyntheticPrediction


def _utilisation(kwh_per_connector_day: float, rated_kw: float) -> float:
    return kwh_per_connector_day / (rated_kw * 24.0)


def _presence_note(confidence: str, seen: OperatorPresence | None) -> str:
    """One plain sentence about what this operator's own stations do here.

    Deliberately not a direction marker. ``favours``/``against`` on an
    operator would need thresholds, and thresholds shown after the data are
    the thing report section 03 exists to forbid. Until those are set and
    printed, this states the mechanism and lets the reader weigh it.
    """
    if confidence == "not_a_network":
        return (
            "You would run the station yourself, so no operator's app is dividing "
            "these drivers between your plug and another - and none is bringing "
            "them either."
        )
    if seen is None:
        return (
            "This name is not matched to a network in our charger inventory, so "
            "its own footprint here is unknown - which is not the same as none."
        )
    if seen.own_within_3km == 0:
        split = (
            "No station of their own within 3 km, so nothing of theirs is "
            "dividing these drivers with you."
        )
    else:
        plural = "s" if seen.own_within_3km != 1 else ""
        split = (
            f"{seen.own_within_3km} station{plural} of their own within 3 km "
            f"({seen.own_within_10km} within 10 km) - their app can send the "
            "same drivers there instead of to you."
        )
    # Reach is the other half of the same question: an operator with no local
    # footprint has no split to worry about AND no audience to bring, which is
    # not the good news the first sentence alone would read as.
    if seen.stations_state == 0:
        reach = (
            "They run nothing else in this state - no local audience already "
            "carrying their app, and no engineer near this site."
        )
    else:
        reach = f"{seen.stations_district} in this district and {seen.stations_state} in the state."
    return f"{split} {reach}"


def _roi(
    spec: ReportSpec,
    tariff: TariffTerms,
    sanctioned_kva: float,
    ramp_per_connector: tuple[float, ...],
    cpo: CpoTerms,
    anchor: FleetAnchor | None = None,
) -> RoiResult:
    return compute_roi(
        RoiInputs(
            chargers=(ChargerSpec(kw=spec.rated_kw_each, count=spec.connectors),),
            tariff=tariff,
            capex=spec.capex,
            opex=SiteOpex(
                sanctioned_kva=sanctioned_kva, rent_paise_per_month=spec.rent_paise_per_month
            ),
            selling_paise_per_kwh=spec.selling_paise_per_kwh,
            kwh_by_year=tuple(k * spec.connectors for k in ramp_per_connector),
            cpo=cpo,
            anchor=anchor,
        )
    )


def _plain(run: RoiResult) -> PlainMoney:
    """One case in money rather than in finance (Track B - R6).

    The annual figures are the STEADY year - the last row of the ramp, the
    same year ``Scenario.kwh_year`` reports - so section 02's "cash left each
    month" is not year 1's smaller number wearing year 10's label. The ramp
    is not hidden by that choice: ``cumulative_paise`` is the engine's own
    year-by-year running total, and section 05 prints every row of it.
    """
    steady = run.cashflow[-1]
    return PlainMoney(
        revenue_paise_year=steady.revenue_paise,
        running_cost_paise_year=steady.energy_cost_paise,
        fixed_cost_paise_year=steady.fixed_cost_paise,
        cash_paise_year=steady.cashflow_paise,
        revenue_paise_month=round(steady.revenue_paise / 12),
        cash_paise_month=round(steady.cashflow_paise / 12),
        cumulative_paise=[row.cumulative_paise for row in run.cashflow],
    )


def _working(run: RoiResult) -> tuple[list[CostLine], UnitEconomics, FixedCosts]:
    """The three breakdowns section 05 shows its working from. Every one of
    them is the engine's, decomposed there so that exactly one place knows
    the arithmetic - and each sums to a headline printed beside it."""
    return (
        [CostLine(label=line.name, paise=line.paise) for line in run.capex_lines],
        UnitEconomics(
            selling_paise_kwh=run.unit_economics.selling_paise,
            deductions=[
                CostLine(label=d.name, paise=d.paise) for d in run.unit_economics.deductions
            ],
            margin_paise_kwh=run.unit_economics.margin_paise,
        ),
        FixedCosts(
            lines=[CostLine(label=line.name, paise=line.paise) for line in run.fixed_cost_lines],
            total_paise_year=run.annual_fixed_paise,
            total_paise_month=round(run.annual_fixed_paise / 12),
        ),
    )


def assemble_report(
    session: Session,
    spec: ReportSpec,
    weights: SyntheticWeights,
    *,
    roads: RoadFeatures | None,
    pois: PoiGravity | None,
    vahan: VahanContext | None = None,
    competitors: CompetitorContext | None = None,
    presence: dict[str, OperatorPresence] | None = None,
    on: dt.date | None = None,
    public_reference: PublicReference | None = None,
) -> AssembledReport:
    """Compose the payload. Raises when a layer the report cannot exist
    without (VAHAN, tariff) is missing - a report with no demand data and no
    tariff is not degraded, it is impossible."""
    vahan = vahan if vahan is not None else district_vahan(session, spec.lgd_district_code)
    if vahan is None:
        raise ValueError(f"no VAHAN data for district {spec.lgd_district_code}")
    competitors = (
        competitors if competitors is not None else competitors_near(session, spec.lat, spec.lng)
    )
    # Same shape as ``competitors``: PostGIS in production, injected by tests
    # that run on SQLite. An empty mapping is a legitimate answer - it means no
    # network we can name has a station in this state.
    presence = (
        presence
        if presence is not None
        else operator_presence(
            session,
            lat=spec.lat,
            lng=spec.lng,
            lgd_district_code=spec.lgd_district_code,
            lgd_state_code=spec.lgd_state_code,
        )
    )
    on = on or vahan.snapshot_date

    tariff_row = state_ev_tariff(session, spec.lgd_state_code, on)
    if tariff_row is None:
        raise ValueError(f"no EV tariff row for state {spec.lgd_state_code} on {on}")
    tariff = TariffTerms(
        energy_paise_per_kwh=tariff_row.energy_paise_per_kwh,
        demand_paise_per_kva_month=tariff_row.demand_paise_per_kva_month,
        fixed_paise_per_month=tariff_row.fixed_paise_per_month,
        duty_pct=tariff_row.duty_bp / 10_000,
    )

    # --- demand: the one uncertain number, quarantined --------------------
    on_major = (
        None
        if roads is None
        else (
            roads.nearest_class in MAJOR_CLASSES[:3]
            and roads.distance_m is not None
            and roads.distance_m <= 100
        )
    )
    prediction = predict(
        SyntheticInputs(
            archetype=spec.archetype,
            rated_kw_per_connector=spec.rated_kw_each,
            district_ev_total=vahan.ev_latest_year,
            district_growth=vahan.growth,
            competitors_within_3km=competitors.within_3km,
            dc_fast_within_3km=competitors.dc_fast_within_3km,
            dwell_anchor_score=None if pois is None else pois.dwell_anchor_score,
            on_major_road=on_major,
        ),
        weights,
    )

    # --- economics: one engine, run per scenario and per operator ---------
    headline_cpo = (
        spec.cpo_options[0]
        if spec.cpo_options
        else CpoOption("Self-operate", False, CpoTerms(), False)
    )
    full_kva = spec.connectors * spec.rated_kw_each / POWER_FACTOR
    base = _roi(spec, tariff, full_kva, prediction.kwh_year_ramp_p50, headline_cpo.terms)
    managed = next(o for o in base.sanctioned_load_options if o.name.startswith("managed"))
    buffered = next(o for o in base.sanctioned_load_options if o.name.startswith("battery"))

    # The report's economics assume the kVA we would actually advise.
    sanctioned_kva = managed.kva
    ramps = {
        "P10 · downside": prediction.kwh_year_ramp_p10,
        "P50 · central": prediction.kwh_year_ramp_p50,
        "P90 · upside": prediction.kwh_year_ramp_p90,
    }
    runs = {
        label: _roi(spec, tariff, sanctioned_kva, ramp, headline_cpo.terms)
        for label, ramp in ramps.items()
    }
    p50_run = runs["P50 · central"]
    if p50_run.breakeven_utilisation is None:
        raise ValueError("negative margin at the assumed price - " + p50_run.assumptions[-1])

    util = {
        "P10 · downside": _utilisation(prediction.kwh_per_connector_day_p10, spec.rated_kw_each),
        "P50 · central": _utilisation(prediction.kwh_per_connector_day_p50, spec.rated_kw_each),
        "P90 · upside": _utilisation(prediction.kwh_per_connector_day_p90, spec.rated_kw_each),
    }
    margin_pp = round((util["P10 · downside"] - p50_run.breakeven_utilisation) * 100, 1)

    anchor_run = _roi(
        spec,
        tariff,
        sanctioned_kva,
        prediction.kwh_year_ramp_p50,
        headline_cpo.terms,
        anchor=FleetAnchor(
            min_kwh_per_year=spec.anchor_kwh_year, paise_per_kwh=spec.anchor_paise_per_kwh
        ),
    )

    cpo_rows: list[CpoRow] = []
    for option in spec.cpo_options:
        run = _roi(spec, tariff, sanctioned_kva, prediction.kwh_year_ramp_p50, option.terms)
        if run.breakeven_utilisation is None:
            continue
        match = canonical_operator(option.operator)
        seen = presence.get(match.canonical) if match.canonical is not None else None
        cpo_rows.append(
            CpoRow(
                operator=option.operator,
                ours=option.ours,
                revenue_share_pct=round(option.terms.revenue_share_pct * 100, 1),
                platform_fee_paise_year=option.terms.network_fee_paise_per_month * 12,
                irr_p50_pct=None if run.irr_pct is None else round(run.irr_pct * 100, 1),
                margin_of_safety_pp=round(
                    (util["P10 · downside"] - run.breakeven_utilisation) * 100, 1
                ),
                # The steady year, exactly as ``_plain`` takes it - so the row
                # for the headline operator carries the same rupees section 02
                # does, and the rest are that number under other terms.
                cash_p50_paise_year=run.cashflow[-1].cashflow_paise,
                uptime="not measured",
                ocpi_roaming=option.ocpi_roaming,
                stations_district=None if seen is None else seen.stations_district,
                stations_state=None if seen is None else seen.stations_state,
                own_within_3km=None if seen is None else seen.own_within_3km,
                own_within_10km=None if seen is None else seen.own_within_10km,
                presence_note=_presence_note(match.confidence, seen),
                # repair_hours and tie_in_years stay None until cpo_terms
                # exists (PLAN 2.3). They are signed terms, so there is no
                # default worth inventing: section 06 drops both columns.
            )
        )
    # No return sorts below any return; among those, the smaller loss first.
    cpo_rows.sort(
        key=lambda r: (r.irr_p50_pct is not None, r.irr_p50_pct or 0.0, r.margin_of_safety_pp),
        reverse=True,
    )

    # --- verdict: from P10, stated as an argument -------------------------
    if margin_pp >= 0:
        verdict_value, verdict_reason = (
            "build",
            (
                "Even the downside case clears breakeven by "
                f"{margin_pp:+.1f} points. The economics hold without heroic assumptions."
            ),
        )
    elif util["P50 · central"] >= p50_run.breakeven_utilisation:
        verdict_value, verdict_reason = (
            "conditional",
            (
                "The prediction band straddles the breakeven rule: the downside case (P10) sits "
                f"{abs(margin_pp):.1f} points under it"
                + (
                    f" in a corridor that already has {competitors.within_3km} competing stations "
                    "within 3 km"
                    if competitors.within_3km
                    else ""
                )
                + ". A fleet or campus charging contract is what moves the downside, "
                "not walk-in traffic."
            ),
        )
    else:
        verdict_value, verdict_reason = (
            "dont",
            (
                "Even the central case falls short of breakeven by "
                f"{(p50_run.breakeven_utilisation - util['P50 · central']) * 100:.1f} points. "
                "At this cost structure and price the site does not pay for itself."
            ),
        )

    # --- section slices ---------------------------------------------------
    growth_pct = None if vahan.growth is None else round(vahan.growth * 100, 1)
    site_facts = _site_facts(
        spec, roads, pois, vahan, competitors, growth_pct, tariff_row, full_kva, managed.kva
    )
    # Capex, the fixed bills and the per-unit margin are identical in all
    # three runs - only the demand curve differs - so the working comes off
    # the central case rather than being assembled three times.
    capex_working, unit_working, fixed_working = _working(p50_run)

    breakeven_day = p50_run.breakeven_kwh_year / 365.0 if p50_run.breakeven_kwh_year else 0.0
    full_cost_year = p50_run.full_cost_breakeven_kwh_year

    payload = ReportPayload(
        report_id=spec.report_id,
        demo=spec.demo,
        site=SitePayload(
            name=spec.name,
            line=spec.line,
            district=spec.district_name,
            lgd_district_code=spec.lgd_district_code,
            lat=spec.lat,
            lng=spec.lng,
            archetype=spec.archetype,
            data_tier=spec.data_tier,  # type: ignore[arg-type]
        ),
        hardware=HardwarePayload(
            connectors=spec.connectors,
            rated_kw_each=spec.rated_kw_each,
            sanctioned_kva_full=round(full_kva),
        ),
        breakeven=BreakevenPayload(
            utilisation=round(p50_run.breakeven_utilisation, 4),
            kwh_year=round(p50_run.breakeven_kwh_year or 0),
            kwh_day=round(breakeven_day),
            # None, not zero: a site with no breakeven at any volume has no
            # full-cost breakeven either, and 0 would read as "none needed".
            full_cost_utilisation=(
                None
                if p50_run.full_cost_breakeven_utilisation is None
                else round(p50_run.full_cost_breakeven_utilisation, 4)
            ),
            full_cost_kwh_year=None if full_cost_year is None else round(full_cost_year),
            full_cost_kwh_day=None if full_cost_year is None else round(full_cost_year / 365.0),
            # Carried whenever the line it belongs to is, so section 09 never
            # prints half a formula.
            full_cost_recovery_paise_year=(
                None if full_cost_year is None else p50_run.full_cost_build_recovery_paise_year
            ),
        ),
        predicted=UtilisationBand(
            p10=round(util["P10 · downside"], 4),
            p50=round(util["P50 · central"], 4),
            p90=round(util["P90 · upside"], 4),
            model_version=prediction.model_version,
            modelled_not_measured=True,
        ),
        margin_of_safety_pp=margin_pp,
        verdict=VerdictPayload(value=verdict_value, reason=verdict_reason),
        demand=DemandPayload(
            district_ev_2025=vahan.ev_latest_year,
            district_growth_yoy_pct=growth_pct or 0.0,
            two_wheeler_share_pct=round((vahan.two_wheeler_share or 0) * 100),
            vahan_snapshot=vahan.snapshot_date.isoformat(),
        ),
        site_facts=site_facts,
        competitors=CompetitorsPayload(
            within_3km=competitors.within_3km,
            nearest=[
                CompetitorRow(
                    name=c.name,
                    operator=c.operator,
                    distance_m=c.distance_m,
                    max_power_kw=c.max_power_kw,
                    points=c.points,
                )
                for c in competitors.nearest
            ],
            source=competitors.source,
            within_5km=competitors.within_5km,
            dc_fast_within_3km=competitors.dc_fast_within_3km,
        ),
        financials=FinancialsPayload(
            capex_paise=spec.capex.net_paise,
            selling_price_paise_kwh=spec.selling_paise_per_kwh,
            energy_tariff_paise_kwh=tariff.energy_paise_per_kwh,
            scenarios=[
                Scenario(
                    label=label,
                    utilisation=round(util[label], 4),
                    kwh_year=round(run.cashflow[-1].kwh),
                    npv_paise=run.npv_paise,
                    irr_pct=None if run.irr_pct is None else round(run.irr_pct * 100, 1),
                    payback_years=run.payback_years,
                    plain=_plain(run),
                )
                for label, run in runs.items()
            ],
            anchor_note=AnchorNote(
                kwh_year=spec.anchor_kwh_year,
                npv_paise=anchor_run.npv_paise,
                irr_pct=round((anchor_run.irr_pct or 0) * 100, 1),
            ),
            sanctioned_load=SanctionedLoad(
                full_kva=round(full_kva),
                recommended_kva=managed.kva,
                recommended_label="managed-peak",
                saving_paise_year=managed.saving_vs_input_paise_per_year,
                buffered_kva=buffered.kva,
            ),
            price_sensitivity=[
                PriceSensitivityPoint(
                    price_paise_kwh=p.selling_paise_per_kwh,
                    breakeven_utilisation=round(p.breakeven_utilisation, 4),
                )
                for p in p50_run.price_sensitivity
                if p.breakeven_utilisation is not None
                and p.selling_paise_per_kwh
                in (
                    spec.selling_paise_per_kwh - 200,
                    spec.selling_paise_per_kwh,
                    spec.selling_paise_per_kwh + 200,
                )
            ],
            capex_lines=capex_working,
            unit_economics=unit_working,
            fixed_costs=fixed_working,
        ),
        cpo=cpo_rows,
        ledger=_ledger(
            spec, prediction, tariff_row, roads, vahan, competitors, managed.kva, cpo_rows
        ),
        # The engine's own ledger, verbatim - from the CENTRAL run, which is
        # the one every headline on the document comes from. The three runs
        # differ only in volume, and volume is not an assumption.
        model_assumptions=list(p50_run.assumptions),
        provenance=_provenance(spec, prediction, p50_run, vahan, competitors, tariff_row),
        # Assembly time, not render time: the payload is the data of record
        # and is served verbatim, so a date read off the row later would be
        # the date of the READING, not of the report.
        generated_at=dt.date.today().isoformat(),
    )
    reference = public_reference if public_reference is not None else load_report_reference()
    payload = enrich_public_context(session, payload, reference)
    return AssembledReport(payload=payload, prediction=prediction)


# ---------------------------------------------------------------------------
# Site factors - every fact carries a heading and a direction marker
# ---------------------------------------------------------------------------

#: The fixed thresholds behind each direction marker. They are the same for
#: every site and were set before any pin was placed: a reader who disagrees
#: with one can see exactly which row it moved. They are heuristics about what
#: helps a charger - the VERDICT rule is P10 against breakeven, above, and
#: these never feed it.
MAJOR_ROAD_NEAR_M = 100
ROAD_FAR_M = 300
EV_STOCK_STRONG = 10_000
EV_STOCK_WEAK = 3_000
GROWTH_STRONG_PCT = 20.0
GROWTH_WEAK_PCT = 5.0
TWO_WHEELER_HEAVY = 0.6
TARIFF_CHEAP_PAISE = 600
TARIFF_DEAR_PAISE = 800
DEMAND_CHARGE_LOW_PAISE = 15_000
DEMAND_CHARGE_HIGH_PAISE = 30_000
NEAREST_CROWDED_M = 500
NEAREST_CLEAR_M = 2_000
STATIONS_3KM_CROWDED = 3
STATIONS_5KM_CROWDED = 5
DC_FAST_3KM_CROWDED = 2

ACCESS = "Access and geometry"
DEMAND = "Demand"
POWER = "Power and tariff"
#: The fifth group. Section 04's chapter map has always expected it; the
#: assembler had never emitted a single row into it (Track B - R13).
AMENITY = "Site and amenities"
COMPETITION = "Competition"

#: Sources for checks that have no fetch behind them yet. Each names WHAT
#: would answer it, never a vague "pending" - the difference between a gap
#: somebody can close and a gap somebody has to investigate first.
#:
#: Every check carrying one of these is `unverified=True`, so section 04
#: prints "? UNVERIFIED" in place of a direction and the assumptions ledger
#: carries it as unconfirmed. That is the whole reason the fourth state
#: exists: a placeholder that looks like a reading is worse than no row.
SRC_SURVEY = "site survey pending"
SRC_IMAGERY = "measured from imagery - not yet automated"
SRC_TRAFFIC = "no free AADT source for India - proxied, not counted"
SRC_DISCOM = "discom confirmation pending"
SRC_CUSTOMER = "customer to supply"
SRC_ARCHETYPE = "archetype default - not this site"


def _band(value: float, low: float, high: float, *, high_is_good: bool) -> Direction:
    """Three-way marker from two thresholds. ``low`` and ``high`` bound the
    neutral middle; which end is favourable depends on the fact."""
    if value >= high:
        return "favours" if high_is_good else "against"
    if value < low:
        return "against" if high_is_good else "favours"
    return "neutral"


#: Sentences reused across the branches of one check. A check that can be
#: assessed or "not assessed" is still the same check, and must not explain
#: itself two different ways depending on whether the fetch succeeded.
ROAD_FRONTAGE_MEANS = "Road type and distance decide who passes the gate at all."
EV_GROWTH_MEANS = "Growth says whether that pool of drivers is widening or flat."
DWELL_MEANS = "Somewhere to go while charging is what makes a wait tolerable."
NEAREST_MEANS = "The closest alternative this site's drivers already have."
AMENITIES_MEANS = "Somewhere to walk to is what turns a wait into a stop."

#: The dwell ring the POI fetch already buckets on. Reused rather than
#: re-chosen, so "walking distance" means one thing across the document.
WALK_RING_M = 1_000
AMENITIES_FEW = 3
AMENITIES_MANY = 8


def _site_facts(
    spec: ReportSpec,
    roads: RoadFeatures | None,
    pois: PoiGravity | None,
    vahan: VahanContext,
    competitors: CompetitorContext,
    growth_pct: float | None,
    tariff_row: ElectricityTariff,
    full_kva: float,
    recommended_kva: float,
) -> list[SiteFact]:
    facts: list[SiteFact] = []

    def add(
        group: str,
        label: str,
        value: str,
        source: str,
        direction: Direction,
        means: str,
        *,
        unverified: bool = False,
    ) -> None:
        """Append one check.

        ``means`` is required, not optional, and that is the whole point: a
        reading with no sentence saying why it was taken is a number the
        reader has to take on trust. Write it about the FACTOR, never about
        this site's value - "a divider can force a driver into a U-turn they
        will not make" holds whether or not this site has one, so it survives
        the value changing underneath it.
        """
        facts.append(
            SiteFact(
                label=label,
                value=value,
                source=source,
                unverified=unverified,
                group=group,
                direction=direction,
                means=means,
            )
        )

    # --- access and geometry ------------------------------------------------
    if roads is None or roads.nearest_class is None or roads.distance_m is None:
        add(
            ACCESS,
            "Road frontage",
            "not assessed",
            "OSM fetch failed — pending",
            "neutral",
            ROAD_FRONTAGE_MEANS,
            unverified=True,
        )
    else:
        major = roads.nearest_class in MAJOR_CLASSES[:3]
        if major and roads.distance_m <= MAJOR_ROAD_NEAR_M:
            road_dir: Direction = "favours"
        elif roads.distance_m > ROAD_FAR_M:
            road_dir = "against"
        else:
            road_dir = "neutral"
        add(
            ACCESS,
            "Road frontage",
            f"{roads.nearest_ref or roads.nearest_class} · {roads.distance_m:.0f} m",
            "OSM · Overpass",
            road_dir,
            ROAD_FRONTAGE_MEANS,
        )
        add(
            ACCESS,
            "Carriageway",
            "Divided — one direction served until a median cut is confirmed"
            if roads.divided
            else "Undivided — traffic from both directions can turn in",
            "OSM · Overpass",
            "against" if roads.divided else "favours",
            "Only traffic that can actually reach the entrance counts.",
        )
        add(
            ACCESS,
            "Junctions within 500 m",
            str(roads.junction_count_500m),
            "OSM · Overpass",
            "favours" if roads.junction_count_500m >= 1 else "against",
            "A junction is where a driver can turn round and come back.",
        )
    add(
        ACCESS,
        "Median access",
        "not assessed",
        "carriageway-pair matching pending",
        "neutral",
        "A divider can force a driver into a U-turn they will not make.",
        unverified=True,
    )
    for label, source, means in (
        (
            "Sub-road access",
            SRC_IMAGERY,
            "A second way in is what keeps the site usable when the main entrance backs up.",
        ),
        (
            "Sight line",
            SRC_IMAGERY,
            "A driver who sees the entrance too late has already passed it.",
        ),
        (
            "Turning radius",
            SRC_SURVEY,
            "A car that cannot make the turn does not stop, however good the site is.",
        ),
        (
            "Entry and exit width",
            SRC_SURVEY,
            "Two cars passing at the gate is the difference between a queue and a jam.",
        ),
        (
            "Frontage width",
            SRC_IMAGERY,
            "Frontage is how much road a driver has to notice the site and decide.",
        ),
        (
            "AADT traffic count",
            SRC_TRAFFIC,
            "How many vehicles pass is the ceiling on how many can ever stop.",
        ),
        (
            "Dominant flow direction",
            SRC_TRAFFIC,
            "Morning traffic on the far carriageway is traffic this site cannot serve.",
        ),
        (
            "Peak hour timing",
            SRC_TRAFFIC,
            "A charger earns when the road is busy AND the driver has time to wait.",
        ),
    ):
        add(ACCESS, label, "not assessed", source, "neutral", means, unverified=True)

    # --- demand -------------------------------------------------------------
    vahan_src = f"VAHAN · {vahan.snapshot_date.isoformat()}"
    # A snapshot taken mid-year makes the latest year a partial one. Its level
    # is still a fact; its growth against a FULL previous year is not, and a
    # row that argued "against" on that arithmetic would be the report lying.
    partial = vahan.latest_year == str(vahan.snapshot_date.year)
    stock_label = (
        f"District EV registrations ({vahan.latest_year} to date)"
        if partial
        else f"District EV registrations ({vahan.latest_year})"
    )
    add(
        DEMAND,
        stock_label,
        f"{vahan.ev_latest_year:,}",
        vahan_src,
        _band(vahan.ev_latest_year, EV_STOCK_WEAK, EV_STOCK_STRONG, high_is_good=True),
        "Registrations are the pool of possible drivers, not daily demand.",
    )
    if growth_pct is not None and partial:
        add(
            DEMAND,
            "EV growth, year on year",
            f"{growth_pct:+.1f}% — {vahan.latest_year} to date against a full "
            f"{int(vahan.latest_year) - 1}; not comparable until the year closes",
            vahan_src,
            "neutral",
            EV_GROWTH_MEANS,
            unverified=True,
        )
    elif growth_pct is not None:
        add(
            DEMAND,
            "EV growth, year on year",
            f"{growth_pct:+.1f}%",
            vahan_src,
            _band(growth_pct, GROWTH_WEAK_PCT, GROWTH_STRONG_PCT, high_is_good=True),
            EV_GROWTH_MEANS,
        )
    if vahan.two_wheeler_share is not None:
        heavy = vahan.two_wheeler_share > TWO_WHEELER_HEAVY
        add(
            DEMAND,
            "Vehicle mix",
            f"{vahan.two_wheeler_share * 100:.0f}% two-wheeler"
            + (" — fast charging draws on the four-wheeler share only" if heavy else ""),
            vahan_src,
            "against" if heavy else "favours",
            "Fast charging only serves the vehicles built to take it.",
        )
    if pois is None:
        add(
            DEMAND,
            "Dwell anchors",
            "not assessed",
            "OSM POI fetch failed — pending",
            "neutral",
            DWELL_MEANS,
            unverified=True,
        )
    else:
        anchors = ", ".join(pois.dwell_anchors[:3])
        add(
            DEMAND,
            "Dwell anchors",
            anchors or "none mapped within 1 km — nothing to do while charging",
            f"OSM POI · score {pois.dwell_anchor_score}",
            "favours" if anchors else "against",
            DWELL_MEANS,
        )

    add(
        DEMAND,
        "Fleet operators within 10 km",
        "not assessed",
        "fleet registry pending",
        "neutral",
        "A fleet charges on a schedule, which is demand a public site can plan around.",
        unverified=True,
    )
    add(
        DEMAND,
        "Distance to nearest city",
        "not assessed",
        "settlement layer pending",
        "neutral",
        "Distance to a city decides whether this is a destination or a passing stop.",
        unverified=True,
    )

    # --- power and tariff ---------------------------------------------------
    tariff_src = f"{tariff_row.discom or 'SERC'} · {tariff_row.order_number}"
    add(
        POWER,
        "EV tariff, energy",
        f"₹{tariff_row.energy_paise_per_kwh / 100:.2f}/kWh",
        tariff_src,
        _band(
            tariff_row.energy_paise_per_kwh,
            TARIFF_CHEAP_PAISE,
            TARIFF_DEAR_PAISE,
            high_is_good=False,
        ),
        "What one unit costs to buy, before any of it is sold.",
    )
    demand_charge = tariff_row.demand_paise_per_kva_month
    add(
        POWER,
        "Demand charge",
        "none" if demand_charge == 0 else f"₹{demand_charge / 100:.0f}/kVA/month",
        tariff_src,
        _band(
            demand_charge,
            DEMAND_CHARGE_LOW_PAISE,
            DEMAND_CHARGE_HIGH_PAISE,
            high_is_good=False,
        ),
        "A fixed power bill that arrives whether or not a car turns up.",
    )
    add(
        POWER,
        "Sanctioned load",
        f"{recommended_kva:.0f} kVA advised (managed peak) · {full_kva:.0f} kVA at full load",
        "engine · no customer input",
        "neutral",
        "The connection has to be sized for the plan, and approved for it.",
        unverified=True,
    )
    new_transformer = spec.capex.transformer_paise > 0
    add(
        POWER,
        "Transformer",
        f"new transformer assumed, ₹{spec.capex.transformer_paise / 10_000_000:.1f} L in capex"
        if new_transformer
        else "existing transformer assumed to cover the load",
        "archetype default — site survey confirms",
        "against" if new_transformer else "favours",
        "A new transformer is paid for once, in the setup cost, not monthly.",
        unverified=True,
    )

    add(
        POWER,
        "Transformer distance",
        "not assessed",
        SRC_SURVEY,
        "neutral",
        "Every metre of cable to the transformer is paid for once, in the setup cost.",
        unverified=True,
    )
    add(
        POWER,
        "Transformer spare capacity",
        "not assessed",
        SRC_DISCOM,
        "neutral",
        "A transformer with no spare capacity means a new one, which is the largest "
        "single line in the budget.",
        unverified=True,
    )
    add(
        POWER,
        "Grid outage hours",
        "not assessed",
        "outage log pending — the poller cannot see this either",
        "neutral",
        "Hours without power are hours without revenue, and no map can see them.",
        unverified=True,
    )
    add(
        POWER,
        "New connection cost",
        f"₹{spec.capex.discom_connection_paise / 10_000_000:.1f} L assumed in capex"
        if spec.capex.discom_connection_paise
        else "not assessed",
        SRC_ARCHETYPE if spec.capex.discom_connection_paise else SRC_DISCOM,
        "neutral",
        "The discom charges for the connection itself, and the budget assumes it "
        "rather than quotes it.",
        unverified=True,
    )
    add(
        POWER,
        "State subsidy applicability",
        f"₹{spec.capex.subsidy_paise / 10_000_000:.1f} L assumed, netted off the build cost"
        if spec.capex.subsidy_paise
        else "none assumed",
        SRC_ARCHETYPE,
        "neutral",
        "A subsidy applied for and refused is the commonest way a build budget moves.",
        unverified=True,
    )

    # --- site and amenities -------------------------------------------------
    # The group section 04 has always had a chapter for and never had a row
    # in. One of the seven is real: the POI fetch already counts what is
    # within walking distance, it was simply never printed as its own check.
    add(
        AMENITY,
        "Plot area",
        "not assessed",
        SRC_CUSTOMER,
        "neutral",
        "The plot has to hold the bays, the queue and the turn, not just the chargers.",
        unverified=True,
    )
    add(
        AMENITY,
        "Parking bays",
        f"{spec.connectors} charging bays planned; bays already on the plot not assessed",
        SRC_CUSTOMER,
        "neutral",
        "A bay blocked by a parked car is a charger that is not earning.",
        unverified=True,
    )
    add(
        AMENITY,
        "Canopy feasibility",
        f"₹{spec.capex.signage_canopy_paise / 10_000_000:.1f} L for signage and canopy in capex"
        if spec.capex.signage_canopy_paise
        else "not assessed",
        SRC_ARCHETYPE if spec.capex.signage_canopy_paise else SRC_SURVEY,
        "neutral",
        "Shade and signage are what make a driver choose this site over the next one.",
        unverified=True,
    )
    if pois is None:
        add(
            AMENITY,
            "Amenities within walking distance",
            "not assessed",
            "OSM POI fetch failed — pending",
            "neutral",
            AMENITIES_MEANS,
            unverified=True,
        )
    else:
        walkable = sum(pois.counts.get(WALK_RING_M, {}).values())
        add(
            AMENITY,
            "Amenities within walking distance",
            f"{walkable} within {WALK_RING_M} m",
            "OSM POI · Overpass",
            _band(walkable, AMENITIES_FEW, AMENITIES_MANY, high_is_good=True),
            AMENITIES_MEANS,
        )
    add(
        AMENITY,
        "Mobile network coverage",
        "not assessed",
        "drive test pending",
        "neutral",
        "A charger that cannot reach the network cannot take a payment.",
        unverified=True,
    )
    add(
        AMENITY,
        "Night lighting",
        "not assessed",
        SRC_SURVEY,
        "neutral",
        "Half the charging day is after dark, and a dark forecourt loses it.",
        unverified=True,
    )
    add(
        AMENITY,
        "Land or lease cost",
        f"₹{spec.rent_paise_per_month / 100:,.0f}/month assumed"
        if spec.rent_paise_per_month
        else "owner-occupied — no rent assumed",
        SRC_ARCHETYPE,
        "neutral",
        "Rent arrives every month whether or not a single unit is sold.",
        unverified=True,
    )

    # --- competition --------------------------------------------------------
    if competitors.nearest:
        near = competitors.nearest[0]
        add(
            COMPETITION,
            "Nearest charger",
            f"{near.distance_m} m · {near.operator}",
            competitors.source,
            _band(near.distance_m, NEAREST_CROWDED_M, NEAREST_CLEAR_M, high_is_good=True),
            NEAREST_MEANS,
        )
    else:
        add(
            COMPETITION,
            "Nearest charger",
            "none within 5 km",
            competitors.source,
            "favours",
            NEAREST_MEANS,
        )
    add(
        COMPETITION,
        "Stations within 3 km",
        str(competitors.within_3km),
        competitors.source,
        _band(competitors.within_3km, 1, STATIONS_3KM_CROWDED, high_is_good=False),
        "How many other options sit inside a short detour.",
    )
    add(
        COMPETITION,
        "Stations within 5 km",
        str(competitors.within_5km),
        competitors.source,
        _band(competitors.within_5km, 1, STATIONS_5KM_CROWDED, high_is_good=False),
        "The same count over the wider catchment a driver will still cross.",
    )
    add(
        COMPETITION,
        "Fast chargers (50 kW and up) within 3 km",
        str(competitors.dc_fast_within_3km),
        competitors.source,
        _band(competitors.dc_fast_within_3km, 1, DC_FAST_3KM_CROWDED, high_is_good=False),
        "Only a charger of comparable speed competes for the same stop.",
    )
    add(
        COMPETITION,
        "Announced stations",
        "not assessed",
        "no announcement feed exists",
        "neutral",
        "A station announced but not built is an intention, not concrete — and it "
        "changes the answer the day it opens.",
        unverified=True,
    )
    return facts


def _demand_line(vahan: VahanContext) -> str:
    """The district's EV level and growth in one line. A mid-year snapshot
    makes the latest year partial, and growth against a full previous year
    is then not a comparison - the line says so rather than shouting a
    negative number."""
    partial = vahan.latest_year == str(vahan.snapshot_date.year)
    if vahan.growth is None:
        return f"{vahan.ev_latest_year:,} registrations in {vahan.latest_year}"
    if partial:
        return (
            f"{vahan.ev_latest_year:,} registrations in {vahan.latest_year} to date "
            f"({vahan.growth * 100:+.1f}% against a full {int(vahan.latest_year) - 1}; "
            "not comparable until the year closes)"
        )
    return (
        f"{vahan.ev_latest_year:,} registrations in {vahan.latest_year}, "
        f"{vahan.growth * 100:+.1f}% YoY"
    )


def _ledger(
    spec: ReportSpec,
    prediction: SyntheticPrediction,
    tariff_row: ElectricityTariff,
    roads: RoadFeatures | None,
    vahan: VahanContext,
    competitors: CompetitorContext,
    recommended_kva: float,
    cpo_rows: list[CpoRow],
) -> list[LedgerRow]:
    headline = spec.cpo_options[0].operator if spec.cpo_options else "self-operate"
    rows = [
        LedgerRow(
            item="Utilisation band",
            value=f"{prediction.model_version} — modelled from archetype, VAHAN density and "
            f"competitor density ({prediction.unknown_inputs} input(s) unknown, band widened)",
            source="not measured",
            unverified=True,
        ),
        LedgerRow(
            item="District EV demand",
            value=_demand_line(vahan),
            source=f"VAHAN · snapshot {vahan.snapshot_date.isoformat()}",
            unverified=False,
        ),
        LedgerRow(
            item="Competitor set",
            value=f"{competitors.within_3km} stations within 3 km, deduped inventory",
            source=competitors.source,
            unverified=False,
        ),
        LedgerRow(
            item="Selling price",
            value=f"₹{spec.selling_paise_per_kwh / 100:.2f}/kWh assumed — a decision variable, "
            "not an observation",
            source="archetype default",
            unverified=True,
        ),
        LedgerRow(
            item="Energy tariff",
            value=f"₹{tariff_row.energy_paise_per_kwh / 100:.2f}/kWh EV-specific + demand charge",
            source=f"{tariff_row.discom or 'SERC'} · {tariff_row.order_number}",
            unverified=False,
        ),
        LedgerRow(
            item="Capex",
            value=f"₹{spec.capex.net_paise / 10_000_000:.2f} L net of subsidy — "
            f"{spec.connectors} × {spec.rated_kw_each:.0f} kW DC, civil, grid",
            source="archetype default",
            unverified=True,
        ),
        LedgerRow(
            item="Headline CPO terms",
            value=f"hero economics assume {headline} terms; see the operator table",
            source="placeholder until cpo_terms (Part 6)",
            unverified=True,
        ),
        LedgerRow(
            item="Operator footprint",
            value=(
                f"{sum(1 for r in cpo_rows if r.own_within_3km is not None)} of "
                f"{len(cpo_rows)} arrangement(s) matched to a network in our charger "
                "inventory; the rest report their footprint as unknown, not as zero"
            ),
            source="competitor_stations — partial inventory, deduplicated within ~55 m",
            unverified=True,
        ),
        LedgerRow(
            item="Sanctioned load",
            value=f"no customer input — engine recommends managed-peak {recommended_kva:.0f} kVA",
            source="unconfirmed",
            unverified=True,
        ),
        # Section 06 prices every operator at ONE volume so the table isolates
        # what the terms cost. That is an assumption, and a strong one - it is
        # the reason the comparison must not be read as a forecast of which
        # network brings more drivers (Track B - R9).
        LedgerRow(
            item="Operator comparison",
            value="every operator priced at the same central-case volume, so the table "
            "shows what the terms cost and not which network brings more drivers",
            source="engine re-run per operator, demand held constant",
            unverified=False,
        ),
    ]
    if spec.archetype_hand_assigned:
        rows.insert(
            1,
            LedgerRow(
                item="Archetype",
                value=f"{spec.archetype} — assigned by hand; clustering not yet run",
                source="manual",
                unverified=True,
            ),
        )
    if roads is None or roads.nearest_class is None:
        rows.append(
            LedgerRow(
                item="Road & median access",
                value="road layer could not be fetched; wrong-side penalty not assessed",
                source="OSM pending",
                unverified=True,
            )
        )
    else:
        rows.append(
            LedgerRow(
                item="Median access",
                value="road measured, but which side of the median the site sits on is "
                "not assessed — the wrong side loses roughly half the addressable traffic",
                source="carriageway-pair matching pending",
                unverified=True,
            )
        )
    if vahan.two_wheeler_share is not None and vahan.two_wheeler_share > 0.6:
        rows.append(
            LedgerRow(
                item="Vehicle-mix caveat",
                value=f"{vahan.two_wheeler_share * 100:.0f}% of district registrations are 2W; "
                "DC-fast demand draws on the four-wheeler share only",
                source=f"VAHAN · {vahan.snapshot_date.isoformat()}",
                unverified=False,
            )
        )
    return rows


def _provenance(
    spec: ReportSpec,
    prediction: SyntheticPrediction,
    p50_run: RoiResult,
    vahan: VahanContext,
    competitors: CompetitorContext,
    tariff_row: ElectricityTariff,
) -> list[ProvenanceRow]:
    return [
        ProvenanceRow(label="economics_version", value=p50_run.economics_version),
        ProvenanceRow(
            label="model_version",
            value=f"{prediction.model_version} (stopgap)",
            unverified=True,
        ),
        ProvenanceRow(label="schema_version", value="0012"),
        ProvenanceRow(
            label="archetype_version",
            value="none — hand-assigned" if spec.archetype_hand_assigned else spec.archetype,
            unverified=spec.archetype_hand_assigned,
        ),
        ProvenanceRow(label="VAHAN snapshot", value=vahan.snapshot_date.isoformat()),
        ProvenanceRow(label="competitor fetch", value=competitors.source),
        ProvenanceRow(label="tariff_effective_date", value=tariff_row.effective_from.isoformat()),
        # No PDF exists when the payload is assembled - the renderer loads the
        # report's own URL, so it necessarily runs afterwards. app/pdf/render.py
        # overwrites this cell in the DOM before printing, so the archived
        # artifact carries the real stamp while the payload stays verbatim
        # (Rule 9). What is true HERE is that nothing has been archived yet.
        ProvenanceRow(label="renderer_version", value="no archived render yet", unverified=True),
    ]
