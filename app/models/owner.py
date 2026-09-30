"""``owner_submissions`` / ``owner_readings`` - what a station owner told us.

Append-only, enforced by database rules in migration 0014 (AGENTS.md rule 3).
A correction is a NEW submission; the earlier one stays as what was said.

The stored ``forecast`` carries ``model_version`` (rule 4), so a submission can
be re-scored later without losing what the owner was originally shown.

**Two ways to say which station.** New submissions carry ``station_id`` and
``connector_ids`` (the charging-network tables, migration 0015): real ids that
stay valid when a station's connector list is re-ordered. Rows written before
migration 0016 carry ``competitor_station_id`` and ``connector_indices`` instead,
and stay that way - the table is append-only, so they cannot be rewritten.
A check constraint requires one complete pair.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
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
    #: The station and the connectors the owner picked (``stations.id``,
    #: ``connectors.id``). Set on every submission written since migration 0016.
    station_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("stations.id"))
    connector_ids: Mapped[list[int] | None] = mapped_column(JsonColumn)
    #: Legacy pair, from before 0016: positions into a competitor row's expanded
    #: connector list. NULL on new submissions.
    competitor_station_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("competitor_stations.id")
    )
    connector_indices: Mapped[list[int] | None] = mapped_column(JsonColumn)
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

    __table_args__ = (
        Index("ix_owner_submissions_station", "competitor_station_id"),
        Index("ix_owner_submissions_network_station", "station_id"),
        CheckConstraint(
            "(station_id IS NOT NULL AND connector_ids IS NOT NULL) "
            "OR (competitor_station_id IS NOT NULL AND connector_indices IS NOT NULL)",
            name="ck_owner_station_ref",
        ),
    )


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
