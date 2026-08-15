"""``sites`` - PART 1.5. The output of Part 1 and the input to everything else.

A site is *a place someone asked us about*, resolved as far as we honestly can.
Part 2 hangs road and POI features off it, Part 3 prices it against its
district's tariff, Part 5 renders it. So this table is the join between "a
customer typed an address" and every number the product produces.

Three decisions worth knowing about:

**``geom`` is generated, not stored.** ``GENERATED ALWAYS AS ... STORED`` from
``lat``/``lng``, so it cannot drift from them. A geometry column written
separately by application code is one UPDATE away from disagreeing with the
coordinates beside it, and nothing would notice until a spatial join returned
the wrong neighbourhood.

**An unresolved address is still a site.** PLAN 1.6: "tier > 1 -> waitlist
response, *but log the site anyway*". The same applies to an address no
geocoder could place - it is a lead, and it is the row the manual queue's
answer eventually lands in. So ``lat``, ``lng`` and the district codes are all
nullable, and ``resolved`` is derived rather than asserted.

**One row per distinct place, with a request counter.** Two customers pasting
the same address are one site asked about twice, not two sites - Part 2's
context features are expensive and there is nothing to recompute. The counter
is what makes a waitlisted district's demand visible (OVERVIEW section 4: the
waitlist is the expansion roadmap).
"""

from __future__ import annotations

import datetime as dt
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SRID = 4326


class Site(Base):
    __tablename__ = "sites"

    #: Client-visible. A UUID rather than a sequence because it appears in
    #: report URLs, and a sequential id there leaks how many sites exist.
    site_id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)

    #: Exactly as received. Kept because a normalisation we got wrong is only
    #: debuggable if the original survived - the same rule as the poller's raw
    #: archive and the manual queue.
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    #: ``NormalisedAddress.cache_key``. Unique: this is the site's identity, and
    #: it is also the join to ``geocode_cache`` and ``geocode_manual_queue``.
    normalised_input: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)

    #: NULL when no geocoder could place the address. The row still exists.
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)

    #: Derived from lat/lng by the database. Read-only from Python: assigning
    #: to it raises rather than silently doing nothing.
    geom: Mapped[object | None] = mapped_column(
        Geometry("POINT", srid=SRID, spatial_index=False),
        Computed(f"ST_SetSRID(ST_MakePoint(lng, lat), {SRID})", persisted=True),
        nullable=True,
    )

    lgd_state_code: Mapped[int | None] = mapped_column(Integer, ForeignKey("states.lgd_state_code"))
    #: The join key the whole system agrees on. NULL means Part 1 refused -
    #: overlapping source polygons, or nothing within 5 km.
    lgd_district_code: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("districts.lgd_district_code")
    )
    pincode: Mapped[str | None] = mapped_column(String(6))

    #: urban | rural. ⚠️ NULL for now: the built-up/town layer from PLAN 1.2 is
    #: not loaded, and guessing from district type would be wrong for exactly
    #: the peri-urban sites where the distinction changes the answer.
    urban_rural: Mapped[str | None] = mapped_column(String(8))

    #: Which cascade level produced the coordinates: nominatim | ola_maps |
    #: mappls | google_maps | manual.
    geocode_source: Mapped[str | None] = mapped_column(String(32))
    #: high | medium | low - the **weaker** of the cascade's confidence in the
    #: point and 1.4's confidence in the district. One number for the report;
    #: ``reasons`` says which step was the weak one.
    geocode_confidence: Mapped[str | None] = mapped_column(String(8))

    #: contained | nearest | pin_override | overlapping | rejected (PLAN 1.4).
    #: ⚠️ ``pin_override`` means the coordinates and the district disagree on
    #: purpose - Part 2 will compute road and POI features at a point that is
    #: NOT inside the district whose tariff Part 3 will charge it. That is the
    #: right call and it must stay visible.
    district_method: Mapped[str | None] = mapped_column(String(16))
    #: Another district within 500 m: two tariff regimes, and the report says so.
    boundary_ambiguous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    #: Every doubt, in the order it was decided - the assumption ledger the
    #: report prints (PLAN 5). Text rather than JSON because it is read by
    #: humans and never queried by structure.
    reasons: Mapped[str | None] = mapped_column(Text)

    #: ⚠️ NULL until PLAN 1.6 builds ``data_coverage``. A tier is a claim about
    #: what data we hold for a district, not a property of the site, and it is
    #: not this table's to invent.
    data_tier: Mapped[int | None] = mapped_column(Integer)

    #: How many times this place has been asked about. Demand for a district we
    #: do not serve yet is the expansion roadmap.
    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    first_requested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_requested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    #: When Part 1 last ran for this site. Distinct from ``last_requested_at``:
    #: a cached answer is a request without a resolution.
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_sites_geom", "geom", postgresql_using="gist"),
        Index("ix_sites_district", "lgd_district_code"),
        # "Which sites are we holding that we cannot yet serve" - the waitlist
        # query, and the one 1.6's tier gate will run.
        Index("ix_sites_tier", "data_tier", "lgd_district_code"),
    )

    @property
    def resolved(self) -> bool:
        """A site is resolved when it has a district, not merely a point.

        A coordinate with no district is useless downstream: no tariff, no
        competitor set, no report.
        """
        return self.lgd_district_code is not None

    @property
    def located(self) -> bool:
        """It has coordinates, whether or not they landed in a district."""
        return self.lat is not None and self.lng is not None
