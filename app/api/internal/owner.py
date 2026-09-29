"""Station-owner upload.

``GET /owner/stations`` - find your station: read-only search over
``competitor_stations``, public inventory only.

``POST /owner/submissions`` - store what the owner tells us and return the peer
comparison and next-month energy band. The maths lives in
``app.domain.owner``; the browser never computes it. Both are open (the owner
holds no login) and throttled, like ``/assess``.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.owner import ForecastBand, expand_connectors, forecast, valid_readings
from app.models.competitors import CompetitorStation
from app.models.owner import OwnerReading, OwnerSubmission
from app.models.reference import State

router = APIRouter(prefix="/owner")


class OwnerStation(BaseModel):
    id: int
    name: str | None
    operator: str | None
    town: str | None
    lat: float
    lng: float
    number_of_points: int | None
    connectors: list[dict[str, object]] | None
    #: One kW per physical connector, in the order ``connector_indices`` refers to.
    connector_kw: list[float]
    source: str


class OwnerStationsOut(BaseModel):
    total: int
    stations: list[OwnerStation]


@router.get("/stations", response_model=OwnerStationsOut)
def stations(
    q: str = Query("", max_length=80),
    state: str = Query("Kerala", max_length=64),
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> OwnerStationsOut:
    stmt = (
        select(CompetitorStation)
        .join(State, State.lgd_state_code == CompetitorStation.lgd_state_code)
        .where(State.name.ilike(state))
    )
    term = q.strip()
    if term:
        like = f"%{term}%"
        stmt = stmt.where(
            or_(
                CompetitorStation.name.ilike(like),
                CompetitorStation.town.ilike(like),
                CompetitorStation.operator.ilike(like),
            )
        )
    rows = session.execute(stmt.order_by(CompetitorStation.name).limit(limit)).scalars().all()
    return OwnerStationsOut(
        total=len(rows),
        stations=[
            OwnerStation(
                id=r.id,
                name=r.name,
                operator=r.operator,
                town=r.town,
                lat=r.lat,
                lng=r.lng,
                number_of_points=r.number_of_points,
                connectors=r.connectors,
                connector_kw=expand_connectors(r.connectors),
                source=r.source,
            )
            for r in rows
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
    connector_indices: list[int] = Field(min_length=1, max_length=64)
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


@router.post("/submissions", response_model=SubmissionOut, status_code=201)
def submit(body: SubmissionIn, session: Session = Depends(get_session)) -> SubmissionOut:
    if not body.consent_aggregate:
        raise HTTPException(422, "Consent to anonymous averaging is required.")
    station = session.get(CompetitorStation, body.station_id)
    if station is None:
        raise HTTPException(404, "Unknown station.")
    all_kw = expand_connectors(station.connectors)
    picked = sorted(set(body.connector_indices))
    if not all_kw or picked[-1] >= len(all_kw) or picked[0] < 0:
        raise HTTPException(422, "Pick connectors this station has.")
    kw = [all_kw[i] for i in picked]

    install = _month_index(body.install_month)
    readings = {_month_index(r.month): r.kwh for r in body.readings}
    result = forecast(kw, install, readings)
    if result is None:
        raise HTTPException(422, "No usable readings: check the months and the kWh figures.")
    used = len(valid_readings(readings, install, kw))

    sub = OwnerSubmission(
        competitor_station_id=station.id,
        connector_indices=picked,
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
