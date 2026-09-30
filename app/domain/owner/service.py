"""Writing owner data: accounts, stations, confirmed bills and the forecast made from them.

Every write that follows a bill goes through ``add_bill``: it validates against
the station's connectors, inserts the bill (never updates one), and stores the
forecast it produced *as it was made* so the track record can later compare
against it, not against a recalculation.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.owner.bill import BillFields, mask_consumer_number, validate
from app.domain.owner.forecast import DEFAULT_FORECASTER, Forecaster
from app.models.owner import (
    OwnerAccount,
    OwnerBill,
    OwnerBillImage,
    OwnerConnectorRecord,
    OwnerForecastRecord,
    OwnerStationRecord,
)


class BillInvalidError(ValueError):
    """The bill cannot be saved. ``errors`` are plain sentences for the owner."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__(" ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class ConnectorSpec:
    standard: str
    power_kw: float


@dataclass(frozen=True)
class StationSpec:
    name: str
    address: str | None
    lat: float
    lng: float
    state_name: str | None
    district_name: str | None
    went_live: dt.date
    meter_type: str


def month_index(d: dt.date) -> int:
    return d.year * 12 + d.month - 1


def first_of(index: int) -> dt.date:
    return dt.date(index // 12, index % 12 + 1, 1)


def find_account(session: Session, phone: str) -> OwnerAccount | None:
    return session.scalar(select(OwnerAccount).where(OwnerAccount.phone == phone))


def create_account(
    session: Session, phone: str, password_hash: str, now: dt.datetime
) -> OwnerAccount:
    account = OwnerAccount(phone=phone, password_hash=password_hash, last_login_at=now)
    session.add(account)
    session.flush()
    return account


def store_image(
    session: Session, account_id: int, content: bytes, content_type: str, sha256: str
) -> OwnerBillImage:
    image = OwnerBillImage(
        id=uuid.uuid4(),
        account_id=account_id,
        content_type=content_type,
        size_bytes=len(content),
        sha256=sha256,
        data=content,
    )
    session.add(image)
    session.flush()
    return image


def current_bills(session: Session, station_id: int) -> list[OwnerBill]:
    """The bill in force for each month: the latest row written for it."""
    rows = session.scalars(
        select(OwnerBill).where(OwnerBill.station_id == station_id).order_by(OwnerBill.id)
    ).all()
    by_period: dict[dt.date, OwnerBill] = {}
    for row in rows:
        by_period[row.period] = row
    return [by_period[p] for p in sorted(by_period)]


def station_readings(bills: Sequence[OwnerBill]) -> dict[int, float]:
    """Monthly kWh keyed by month index: past consumption printed on bills fills
    months with no bill of their own; a confirmed bill for a month always wins."""
    readings: dict[int, float] = {}
    for bill in bills:  # oldest period first, so a later bill's history wins
        for entry in bill.history or []:
            readings[month_index(dt.date.fromisoformat(str(entry["period"])))] = float(entry["kwh"])
    for bill in bills:
        readings[month_index(bill.period)] = bill.kwh
    return readings


def add_bill(
    session: Session,
    station: OwnerStationRecord,
    fields: BillFields,
    *,
    image_id: uuid.UUID | None,
    today: dt.date,
    forecaster: Forecaster = DEFAULT_FORECASTER,
) -> OwnerBill:
    connectors = session.scalars(
        select(OwnerConnectorRecord.power_kw).where(OwnerConnectorRecord.station_id == station.id)
    ).all()
    errors = validate(
        fields, total_kw=float(sum(connectors)), went_live=station.went_live, today=today
    )
    if errors:
        raise BillInvalidError(errors)
    bill = OwnerBill(
        station_id=station.id,
        period=fields.period,
        kwh=fields.kwh,
        history=[{"period": p.isoformat(), "kwh": v} for p, v in fields.history] or None,
        tariff_category=fields.tariff_category,
        contract_demand=fields.contract_demand,
        recorded_demand=fields.recorded_demand,
        demand_unit=fields.demand_unit,
        power_factor=fields.power_factor,
        pf_effect=fields.pf_effect,
        pf_amount_paise=fields.pf_amount_paise,
        tod_peak_kwh=fields.tod_peak_kwh,
        tod_normal_kwh=fields.tod_normal_kwh,
        tod_offpeak_kwh=fields.tod_offpeak_kwh,
        board=fields.board,
        consumer_last4=mask_consumer_number(fields.consumer_number),
        source="image" if image_id else "typed",
        image_id=image_id,
    )
    session.add(bill)
    session.flush()
    _store_forecast(session, station, [float(k) for k in connectors], forecaster)
    return bill


def _store_forecast(
    session: Session, station: OwnerStationRecord, kw: list[float], forecaster: Forecaster
) -> None:
    bills = current_bills(session, station.id)
    result = forecaster(kw, month_index(station.went_live), station_readings(bills))
    if result is None:
        return
    target = first_of(result.next_month)
    # A forecast for a month whose bill is already in is hindsight, not a forecast.
    if any(b.period == target for b in bills):
        return
    used_to = first_of(result.next_month - 1)
    session.add(
        OwnerForecastRecord(
            station_id=station.id,
            made_from=used_to,
            target_month=target,
            p10_kwh=result.band.p10,
            p50_kwh=result.band.p50,
            p90_kwh=result.band.p90,
            model_version=result.model_version,
            readings_used=result.readings_used,
        )
    )


def register_station(
    session: Session,
    account: OwnerAccount,
    spec: StationSpec,
    connectors: Sequence[ConnectorSpec],
    *,
    consent_aggregate: bool,
    now: dt.datetime,
) -> OwnerStationRecord:
    if not consent_aggregate:
        raise BillInvalidError(["Consent to benchmarking is required."])
    if not connectors:
        raise BillInvalidError(["Add at least one connector."])
    station = OwnerStationRecord(
        account_id=account.id,
        name=spec.name,
        address=spec.address,
        lat=spec.lat,
        lng=spec.lng,
        state_name=spec.state_name,
        district_name=spec.district_name,
        went_live=spec.went_live.replace(day=1),
        meter_type=spec.meter_type,
        consent_aggregate=True,
        consent_at=now,
    )
    session.add(station)
    session.flush()
    session.add_all(
        OwnerConnectorRecord(station_id=station.id, standard=c.standard, power_kw=c.power_kw)
        for c in connectors
    )
    session.flush()
    return station


def owned_station(session: Session, account_id: int, station_id: int) -> OwnerStationRecord | None:
    station = session.get(OwnerStationRecord, station_id)
    return station if station is not None and station.account_id == account_id else None


def station_count(session: Session, account_id: int) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(OwnerStationRecord)
            .where(OwnerStationRecord.account_id == account_id)
        )
        or 0
    )
