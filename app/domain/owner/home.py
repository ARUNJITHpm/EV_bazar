"""The station home page, assembled from confirmed bills alone.

Everything the page shows is read from what the owner confirmed and from the
forecasts stored when each bill came in. Nothing is scraped, and the forecast on
the page is the stored one, never a recalculation.

Bands, never points: the forecast and every peer figure are P10/P50/P90. There
are no rupee figures except the power factor amount the bill itself printed,
carried as integer paise.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.owner.forecast import model_band
from app.domain.owner.peers import (
    MIN_PEERS,
    PeerRow,
    cohort_size,
    cohort_stat,
    percentile_rank,
)
from app.domain.owner.service import current_bills, month_index, station_readings
from app.models.owner import (
    OwnerBill,
    OwnerConnectorRecord,
    OwnerForecastRecord,
    OwnerStationRecord,
)

#: A contract demand this far above the recorded peak is worth a second look.
CONTRACT_WELL_ABOVE = 1.35
#: DC fast chargers start here; below it a connector is AC.
DC_MIN_KW = 25.0


class Band(BaseModel):
    p10_kwh: float
    p50_kwh: float
    p90_kwh: float


class ConnectorView(BaseModel):
    standard: str
    power_kw: float


class StationView(BaseModel):
    id: int
    name: str
    district: str | None
    state: str | None
    went_live: dt.date
    meter_type: str
    #: True unless the bill is known to be on its own meter.
    possibly_shared: bool
    connectors: list[ConnectorView]


class LastMonth(BaseModel):
    period: dt.date
    month_of_operation: int
    kwh: float


class ForecastView(BaseModel):
    target_month: dt.date
    month_of_operation: int
    band: Band
    model_version: str
    readings_used: int


class SeriesPoint(BaseModel):
    month_of_operation: int
    period: dt.date
    kwh: float


class PeerBandPoint(BaseModel):
    month_of_operation: int
    band: Band
    n: int


class ModelPoint(BaseModel):
    month_of_operation: int
    band: Band


class PeerView(BaseModel):
    #: True only with MIN_PEERS or more comparable stations. Otherwise every
    #: field but ``n`` and ``reason`` is empty and the model curve stands in.
    available: bool
    n: int
    min_required: int
    reason: str | None
    message: str
    #: Same charger type, similar age, same state.
    basis: str
    percentile: float | None
    latest_band: Band | None
    band: list[PeerBandPoint]
    model_curve: list[ModelPoint]


class DemandCard(BaseModel):
    contract: float
    recorded: float
    unit: str
    #: recorded as a share of contract, 0-1.
    used_share: float
    well_above_peak: bool


class PowerFactorCard(BaseModel):
    power_factor: float | None
    effect: str | None
    amount_paise: int | None


class TodCard(BaseModel):
    peak_kwh: float | None
    normal_kwh: float | None
    offpeak_kwh: float | None


class BillMoney(BaseModel):
    period: dt.date
    demand: DemandCard | None
    power_factor: PowerFactorCard | None
    time_of_day: TodCard | None


class TrackRow(BaseModel):
    target_month: dt.date
    forecast_made_from: dt.date
    band: Band
    actual_kwh: float
    error_pct: float
    inside_range: bool
    model_version: str


class BillRef(BaseModel):
    period: dt.date
    kwh: float
    image_id: str | None


class StationHome(BaseModel):
    station: StationView
    last_month: LastMonth | None
    forecast: ForecastView | None
    series: list[SeriesPoint]
    peer: PeerView
    money: BillMoney | None
    track_record: list[TrackRow]
    bills: list[BillRef]


class PortfolioRow(BaseModel):
    station_id: int
    name: str
    district: str | None
    last_period: dt.date | None
    last_kwh: float | None
    change_pct: float | None
    peer_percentile: float | None
    peer_n: int
    possibly_shared: bool


def _round(v: float) -> float:
    return round(v, 1)


def _band(p10: float, p50: float, p90: float, scale: float = 1.0) -> Band:
    return Band(
        p10_kwh=_round(p10 * scale), p50_kwh=_round(p50 * scale), p90_kwh=_round(p90 * scale)
    )


def _connectors(session: Session, station_id: int) -> list[OwnerConnectorRecord]:
    return list(
        session.scalars(
            select(OwnerConnectorRecord)
            .where(OwnerConnectorRecord.station_id == station_id)
            .order_by(OwnerConnectorRecord.id)
        ).all()
    )


def charger_type(power_kw: list[float]) -> str:
    return "DC" if any(p >= DC_MIN_KW for p in power_kw) else "AC"


def peer_rows(session: Session, own: OwnerStationRecord, kind: str) -> list[PeerRow]:
    """One row per peer bill: same state and charger type, own meter, consented."""
    if own.state_name is None:
        return []
    stations = session.scalars(
        select(OwnerStationRecord).where(
            OwnerStationRecord.state_name == own.state_name,
            OwnerStationRecord.meter_type == "separate",
            OwnerStationRecord.consent_aggregate.is_(True),
            OwnerStationRecord.id != own.id,
        )
    ).all()
    rows: list[PeerRow] = []
    for st in stations:
        kw = [c.power_kw for c in _connectors(session, st.id)]
        if not kw or charger_type(kw) != kind:
            continue
        live = month_index(st.went_live)
        for bill in current_bills(session, st.id):
            rows.append(PeerRow(st.id, month_index(bill.period) - live, bill.kwh / sum(kw)))
    return rows


def _peer_view(
    own: OwnerStationRecord,
    kw: list[float],
    last: OwnerBill | None,
    rows: list[PeerRow],
) -> PeerView:
    kind = charger_type(kw)
    basis = f"{kind} chargers, similar age, {own.state_name or 'your state'}"
    age = month_index(last.period) - month_index(own.went_live) if last else 0
    ages = range(0, age + 2)
    total_kw = sum(kw)
    curve = [ModelPoint(month_of_operation=a + 1, band=_model(kw, a)) for a in ages]

    def unavailable(reason: str, n: int, message: str) -> PeerView:
        return PeerView(
            available=False,
            n=n,
            min_required=MIN_PEERS,
            reason=reason,
            message=message,
            basis=basis,
            percentile=None,
            latest_band=None,
            band=[],
            model_curve=curve,
        )

    if own.meter_type != "separate":
        return unavailable(
            "shared_meter",
            0,
            "This meter may include other load, so it is not compared with other stations. "
            "The curve below is the model's estimate.",
        )
    n = cohort_size(rows, age)
    stat = cohort_stat(rows, age)
    if last is None or stat is None:
        return unavailable(
            "too_few",
            n,
            "Not enough similar stations yet. The curve below is the model's estimate.",
        )
    band = [
        PeerBandPoint(month_of_operation=a + 1, band=_band(s.p10, s.p50, s.p90, total_kw), n=s.n)
        for a in ages
        if (s := cohort_stat(rows, a)) is not None
    ]
    return PeerView(
        available=True,
        n=stat.n,
        min_required=MIN_PEERS,
        reason=None,
        message=f"Compared with {stat.n} similar stations.",
        basis=basis,
        percentile=percentile_rank(last.kwh / total_kw, rows, age),
        latest_band=_band(stat.p10, stat.p50, stat.p90, total_kw),
        band=band,
        model_curve=[],
    )


def _model(kw: list[float], age: int) -> Band:
    b = model_band(kw, age)
    return _band(b.p10, b.p50, b.p90)


def _money(last: OwnerBill | None) -> BillMoney | None:
    if last is None:
        return None
    demand = None
    if last.contract_demand and last.recorded_demand and last.demand_unit:
        share = last.recorded_demand / last.contract_demand
        demand = DemandCard(
            contract=last.contract_demand,
            recorded=last.recorded_demand,
            unit=last.demand_unit,
            used_share=round(share, 3),
            well_above_peak=last.contract_demand >= last.recorded_demand * CONTRACT_WELL_ABOVE,
        )
    pf = None
    if last.power_factor is not None or last.pf_amount_paise is not None:
        pf = PowerFactorCard(
            power_factor=last.power_factor,
            effect=last.pf_effect,
            amount_paise=last.pf_amount_paise,
        )
    tod = None
    if any(v is not None for v in (last.tod_peak_kwh, last.tod_normal_kwh, last.tod_offpeak_kwh)):
        tod = TodCard(
            peak_kwh=last.tod_peak_kwh,
            normal_kwh=last.tod_normal_kwh,
            offpeak_kwh=last.tod_offpeak_kwh,
        )
    if demand is None and pf is None and tod is None:
        return None
    return BillMoney(period=last.period, demand=demand, power_factor=pf, time_of_day=tod)


def _track_record(session: Session, station_id: int, bills: list[OwnerBill]) -> list[TrackRow]:
    """Each forecast beside the bill that came in, as it was when it was made."""
    forecasts = session.scalars(
        select(OwnerForecastRecord)
        .where(OwnerForecastRecord.station_id == station_id)
        .order_by(OwnerForecastRecord.id)
    ).all()
    out: list[TrackRow] = []
    for bill in bills:
        made = [
            f
            for f in forecasts
            if f.target_month == bill.period and f.created_at <= bill.created_at
        ]
        if not made:
            continue
        f = made[-1]  # the last forecast standing before the bill arrived
        out.append(
            TrackRow(
                target_month=bill.period,
                forecast_made_from=f.made_from,
                band=_band(f.p10_kwh, f.p50_kwh, f.p90_kwh),
                actual_kwh=bill.kwh,
                error_pct=round(100.0 * (bill.kwh - f.p50_kwh) / f.p50_kwh, 1),
                inside_range=f.p10_kwh <= bill.kwh <= f.p90_kwh,
                model_version=f.model_version,
            )
        )
    return out


def station_home(session: Session, station: OwnerStationRecord) -> StationHome:
    connectors = _connectors(session, station.id)
    kw = [c.power_kw for c in connectors]
    bills = current_bills(session, station.id)
    last = bills[-1] if bills else None
    live = month_index(station.went_live)

    readings = station_readings(bills)
    series = [
        SeriesPoint(month_of_operation=m - live + 1, period=_first(m), kwh=v)
        for m, v in sorted(readings.items())
        if m >= live
    ]

    stored = None
    if last is not None:
        stored = session.scalars(
            select(OwnerForecastRecord)
            .where(
                OwnerForecastRecord.station_id == station.id,
                OwnerForecastRecord.target_month > last.period,
            )
            .order_by(OwnerForecastRecord.id.desc())
        ).first()

    rows = peer_rows(session, station, charger_type(kw)) if kw else []
    return StationHome(
        station=StationView(
            id=station.id,
            name=station.name,
            district=station.district_name,
            state=station.state_name,
            went_live=station.went_live,
            meter_type=station.meter_type,
            possibly_shared=station.meter_type != "separate",
            connectors=[
                ConnectorView(standard=c.standard, power_kw=c.power_kw) for c in connectors
            ],
        ),
        last_month=(
            LastMonth(
                period=last.period,
                month_of_operation=month_index(last.period) - live + 1,
                kwh=last.kwh,
            )
            if last
            else None
        ),
        forecast=(
            ForecastView(
                target_month=stored.target_month,
                month_of_operation=month_index(stored.target_month) - live + 1,
                band=_band(stored.p10_kwh, stored.p50_kwh, stored.p90_kwh),
                model_version=stored.model_version,
                readings_used=stored.readings_used,
            )
            if stored
            else None
        ),
        series=series,
        peer=_peer_view(station, kw, last, rows),
        money=_money(last),
        track_record=_track_record(session, station.id, bills),
        bills=[
            BillRef(period=b.period, kwh=b.kwh, image_id=str(b.image_id) if b.image_id else None)
            for b in bills
        ],
    )


def _first(index: int) -> dt.date:
    return dt.date(index // 12, index % 12 + 1, 1)


def portfolio(session: Session, account_id: int) -> list[PortfolioRow]:
    stations = session.scalars(
        select(OwnerStationRecord)
        .where(OwnerStationRecord.account_id == account_id)
        .order_by(OwnerStationRecord.id)
    ).all()
    out: list[PortfolioRow] = []
    for st in stations:
        kw = [c.power_kw for c in _connectors(session, st.id)]
        bills = current_bills(session, st.id)
        last = bills[-1] if bills else None
        prev = (
            next((b for b in reversed(bills[:-1]) if b.period < last.period), None)
            if last
            else None
        )
        percentile = None
        n = 0
        if last and kw and st.meter_type == "separate":
            rows = peer_rows(session, st, charger_type(kw))
            age = month_index(last.period) - month_index(st.went_live)
            n = cohort_size(rows, age)
            percentile = percentile_rank(last.kwh / sum(kw), rows, age)
        out.append(
            PortfolioRow(
                station_id=st.id,
                name=st.name,
                district=st.district_name,
                last_period=last.period if last else None,
                last_kwh=last.kwh if last else None,
                change_pct=(
                    round(100.0 * (last.kwh - prev.kwh) / prev.kwh, 1) if last and prev else None
                ),
                peer_percentile=percentile,
                peer_n=n,
                possibly_shared=st.meter_type != "separate",
            )
        )
    return out
