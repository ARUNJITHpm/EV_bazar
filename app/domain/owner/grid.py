"""Owner-authorized append-only writes and explicit private-grid erasure."""

from __future__ import annotations

import calendar
import datetime as dt
import json
import os
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.owner import OwnerStationRecord
from app.models.owner_grid import (
    GRID_MODELS,
    OwnerGridConsent,
    OwnerGridRevision,
    OwnerOutageRevision,
)

OWNER_GRID_VERSIONS = {
    "model_version": "not_applicable:owner_entered",
    "economics_version": "not_applicable:no_economics",
    "schema_version": "owner_grid_v1",
    "archetype_version": "not_applicable:private_grid",
    "tariff_effective_date": "not_applicable:private_grid",
    "renderer_version": "owner_grid_ui_v1",
}

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


class TimestampOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    recorded_at: dt.datetime

    @field_validator("recorded_at")
    @classmethod
    def utc_timestamp(cls, value: dt.datetime) -> dt.datetime:
        return value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value.astimezone(dt.UTC)


class GridDetailsIn(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    consent_private: Literal[True]
    expected_revision_id: int | None = Field(default=None, gt=0)
    effective_on: dt.date
    sanctioned_load_kva: float | None = Field(default=None, ge=0, le=1000000)
    connected_load_kw: float | None = Field(default=None, ge=0, le=1000000)
    transformer_ownership: Literal["own", "shared", "unknown"] = "unknown"
    transformer_rating_kva: float | None = Field(default=None, gt=0, le=1000000)

    @field_validator("effective_on")
    @classmethod
    def not_future(cls, value: dt.date) -> dt.date:
        if value > dt.datetime.now(IST).date():
            raise ValueError("Effective date cannot be in the future")
        return value


class OutageIn(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    consent_private: Literal[True]
    expected_revision_id: int | None = Field(default=None, gt=0)
    month: dt.date
    approximate_hours: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def valid_month_hours(self) -> OutageIn:
        today = dt.datetime.now(IST).date()
        if self.month.day != 1 or self.month > today.replace(day=1):
            raise ValueError("Use a current/past month, dated on its first day")
        maximum = calendar.monthrange(self.month.year, self.month.month)[1] * 24
        if self.approximate_hours is not None and self.approximate_hours > maximum:
            raise ValueError("Outage hours exceed the calendar month's hours")
        return self


class GridDetailsOut(TimestampOut):
    model_config = ConfigDict(from_attributes=True)
    id: int
    supersedes_id: int | None
    effective_on: dt.date
    recorded_at: dt.datetime
    sanctioned_load_kva: float | None
    connected_load_kw: float | None
    transformer_ownership: Literal["own", "shared", "unknown"]
    transformer_rating_kva: float | None


class OutageOut(TimestampOut):
    model_config = ConfigDict(from_attributes=True)
    id: int
    supersedes_id: int | None
    month: dt.date
    approximate_hours: float | None
    recorded_at: dt.datetime


class OwnerGridOut(BaseModel):
    version: Literal["owner_grid_v1"] = "owner_grid_v1"
    versions: dict[str, str] = Field(default_factory=lambda: dict(OWNER_GRID_VERSIONS))
    consent_private: bool
    storage_available: bool
    storage_reason: str | None = None
    details: GridDetailsOut | None
    outages: list[OutageOut]


def ownership_review(station_id: int) -> str | None:
    """Fail closed: deployment staff supply reviewed station ID/evidence pairs."""
    try:
        reviews = json.loads(os.environ.get("OWNER_GRID_VERIFIED_STATIONS", "{}"))
        if not isinstance(reviews, dict) or any(
            not str(key).isdigit() or not isinstance(value, str) or not value.strip()
            for key, value in reviews.items()
        ):
            raise ValueError("Invalid ownership register")
    except (ValueError, TypeError) as error:
        raise HTTPException(
            503, "Station ownership review configuration is unavailable."
        ) from error
    return reviews.get(str(station_id))


def _station(
    session: Session, account_id: int, station_id: int, *, lock: bool = False
) -> OwnerStationRecord:
    statement = select(OwnerStationRecord).where(
        OwnerStationRecord.id == station_id,
        OwnerStationRecord.account_id == account_id,
    )
    station = session.scalar(statement.with_for_update() if lock else statement)
    if station is None:
        raise HTTPException(404, "No such station.")
    return station


def _details(session: Session, station_id: int) -> OwnerGridRevision | None:
    return session.scalar(
        select(OwnerGridRevision)
        .where(
            OwnerGridRevision.station_id == station_id,
        )
        .order_by(OwnerGridRevision.id.desc())
        .limit(1)
    )


def _consent(session: Session, station_id: int, now: dt.datetime) -> None:
    review = ownership_review(station_id)
    if review is None:
        raise HTTPException(403, "Private grid storage needs reviewed station ownership evidence.")
    if (
        session.scalar(select(OwnerGridConsent.id).where(OwnerGridConsent.station_id == station_id))
        is None
    ):
        session.add(
            OwnerGridConsent(
                station_id=station_id,
                consent_private=True,
                purpose_version="private_display_v1",
                ownership_review_ref=review,
                recorded_at=now,
            )
        )


def _check_revision(expected: int | None, current: int | None) -> None:
    if expected != current:
        raise HTTPException(409, "The grid record changed. Reload before saving this correction.")


def read_grid(session: Session, account_id: int, station_id: int) -> OwnerGridOut:
    _station(session, account_id, station_id)
    details = _details(session, station_id)
    consent = session.scalar(
        select(OwnerGridConsent.id).where(OwnerGridConsent.station_id == station_id)
    )
    revisions = session.scalars(
        select(OwnerOutageRevision)
        .where(
            OwnerOutageRevision.station_id == station_id,
        )
        .order_by(OwnerOutageRevision.id)
    ).all()
    latest = {row.month: row for row in revisions}
    return OwnerGridOut(
        consent_private=consent is not None,
        storage_available=ownership_review(station_id) is not None,
        storage_reason=(
            None
            if ownership_review(station_id) is not None
            else "Private grid storage needs reviewed station ownership evidence."
        ),
        details=GridDetailsOut.model_validate(details) if details else None,
        outages=[OutageOut.model_validate(latest[month]) for month in sorted(latest, reverse=True)],
    )


def save_grid(
    session: Session, account_id: int, station_id: int, data: GridDetailsIn
) -> OwnerGridOut:
    _station(session, account_id, station_id, lock=True)
    previous = _details(session, station_id)
    _check_revision(data.expected_revision_id, previous.id if previous else None)
    now = dt.datetime.now(dt.UTC)
    _consent(session, station_id, now)
    values = data.model_dump(exclude={"consent_private", "expected_revision_id"})
    session.add(
        OwnerGridRevision(
            station_id=station_id,
            supersedes_id=previous.id if previous else None,
            recorded_at=now,
            **values,
        )
    )
    session.flush()
    return read_grid(session, account_id, station_id)


def save_outage(session: Session, account_id: int, station_id: int, data: OutageIn) -> OwnerGridOut:
    _station(session, account_id, station_id, lock=True)
    previous = session.scalar(
        select(OwnerOutageRevision)
        .where(
            OwnerOutageRevision.station_id == station_id,
            OwnerOutageRevision.month == data.month,
        )
        .order_by(OwnerOutageRevision.id.desc())
        .limit(1)
    )
    _check_revision(data.expected_revision_id, previous.id if previous else None)
    now = dt.datetime.now(dt.UTC)
    _consent(session, station_id, now)
    session.add(
        OwnerOutageRevision(
            station_id=station_id,
            supersedes_id=previous.id if previous else None,
            month=data.month,
            approximate_hours=data.approximate_hours,
            recorded_at=now,
        )
    )
    session.flush()
    return read_grid(session, account_id, station_id)


def erase_grid_for_stations(session: Session, station_ids: list[int]) -> None:
    """Privacy erasure of all versions; caller owns authorization and transaction."""
    if station_ids:
        for model in GRID_MODELS:
            session.execute(delete(model).where(model.station_id.in_(station_ids)))
        session.flush()


def withdraw_grid(session: Session, account_id: int, station_id: int) -> None:
    _station(session, account_id, station_id, lock=True)
    erase_grid_for_stations(session, [station_id])
