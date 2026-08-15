"""``vahan_ev_registrations`` - PART 4.1, EV vehicle counts per district.

The demand layer's raw input: how many electric vehicles are registered in each
district, split by vehicle class, read from the government's VAHAN dashboard.

**A time series, never overwritten.** VAHAN publishes a *cumulative* count - the
running total of every EV ever registered - so a single reading carries no sense
of momentum, and PLAN 4.1 is emphatic that momentum is what matters ("weight the
12-month growth rate above absolute count"). Two things follow from that:

  * ``period`` names the window a row covers - a calendar year ("2024") for the
    year-on-year growth the model leans on, or "till_today" for the all-time
    cumulative. Storing per-year rows is what makes a growth rate computable at
    all.
  * ``snapshot_date`` is the capture vintage - when WE scraped it. A re-scrape
    next month is a NEW snapshot, not an overwrite, so the record only ever
    grows and an old report still sees the numbers it was built on.

**Tall, not wide.** One row per (district, snapshot, period, fuel, vehicle
class). VAHAN's category axis is open-ended - two-wheelers through buses and
heavy goods - and a wide table would need a migration every time the source adds
a column or we widen what we keep. A class is stored *verbatim* under its VAHAN
code so nothing is silently collapsed; "which classes count as commercial" is a
read-time decision, made where it can be seen, not baked into the schema.

**District, resolved from the RTO office coordinate.** VAHAN reports per RTO, not
per district; each RTO's office point is run through PLAN 1.4 once at ingest and
its counts are summed into that district (``rto_count`` records how many). NULL
district = the point could not be placed - the state is still known, so a
state-level total survives.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
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


class VahanEvRegistration(Base):
    __tablename__ = "vahan_ev_registrations"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    #: Resolved once on ingest via PLAN 1.4 from the RTO office coordinate.
    #: NULL = the point could not be placed in any district polygon.
    lgd_district_code: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("districts.lgd_district_code")
    )
    #: Known even when the district is not: it comes from the RTO's own state,
    #: not from the point-in-polygon step, so a state total never goes missing.
    lgd_state_code: Mapped[int | None] = mapped_column(Integer, ForeignKey("states.lgd_state_code"))

    #: When WE captured this from the portal. VAHAN carries no as-of date, so
    #: this is the reading's identity in the time series.
    snapshot_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    #: The window this count covers: a calendar year ("2024") for growth, or
    #: "till_today" for the all-time cumulative. Part of the identity so a
    #: snapshot can hold several years side by side.
    period: Mapped[str] = mapped_column(String(16), nullable=False)

    #: VAHAN fuel label, verbatim: "ELECTRIC(BOV)" or "PURE EV".
    fuel_category: Mapped[str] = mapped_column(String(24), nullable=False)
    #: VAHAN vehicle-category code, verbatim and uppercased: "2WN", "3WT",
    #: "LMV", "LPV", "LGV", "OMNI BUS", "HGV", ... or the row's "TOTAL". Kept raw
    #: so no class is silently folded away.
    vehicle_class: Mapped[str] = mapped_column(String(16), nullable=False)

    count: Mapped[int] = mapped_column(Integer, nullable=False)
    #: How many RTOs were summed into this district row. Transparency: a district
    #: served by four RTOs should say so.
    rto_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    #: sha256 of the scrape CSV this row was ingested from - provenance, so a
    #: figure can be traced back to the exact capture that produced it.
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # One row per (district, snapshot, period, fuel, class). nulls-not-
        # distinct so the unplaced-district bucket collapses to one row too,
        # keeping a same-day re-ingest idempotent rather than doubling it.
        UniqueConstraint(
            "lgd_district_code",
            "snapshot_date",
            "period",
            "fuel_category",
            "vehicle_class",
            name="uq_vahan_slice",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_vahan_district", "lgd_district_code"),
        Index("ix_vahan_state_period", "lgd_state_code", "period"),
    )
