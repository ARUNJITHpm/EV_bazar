"""The geocoding cascade. PART 1.3.

    normalise -> cache -> nominatim -> [ola -> mappls -> google] -> manual

This module wires the levels together. Its shape is the same as everywhere else
in this package: a **pure decision** (``classify_geocode`` - given the results,
what do we believe and how much) and a **thin I/O shell** (``geocode`` - run the
levels, read and write the cache).

Only the free levels are wired here: L0 normalise, L1 cache, L2 Nominatim.
L3-L5 are paid and gated by the cap-before-boot guard in ``config.py``; they
slot in as more entries in the ``geocoders`` list, each wrapped in ``meter()``.
Until then, anything Nominatim cannot resolve becomes a ``MISS`` for the manual
queue (L6), which is honest: refusing to guess is the whole design.

The escalation rule from PLAN 1.3 - "two geocoders disagreeing by > 2 km, do not
pick one, queue it" - lives in ``classify_geocode`` already, so it starts
working the moment a second geocoder is added; with only Nominatim there is
never anything to disagree with.
"""

from __future__ import annotations

import datetime as dt
import enum
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.domain.resolution.geography import Confidence
from app.domain.resolution.normalise import NormalisedAddress, normalise_address
from app.domain.resolution.providers.nominatim import GeocodeResult, NominatimGeocoder
from app.models.geocode import GeocodeCache

#: Metres. Two geocoders further apart than this are not rounding differences on
#: the same place; they found different places, and PLAN 1.3 says queue it rather
#: than pick one.
DEFAULT_DISAGREEMENT_M = 2000


class GeocodeStatus(enum.StrEnum):
    HIT = "hit"  # a geocoder resolved it this run
    CACHED = "cached"  # served from L1 without a call
    MISS = "miss"  # no free geocoder resolved it -> manual queue (L6)


