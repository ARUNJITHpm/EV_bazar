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
from app.domain.demand.synthetic import (
    SyntheticInputs,
    SyntheticPrediction,
    SyntheticWeights,
    predict,
)
from app.domain.report.payload import (
    AnchorNote,
    BreakevenPayload,
    CompetitorRow,
    CompetitorsPayload,
    CpoRow,
    DemandPayload,
    FinancialsPayload,
    HardwarePayload,
    LedgerRow,
    PriceSensitivityPoint,
    ProvenanceRow,
    ReportPayload,
    SanctionedLoad,
    Scenario,
    SiteFact,
    SitePayload,
    UtilisationBand,
    VerdictPayload,
)
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


def assemble_report(
    session: Session,
    spec: ReportSpec,
    weights: SyntheticWeights,
    *,
    roads: RoadFeatures | None,
    pois: PoiGravity | None,
    vahan: VahanContext | None = None,
    competitors: CompetitorContext | None = None,
    on: dt.date | None = None,
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
        cpo_rows.append(
            CpoRow(
                operator=option.operator,
                ours=option.ours,
                revenue_share_pct=round(option.terms.revenue_share_pct * 100, 1),
                platform_fee_paise_year=option.terms.network_fee_paise_per_month * 12,
                irr_p50_pct=round((run.irr_pct or 0) * 100, 1),
                margin_of_safety_pp=round(
                    (util["P10 · downside"] - run.breakeven_utilisation) * 100, 1
                ),
                uptime="awaiting poller",
                ocpi_roaming=option.ocpi_roaming,
            )
        )
    cpo_rows.sort(key=lambda r: r.irr_p50_pct, reverse=True)

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
    site_facts = _site_facts(spec, roads, pois, vahan, competitors, growth_pct)
    breakeven_day = p50_run.breakeven_kwh_year / 365.0 if p50_run.breakeven_kwh_year else 0.0

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
        ),
        cpo=cpo_rows,
        ledger=_ledger(spec, prediction, tariff_row, roads, vahan, competitors, managed.kva),
        provenance=_provenance(spec, prediction, p50_run, vahan, competitors, tariff_row),
    )
    return AssembledReport(payload=payload, prediction=prediction)


def _site_facts(
    spec: ReportSpec,
    roads: RoadFeatures | None,
    pois: PoiGravity | None,
    vahan: VahanContext,
    competitors: CompetitorContext,
    growth_pct: float | None,
) -> list[SiteFact]:
    facts: list[SiteFact] = []
    if roads is None or roads.nearest_class is None:
        facts.append(
            SiteFact(
                label="Road frontage",
                value="not assessed",
                source="OSM fetch failed — pending",
                unverified=True,
            )
        )
    else:
        divided = ", divided carriageway" if roads.divided else ""
        facts.append(
            SiteFact(
                label="Road frontage",
                value=f"{roads.nearest_ref or roads.nearest_class} · {roads.distance_m:.0f} m"
                + divided,
                source="OSM · Overpass",
                unverified=False,
            )
        )
        facts.append(
            SiteFact(
                label="Junctions within 500 m",
                value=str(roads.junction_count_500m),
                source="OSM · Overpass",
                unverified=False,
            )
        )
    facts.append(
        SiteFact(
            label="Median access",
            value="not assessed",
            source="carriageway-pair matching pending",
            unverified=True,
        )
    )
    growth = f" · {growth_pct:+.1f}% YoY" if growth_pct is not None else ""
    facts.append(
        SiteFact(
            label=f"District EV stock ({vahan.latest_year})",
            value=f"{vahan.ev_latest_year:,}{growth}",
            source=f"VAHAN · {vahan.snapshot_date.isoformat()}",
            unverified=False,
        )
    )
    if vahan.two_wheeler_share is not None:
        facts.append(
            SiteFact(
                label="Vehicle mix",
                value=f"{vahan.two_wheeler_share * 100:.0f}% two-wheeler",
                source=f"VAHAN · {vahan.snapshot_date.isoformat()}",
                unverified=False,
            )
        )
    if pois is None:
        facts.append(
            SiteFact(
                label="Dwell anchors",
                value="not assessed",
                source="OSM POI fetch failed — pending",
                unverified=True,
            )
        )
    else:
        anchors = ", ".join(pois.dwell_anchors[:3]) or "none mapped within 1 km"
        facts.append(
            SiteFact(
                label="Dwell anchors",
                value=anchors,
                source=f"OSM POI · score {pois.dwell_anchor_score}",
                unverified=False,
            )
        )
    nearest = competitors.nearest[0].distance_m if competitors.nearest else None
    facts.append(
        SiteFact(
            label="Competitors within 3 km",
            value=f"{competitors.within_3km} stations"
            + (f" · nearest {nearest} m" if nearest is not None else ""),
            source="competitor inventory",
            unverified=False,
        )
    )
    return facts


def _ledger(
    spec: ReportSpec,
    prediction: SyntheticPrediction,
    tariff_row: ElectricityTariff,
    roads: RoadFeatures | None,
    vahan: VahanContext,
    competitors: CompetitorContext,
    recommended_kva: float,
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
            value=f"{vahan.ev_latest_year:,} registrations in {vahan.latest_year}"
            + (f", {vahan.growth * 100:+.1f}% YoY" if vahan.growth is not None else ""),
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
            item="Sanctioned load",
            value=f"no customer input — engine recommends managed-peak {recommended_kva:.0f} kVA",
            source="unconfirmed",
            unverified=True,
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
        ProvenanceRow(label="renderer_version", value="dev — unpinned", unverified=True),
    ]
