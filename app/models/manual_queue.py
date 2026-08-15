"""L6 of the geocoding cascade - the manual queue. PART 1.3.

    "L6 Manual queue: table + tiny Leaflet page, human clicks the point (~20s).
     Expect 3-8% in Tier 1."

This is the cascade's answer of last resort, and the reason the rest of it is
allowed to refuse. Every level above may return "I don't know" precisely
because there is somewhere for "I don't know" to go. Without this table the
pressure is always to accept the doubtful answer, which is how a report ends up
confidently wrong.

**One row per normalised address, not per request.** The same site pasted three
times is one job for a human. ``resolve`` writes the coordinates back into
``geocode_cache`` with ``source='manual'``, which is what makes the human's 20
seconds permanent - the next lookup of that address is a cache hit and never
reaches a geocoder again.
"""

from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

#: SQLite autoincrements only plain INTEGER primary keys, never BIGINT.
BigIntPk = BigInteger().with_variant(Integer(), "sqlite")


class QueueStatus(enum.StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    #: A human looked and could not place it either - a real outcome, and one
    #: worth counting separately from "nobody has looked yet".
    REJECTED = "rejected"


class GeocodeManualQueue(Base):
    __tablename__ = "geocode_manual_queue"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)

    #: ``NormalisedAddress.cache_key`` - the same key L1 is stored under, so a
    #: resolution here upserts exactly the cache row that missed.
    normalised_input: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)

    #: The address exactly as it arrived. The human needs this, not the
    #: normalised form - normalisation is what may have broken it.
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    pincode: Mapped[str | None] = mapped_column(String(6))

    #: Why the cascade gave up, in its own words - the ``reasons`` tuple joined.
    #: "Google and Nominatim disagree by 40 km" tells the human where to look;
    #: "unresolved" tells them nothing.
    reason: Mapped[str | None] = mapped_column(Text)

    #: How many times this address has been asked for. A queue sorted by this
    #: puts the twenty seconds where they buy the most.
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=QueueStatus.OPEN.value)

    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    #: Free text from the operator: which building, which entrance, why here.
    note: Mapped[str | None] = mapped_column(Text)

    resolved_by: Mapped[str | None] = mapped_column(String(64))
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # A resolved row without coordinates would be silently unusable by the
        # cache write-back, so the database refuses to hold one.
        CheckConstraint(
            "status <> 'resolved' OR (lat IS NOT NULL AND lng IS NOT NULL)",
            name="ck_manual_queue_resolved_has_point",
        ),
        Index("ix_manual_queue_status", "status", "hits"),
    )
