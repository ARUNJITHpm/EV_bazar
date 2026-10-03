"""``cea_ev_consumption`` - CEA's monthly EV charging electricity report.

One row per (report, span, place): the electricity EV charging drew from the
grid in a state, a DISCOM, or all of India, for the report month and for the
financial year to date, as the Central Electricity Authority published it.
See ``app.domain.cea.parse``.

**Append-only, keyed on the source file.** Every row carries the sha256 of the
PDF it came from. CEA reports arrive 2-5 months late and a month may be
re-issued; a re-issue is a new file, so it lands as new rows beside the old
ones, and a reader takes the most recently fetched file for a month. Nothing
is updated or deleted.

**kWh, integers, NULL = not reported.** The PDF prints MU to 0.01; stored here
as exact kWh. A DISCOM that did not report is NULL, never zero - most states
have DISCOMs that do not.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CeaEvConsumption(Base):
    __tablename__ = "cea_ev_consumption"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    #: First day of the month the report is for.
    report_month: Mapped[dt.date] = mapped_column(Date, nullable=False)
    #: "month" (the report month) or "fy_to_date" (from ``span_start``).
    span: Mapped[str] = mapped_column(String(12), nullable=False)
    span_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    #: "state" | "discom" | "india".
    geography: Mapped[str] = mapped_column(String(8), nullable=False)
    #: CEA's spelling, verbatim. For a DISCOM, the state it is listed under.
    state_name: Mapped[str] = mapped_column(String(128), nullable=False)
    #: NULL when CEA's line is not one LGD state ("UT of J&K and Ladakh").
    lgd_state_code: Mapped[int | None] = mapped_column(Integer, ForeignKey("states.lgd_state_code"))
    discom: Mapped[str | None] = mapped_column(String(128))
    #: Public charging stations, excluding heavy duty.
    pcs_kwh: Mapped[int | None] = mapped_column(BigInteger)
    #: Heavy-duty public charging stations only.
    heavy_duty_pcs_kwh: Mapped[int | None] = mapped_column(BigInteger)
    #: EV charging stations other than public ones.
    other_kwh: Mapped[int | None] = mapped_column(BigInteger)
    total_kwh: Mapped[int | None] = mapped_column(BigInteger)

    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "source_sha256",
            "span",
            "geography",
            "state_name",
            "discom",
            name="uq_cea_ev_row",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("span IN ('month', 'fy_to_date')", name="ck_cea_ev_span"),
        CheckConstraint("geography IN ('state', 'discom', 'india')", name="ck_cea_ev_geography"),
        Index("ix_cea_ev_month_state", "report_month", "lgd_state_code"),
    )
