"""Station-owner upload.

``GET /owner/stations`` - find your station: read-only search over the
charging-network tables (``stations`` and their connectors), public inventory
only. A submission names a station and the real connectors the owner picked.

``POST /owner/submissions`` - store what the owner tells us and return the peer
comparison and next-month energy band. The maths lives in
``app.domain.owner``; the browser never computes it. Both are open (the owner
holds no login) and throttled like ``/assess``; the POST also has its own
hourly per-IP cap, because a submission is a row that can never be deleted.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, PositiveInt, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.internal.ratelimit import owner_submit_limit
from app.db import get_session
from app.domain.owner import ForecastBand, forecast, valid_readings
from app.models.charging import Charger, Connector, Cpo, Station
from app.models.owner import OwnerReading, OwnerSubmission
from app.models.reference import State

router = APIRouter(prefix="/owner")


class OwnerConnector(BaseModel):
    id: int
    standard: str | None
    power_kw: float


class OwnerStation(BaseModel):
    id: int
    name: str | None
    operator: str | None
    town: str | None
    lat: float
    lng: float
    #: Only connectors whose power is known - a forecast needs it. Ordered by id.
    connectors: list[OwnerConnector]


class OwnerStationsOut(BaseModel):
    total: int
    stations: list[OwnerStation]


def _powered_connectors(
    session: Session, station_ids: list[int], only: list[int] | None = None
) -> list[tuple[int, int, str | None, float]]:
    """(station id, connector id, standard, kW) for connectors with a known power."""
    stmt = (
        select(Charger.station_id, Connector.id, Connector.standard, Connector.max_power_kw)
        .join(Charger, Charger.id == Connector.charger_id)
        .where(
            Charger.station_id.in_(station_ids),
            Charger.status != "retired",
            Connector.max_power_kw.is_not(None),
        )
        .order_by(Connector.id)
    )
    if only is not None:
        stmt = stmt.where(Connector.id.in_(only))
    return [(sid, cid, std, float(kw)) for sid, cid, std, kw in session.execute(stmt).all()]


@router.get("/stations", response_model=OwnerStationsOut)
def stations(
    q: str = Query("", max_length=80),
    state: str = Query("Kerala", max_length=64),
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> OwnerStationsOut:
    stmt = (
        select(Station, Cpo.name)
        .join(State, State.lgd_state_code == Station.lgd_state_code)
        .outerjoin(Cpo, Cpo.id == Station.cpo_id)
        .where(State.name.ilike(state), Station.merged_into_id.is_(None))
    )
    term = q.strip()
    if term:
        like = f"%{term}%"
        stmt = stmt.where(
            or_(
                Station.name.ilike(like),
                Station.town.ilike(like),
                Station.operator_raw.ilike(like),
                Cpo.name.ilike(like),
            )
        )
    rows = session.execute(stmt.order_by(Station.name, Station.id).limit(limit)).all()
    by_station: dict[int, list[OwnerConnector]] = {}
    for sid, cid, std, kw in _powered_connectors(session, [st.id for st, _ in rows]):
        by_station.setdefault(sid, []).append(OwnerConnector(id=cid, standard=std, power_kw=kw))
    return OwnerStationsOut(
        total=len(rows),
        stations=[
            OwnerStation(
                id=st.id,
                name=st.name,
                operator=cpo_name or st.operator_raw,
                town=st.town,
                lat=st.lat,
                lng=st.lng,
                connectors=by_station.get(st.id, []),
            )
            for st, cpo_name in rows
        ],
    )


_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _month_index(value: str) -> int:
    year, month = value.split("-")
    return int(year) * 12 + int(month) - 1


def _first_of(index: int) -> dt.date:
    return dt.date(index // 12, index % 12 + 1, 1)


def _month_str(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


class ReadingIn(BaseModel):
    month: str
    kwh: float = Field(gt=0, le=1_000_000)

    @field_validator("month")
    @classmethod
    def _check_month(cls, v: str) -> str:
        if not _MONTH.match(v):
            raise ValueError("month must be YYYY-MM")
        return v


class SubmissionIn(BaseModel):
    station_id: int
    connector_ids: list[PositiveInt] = Field(min_length=1, max_length=64)
    install_month: str
    meter_type: Literal["separate", "shared", "unsure"]
    readings: list[ReadingIn] = Field(min_length=1, max_length=24)
    consent_aggregate: bool
    consent_public: bool = False

    @field_validator("install_month")
    @classmethod
    def _check_install(cls, v: str) -> str:
        if not _MONTH.match(v):
            raise ValueError("install_month must be YYYY-MM")
        return v


class BandOut(BaseModel):
    p10_kwh: float
    p50_kwh: float
    p90_kwh: float


class SubmissionOut(BaseModel):
    submission_id: uuid.UUID
    model_version: str
    readings_used: int
    readings_ignored: int
    next_month: str
    age_months: int
    forecast: BandOut
    peer: BandOut
    relative_to_peers: float
    peer_percentile: float


def _band(b: ForecastBand) -> BandOut:
    return BandOut(p10_kwh=round(b.p10, 1), p50_kwh=round(b.p50, 1), p90_kwh=round(b.p90, 1))


@router.post(
    "/submissions",
    response_model=SubmissionOut,
    status_code=201,
    dependencies=[Depends(owner_submit_limit)],
)
def submit(body: SubmissionIn, session: Session = Depends(get_session)) -> SubmissionOut:
    if not body.consent_aggregate:
        raise HTTPException(422, "Consent to anonymous averaging is required.")
    station = session.get(Station, body.station_id)
    if station is None or station.merged_into_id is not None:
        raise HTTPException(404, "Unknown station.")
    picked = sorted(set(body.connector_ids))
    power = {cid: kw for _, cid, _, kw in _powered_connectors(session, [station.id], picked)}
    if any(cid not in power for cid in picked):
        raise HTTPException(422, "Pick connectors this station has.")
    kw = [power[cid] for cid in picked]

    install = _month_index(body.install_month)
    readings = {_month_index(r.month): r.kwh for r in body.readings}
    result = forecast(kw, install, readings)
    if result is None:
        raise HTTPException(422, "No usable readings: check the months and the kWh figures.")
    used = len(valid_readings(readings, install, kw))

    sub = OwnerSubmission(
        station_id=station.id,
        connector_ids=picked,
        install_month=_first_of(install),
        meter_type=body.meter_type,
        consent_aggregate=body.consent_aggregate,
        consent_public=body.consent_public,
        model_version=result.model_version,
        forecast={
            "model_version": result.model_version,
            "next_month": _month_str(result.next_month),
            "band": _band(result.band).model_dump(),
            "peer": _band(result.peer_band).model_dump(),
            "relative_to_peers": result.relative_to_peers,
            "peer_percentile": result.peer_percentile,
        },
    )
    sub.submission_id = uuid.uuid4()
    session.add(sub)
    session.flush()
    session.add_all(
        OwnerReading(submission_id=sub.submission_id, month=_first_of(m), kwh=v)
        for m, v in sorted(readings.items())
    )
    return SubmissionOut(
        submission_id=sub.submission_id,
        model_version=result.model_version,
        readings_used=used,
        readings_ignored=len(readings) - used,
        next_month=_month_str(result.next_month),
        age_months=result.age_months,
        forecast=_band(result.band),
        peer=_band(result.peer_band),
        relative_to_peers=round(result.relative_to_peers, 3),
        peer_percentile=result.peer_percentile,
    )
