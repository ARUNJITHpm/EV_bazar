"""``owner_submissions`` / ``owner_readings`` - what a station owner told us.

Append-only, enforced by database rules in migration 0014 (AGENTS.md rule 3).
A correction is a NEW submission; the earlier one stays as what was said.

The stored ``forecast`` carries ``model_version`` (rule 4), so a submission can
be re-scored later without losing what the owner was originally shown.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

JsonColumn = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class OwnerSubmission(Base):
    __tablename__ = "owner_submissions"

    submission_id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    competitor_station_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("competitor_stations.id"), nullable=False
    )
    #: Positions into the station's expanded connector list, as the owner picked.
    connector_indices: Mapped[list[int]] = mapped_column(JsonColumn, nullable=False)
    #: First day of the month the station went live.
    install_month: Mapped[dt.date] = mapped_column(Date, nullable=False)
    #: separate | shared | unsure - whether the bill measures charging alone.
    meter_type: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Consent to use the figures in anonymous peer averages. Required.
    consent_aggregate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    #: Consent to be named on the public map. Optional.
    consent_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    forecast: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_owner_submissions_station", "competitor_station_id"),)


class OwnerReading(Base):
    __tablename__ = "owner_readings"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("owner_submissions.submission_id"), nullable=False
    )
    #: First day of the billed month.
    month: Mapped[dt.date] = mapped_column(Date, nullable=False)
    kwh: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (Index("ix_owner_readings_submission", "submission_id"),)