@dataclass(frozen=True)
class GeocodeOutcome:
    """A coordinate, its provenance, and how sure we are - ready for the report."""

    status: GeocodeStatus
    normalised: NormalisedAddress

    lat: float | None = None
    lng: float | None = None
    source: str | None = None
    confidence: Confidence | None = None
    display_name: str | None = None
    #: The chosen geocoder's full response body, kept so confidence can be
    #: re-derived later without paying for the call again (see GeocodeCache).
    raw: dict[str, Any] | None = None

    #: In the order they were decided; feeds the assumption ledger (PLAN 5).
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def resolved(self) -> bool:
        return self.lat is not None and self.lng is not None


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres. Pure.

    Good to a fraction of a percent at city scale, which is all the disagreement
    check needs - it is deciding "same place or not", not surveying.
    """
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def classify_geocode(
    normalised: NormalisedAddress,
    results: Sequence[GeocodeResult],
    *,
    disagreement_limit_m: int = DEFAULT_DISAGREEMENT_M,
) -> GeocodeOutcome:
    """Decide what to believe from the geocoders that answered. Pure.

    ``results`` is in cascade order (cheapest first). The first is the working
    answer; any later one is only consulted to see whether it *disagrees*.
    """
    reasons: list[str] = []

    if not results:
        return GeocodeOutcome(
            status=GeocodeStatus.MISS,
            normalised=normalised,
            reasons=("no free geocoder resolved this address; sending it to the manual queue",),
        )

    chosen = results[0]

    # --- escalation: a later geocoder found a materially different place -----
    for other in results[1:]:
        gap = haversine_m(chosen.lat, chosen.lng, other.lat, other.lng)
        if gap > disagreement_limit_m:
            return GeocodeOutcome(
                status=GeocodeStatus.MISS,
                normalised=normalised,
                reasons=(
                    f"{chosen.source} and {other.source} disagree by {gap / 1000:.1f} km "
                    f"(> {disagreement_limit_m / 1000:.0f} km); PLAN 1.3 says queue it rather "
                    "than pick one",
                ),
            )

    # --- confidence: corroborate with the customer's PIN when we have one ----
    confidence = Confidence.MEDIUM
    if normalised.pincode and chosen.postcode:
        if chosen.postcode == normalised.pincode:
            confidence = Confidence.HIGH
            reasons.append(
                f"matched address PIN {chosen.postcode} agrees with the supplied "
                f"{normalised.pincode}"
            )
        else:
            confidence = Confidence.LOW
            reasons.append(
                f"matched address PIN {chosen.postcode} disagrees with the supplied "
                f"{normalised.pincode}; the point-in-polygon step will decide (PLAN 1.4)"
            )
    else:
        reasons.append(
            f"resolved by {chosen.source}; no PIN to corroborate, so confidence is medium"
        )

    return GeocodeOutcome(
        status=GeocodeStatus.HIT,
        normalised=normalised,
        lat=chosen.lat,
        lng=chosen.lng,
        source=chosen.source,
        confidence=confidence,
        display_name=chosen.display_name,
        raw=chosen.raw,
        reasons=tuple(reasons),
    )


# ---------------------------------------------------------------------------
# The I/O shell. All judgement is above; this only reads/writes and calls out.
# ---------------------------------------------------------------------------


def cache_get(session: Session, key: str) -> GeocodeCache | None:
    return session.get(GeocodeCache, key)


def _outcome_from_cache(row: GeocodeCache, normalised: NormalisedAddress) -> GeocodeOutcome:
    if not row.is_hit:
        return GeocodeOutcome(
            status=GeocodeStatus.MISS,
            normalised=normalised,
            reasons=(
                f"cached miss from {row.source}; still unresolved, still for the manual queue",
            ),
        )
    return GeocodeOutcome(
        status=GeocodeStatus.CACHED,
        normalised=normalised,
        lat=row.lat,
        lng=row.lng,
        source=row.source,
        confidence=Confidence(row.confidence) if row.confidence else None,
        display_name=row.display_name,
        reasons=(f"served from cache ({row.source})",),
    )


def cache_put(session: Session, outcome: GeocodeOutcome, *, now: dt.datetime | None = None) -> None:
    """Upsert the outcome, hit or miss. Overwrites in place - a manual
    resolution later replaces a cached miss on the same key."""
    row = session.get(GeocodeCache, outcome.normalised.cache_key)
    if row is None:
        row = GeocodeCache(normalised_input=outcome.normalised.cache_key)
        session.add(row)
    row.lat = outcome.lat
    row.lng = outcome.lng
    row.source = outcome.source or "nominatim"
    row.confidence = outcome.confidence.value if outcome.confidence else None
    row.display_name = outcome.display_name
    # The chosen geocoder's raw body, for later re-derivation without re-paying.
    row.raw_response = outcome.raw
    if now is not None:
        row.fetched_at = now
    session.flush()


def geocode(
    session: Session,
    raw: str,
    *,
    geocoders: Sequence[NominatimGeocoder],
    client: httpx.Client,
    use_cache: bool = True,
    disagreement_limit_m: int = DEFAULT_DISAGREEMENT_M,
) -> GeocodeOutcome:
    """Run the cascade for one address.

    ``geocoders`` is the ordered free-level list (currently just Nominatim). The
    HTTP ``client`` is passed in so the caller controls its lifetime and so tests
    can hand in a mock transport.
    """
    normalised = normalise_address(raw)

    if normalised.is_empty:
        return GeocodeOutcome(
            status=GeocodeStatus.MISS,
            normalised=normalised,
            reasons=("nothing to geocode - no place name and no PIN in the input",),
        )

    if use_cache:
        cached = cache_get(session, normalised.cache_key)
        if cached is not None:
            return _outcome_from_cache(cached, normalised)

    results: list[GeocodeResult] = []
    for g in geocoders:
        hit = g.search(client, normalised.query, pincode=normalised.pincode)
        if hit is not None:
            results.append(hit)

    outcome = classify_geocode(normalised, results, disagreement_limit_m=disagreement_limit_m)

    if use_cache:
        cache_put(session, outcome)

    return outcome
