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
    LargeBinary,
    String,
    Text,
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


# --- Owner accounts, stations, bills (migration 0017) ------------------------
#
# The initial stage's only station data source is what owners upload. Accounts
# are a phone number; stations and their connectors are what the owner
# registered (not the scraped inventory); bills are confirmed fields plus the
# original image, kept permanently. Everything but ``owner_accounts`` is insert-
# only in the database: a corrected bill is a NEW row and the latest one for a
# month is the one in force.


class OwnerAccount(Base):
    __tablename__ = "owner_accounts"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    #: Full E.164 number (``+91XXXXXXXXXX``). The browser only ever sees it masked.
    phone: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    #: ``scrypt$...`` (app.auth.hash_password). NULL only on an account made before
    #: passwords existed; such an account cannot log in.
    password_hash: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class OwnerStationRecord(Base):
    __tablename__ = "owner_stations"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("owner_accounts.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    #: Resolved server-side from the pin; NULL when the pin fell outside coverage.
    state_name: Mapped[str | None] = mapped_column(String(64))
    district_name: Mapped[str | None] = mapped_column(String(64))
    went_live: Mapped[dt.date] = mapped_column(Date, nullable=False)
    #: separate | shared | unsure. Anything but ``separate`` stays out of peer averages.
    meter_type: Mapped[str] = mapped_column(String(16), nullable=False)
    #: "Use my figures to benchmark and forecast my station. Only published as
    #: anonymised district averages of 10 or more stations." Required.
    consent_aggregate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    consent_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_owner_stations_account", "account_id"),
        CheckConstraint("consent_aggregate", name="ck_owner_station_consent"),
        CheckConstraint(
            "meter_type IN ('separate','shared','unsure')", name="ck_owner_station_meter"
        ),
    )


class OwnerConnectorRecord(Base):
    __tablename__ = "owner_connectors"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    station_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("owner_stations.id"), nullable=False
    )
    standard: Mapped[str] = mapped_column(String(24), nullable=False)
    power_kw: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_owner_connectors_station", "station_id"),
        CheckConstraint("power_kw > 0", name="ck_owner_connector_power"),
    )


class OwnerBillImage(Base):
    """The uploaded bill photo or PDF, kept as uploaded (never deleted)."""

    __tablename__ = "owner_bill_images"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("owner_accounts.id"), nullable=False
    )
    content_type: Mapped[str] = mapped_column(String(48), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OwnerBill(Base):
    __tablename__ = "owner_bills"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), Identity(), primary_key=True
    )
    station_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("owner_stations.id"), nullable=False
    )
    #: First day of the billed month.
    period: Mapped[dt.date] = mapped_column(Date, nullable=False)
    kwh: Mapped[float] = mapped_column(Float, nullable=False)
    #: Past consumption printed on the bill: ``[{"period": "2026-03-01", "kwh": 812}]``.
    history: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonColumn)
    tariff_category: Mapped[str | None] = mapped_column(String(80))
    contract_demand: Mapped[float | None] = mapped_column(Float)
    recorded_demand: Mapped[float | None] = mapped_column(Float)
    #: "kVA" or "kW" as printed; the two are never converted between.
    demand_unit: Mapped[str | None] = mapped_column(String(3))
    power_factor: Mapped[float | None] = mapped_column(Float)
    #: penalty | incentive, with the amount as integer paise (money is paise).
    pf_effect: Mapped[str | None] = mapped_column(String(9))
    pf_amount_paise: Mapped[int | None] = mapped_column(BigInteger)
    tod_peak_kwh: Mapped[float | None] = mapped_column(Float)
    tod_normal_kwh: Mapped[float | None] = mapped_column(Float)
    tod_offpeak_kwh: Mapped[float | None] = mapped_column(Float)
    board: Mapped[str | None] = mapped_column(String(64))
    #: Last four characters of the consumer number. The full number is never stored.
    consumer_last4: Mapped[str | None] = mapped_column(String(4))
    #: image | typed
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    image_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), ForeignKey("owner_bill_images.id"))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_owner_bills_station_period", "station_id", "period"),
        CheckConstraint("kwh > 0", name="ck_owner_bill_kwh"),
        CheckConstraint("source IN ('image','typed')", name="ck_owner_bill_source"),
    )


class OwnerForecastRecord(Base):
    """A forecast as it was made. Never recomputed, so the track record is honest."""

    __tablename__ = "owner_forecasts"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), Identity(), primary_key=True
    )
    station_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("owner_stations.id"), nullable=False
    )
    #: The latest billed month the forecast was made from.
    made_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    target_month: Mapped[dt.date] = mapped_column(Date, nullable=False)
    p10_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    p50_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    p90_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    readings_used: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_owner_forecasts_station_target", "station_id", "target_month"),)
