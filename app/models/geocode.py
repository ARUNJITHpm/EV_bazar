"""L1 of the geocoding cascade - the geocode cache. PART 1.3.

    "L1 Cache: geocode_cache(normalised_input PK, lat, lng, source, confidence,
     raw_response JSONB, fetched_at) - store the FULL raw JSON, not just lat/lng."

Why the full blob and not just the coordinates: a geocoder returns the matched
address, its type, its bounding box and an importance score, and a month from
now we will want to re-derive confidence from those without paying for the call
again. Throwing them away at write time is not recoverable - the same mistake
the poller's raw archive exists to avoid.

**Misses are cached too**, with ``lat`` NULL. A place that no free geocoder can
find is a place we should not re-ask on every retry; the row records that we
looked. When a human resolves it through the manual queue (L6), that write
upserts the same key with ``source = 'manual'`` and real coordinates.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import JSON, DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

#: JSONB in Postgres, plain JSON on SQLite so the cache tests need no database.
#: ``none_as_null`` keeps "no payload" a SQL NULL rather than the JSON value
#: ``null`` - the same distinction the metering table draws.
JsonColumn = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class GeocodeCache(Base):
    """One normalised address -> its geocode, hit or miss.

    Keyed on the normalised input (``NormalisedAddress.cache_key``), so trivial
    spelling differences collapse onto one row and the expensive cascade runs
    once per genuinely distinct place.
    """

    __tablename__ = "geocode_cache"

    #: ``NormalisedAddress.cache_key`` - query text plus PIN.
    normalised_input: Mapped[str] = mapped_column(String(512), primary_key=True)

    #: NULL for a cached miss (no geocoder resolved it).
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)

    #: Which cascade level produced this: nominatim | ola | mappls | google |
    #: manual. A cached miss carries the level that last failed to resolve it.
    source: Mapped[str] = mapped_column(String(32), nullable=False)

    #: high | medium | low - the same label vocabulary as district resolution.
    #: NULL on a miss.
    confidence: Mapped[str | None] = mapped_column(String(8))

    #: The geocoder's own matched-address string, for eyeballing in the console.
    display_name: Mapped[str | None] = mapped_column(Text)

    #: The complete provider response. ALWAYS kept (see module docstring).
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn)

    fetched_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    @property
    def is_hit(self) -> bool:
        return self.lat is not None and self.lng is not None
