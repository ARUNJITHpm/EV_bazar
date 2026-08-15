"""``competitor_stations`` - PART 2.3, the competitor inventory.

Every charging station we know about that is not a customer's candidate site:
who runs it, where, how powerful, and how public. This is the denominator for
"how much competition is within 3 km of this site", and - once the poller has
run - the join target for observed occupancy.

**A cache, not a ledger.** Upserted by ``(source, source_id)``: re-fetching a
station overwrites it in place, because the current state of a competitor is
what matters, not its edit history. Provenance (``source``, ``fetched_at``)
lives on the row. This is the same shape as ``geocode_cache``, and the opposite
of the poller's append-only archive - the distinction is deliberate (a
competitor's *availability over time* is the poller's job; its *existence and
specs* are this table's).

**``lgd_district_code`` is resolved on ingest, not joined at query time.** Each
station's point is run through PLAN 1.4 once when stored, so "competitors per
district" is an indexed integer lookup rather than a spatial join over every
row on every report. NULL means 1.4 refused the point (offshore, or outside
India) - kept, because a station we cannot place is still evidence the source
has coverage there.

**Occupancy is NOT here.** Open Charge Map and its kin carry a station's
*existence and an operational flag*, never live free/busy state. That flag is
recorded (``is_operational``) but it is a data-quality signal, not occupancy;
occupancy comes only from the poller (PART 0.1), and this row is what it will
attach to.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Boolean,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SRID = 4326
JsonColumn = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class CompetitorStation(Base):
    __tablename__ = "competitor_stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Where this row came from: "open_charge_map", later "chargezone" (poller),
    #: "plugshare", etc. Part of the identity so the same physical charger seen
    #: from two sources is two rows until PLAN 2.3 dedupes them downstream.
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    #: The source's own stable id for this station (OCM UUID). With ``source``,
    #: the upsert key.
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)

    name: Mapped[str | None] = mapped_column(Text)
    #: The network/operator, verbatim from the source ("Zeon Charging"). NULL
    #: when the source did not attribute it - common, and itself informative.
    operator: Mapped[str | None] = mapped_column(String(128))

    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[object | None] = mapped_column(
        Geometry("POINT", srid=SRID, spatial_index=False),
        Computed(f"ST_SetSRID(ST_MakePoint(lng, lat), {SRID})", persisted=True),
        nullable=True,
    )

    #: Resolved once on ingest via PLAN 1.4. NULL = the point could not be placed.
    lgd_district_code: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("districts.lgd_district_code")
    )
    lgd_state_code: Mapped[int | None] = mapped_column(Integer, ForeignKey("states.lgd_state_code"))
    town: Mapped[str | None] = mapped_column(String(128))
    postcode: Mapped[str | None] = mapped_column(String(12))

    #: public | private | membership | restricted - normalised from the source's
    #: usage-type vocabulary. Competition from a members-only depot is not the
    #: same threat as a public forecourt, so this is kept rather than flattened.
    access: Mapped[str | None] = mapped_column(String(16))

    #: The source's operational flag. A DATA-QUALITY signal ("this row is
    #: believed live"), NOT occupancy. See the module docstring.
    is_operational: Mapped[bool | None] = mapped_column(Boolean)

    #: Connectors and rated power, the two numbers a competitor comparison
    #: turns on. ``max_power_kw`` is denormalised for the "any DC fast within
    #: 3 km" filter; ``connectors`` keeps the full breakdown.
    number_of_points: Mapped[int | None] = mapped_column(Integer)
    max_power_kw: Mapped[float | None] = mapped_column(Float)
    #: [{"type": "CCS", "power_kw": 60, "quantity": 2}, ...] - as reported.
    connectors: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonColumn)

    #: The source's own provenance, kept so a stale or thin row is visible.
    data_provider: Mapped[str | None] = mapped_column(String(128))
    source_last_status_update: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    #: When WE last fetched it. The row's freshness, distinct from the source's.
    fetched_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_competitor_source"),
        Index("ix_competitor_geom", "geom", postgresql_using="gist"),
        Index("ix_competitor_district", "lgd_district_code"),
    )
