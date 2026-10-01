"""Private, erasable owner grid revisions; never demand or public features."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OwnerGridConsent(Base):
    __tablename__ = "owner_grid_consents"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("owner_stations.id"), index=True)
    consent_private: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ownership_review_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    purpose_version: Mapped[str] = mapped_column(String(32), nullable=False)
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (CheckConstraint("consent_private", name="ck_owner_grid_consent"),)


class OwnerGridRevision(Base):
    __tablename__ = "owner_grid_revisions"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("owner_stations.id"), index=True)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("owner_grid_revisions.id"))
    effective_on: Mapped[dt.date] = mapped_column(Date, nullable=False)
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sanctioned_load_kva: Mapped[float | None] = mapped_column(Float)
    connected_load_kw: Mapped[float | None] = mapped_column(Float)
    transformer_ownership: Mapped[str] = mapped_column(String(16), nullable=False)
    transformer_rating_kva: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (
        CheckConstraint(
            "sanctioned_load_kva >= 0 AND sanctioned_load_kva <= 1000000", name="ck_grid_sanctioned"
        ),
        CheckConstraint(
            "connected_load_kw >= 0 AND connected_load_kw <= 1000000", name="ck_grid_connected"
        ),
        CheckConstraint(
            "transformer_rating_kva > 0 AND transformer_rating_kva <= 1000000",
            name="ck_grid_rating",
        ),
        CheckConstraint(
            "transformer_ownership IN ('own','shared','unknown')", name="ck_grid_ownership"
        ),
    )


class OwnerOutageRevision(Base):
    __tablename__ = "owner_outage_revisions"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("owner_stations.id"), index=True)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("owner_outage_revisions.id"))
    month: Mapped[dt.date] = mapped_column(Date, nullable=False)
    approximate_hours: Mapped[float | None] = mapped_column(Float)
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint(
            "approximate_hours >= 0 AND approximate_hours <= 744", name="ck_outage_hours"
        ),
    )


GRID_MODELS = (OwnerOutageRevision, OwnerGridRevision, OwnerGridConsent)
