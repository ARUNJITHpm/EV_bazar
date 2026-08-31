"""``predictions`` - PLAN 4.3, Rule 2's table.

Every demand prediction ever made, written with a NULL ``actual_kwh`` from the
very first one - "in 18 months this table is worth more than the model"
(OVERVIEW.md Rule 2). AGENTS.md rule 5 is explicit that test and demo runs are
flagged and logged, never skipped, which is what ``is_demo`` is for: the
synthetic stopgap's predictions land here too, and when a calibrated model
arrives its calibration curve must be able to exclude them cleanly.

Append-only (AGENTS.md rule 3): enforced by database rules in migration 0012,
not by convention. Backfilling ``actual_kwh`` when the poller's observations
arrive (PLAN 8) will supersede with new rows carrying the actual - the same
discipline as tariffs.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    site_id: Mapped[uuid.UUID] = mapped_column(Uuid(), ForeignKey("sites.site_id"), nullable=False)

    #: Which model produced the band - "synthetic_v0" for the stopgap.
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Which economics the band was fed into, for joint regeneration.
    economics_version: Mapped[str] = mapped_column(String(16), nullable=False)

    #: kwh_per_connector_day - the ONE thing a model predicts (AGENTS.md rule 1).
    predicted_p10: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_p50: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_p90: Mapped[float] = mapped_column(Float, nullable=False)

    #: Rule 5: demo/test runs are flagged, not skipped.
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    predicted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    #: NULL until a real observation exists (PLAN 8 backfills). The whole
    #: calibration story lives in this pair of columns.
    actual_kwh: Mapped[float | None] = mapped_column(Float)
    actual_observed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_predictions_site", "site_id"),)
