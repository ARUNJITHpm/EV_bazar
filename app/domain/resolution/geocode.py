"""The geocoding cascade. PART 1.3.

    normalise -> cache -> nominatim -> ola -> mappls -> google -> manual

This module wires the levels together. Its shape is the same as everywhere else
in this package: a **pure decision** (``classify_geocode`` - given the results,
what do we believe and how much) and a **thin I/O shell** (``geocode`` - run the
levels, read and write the cache).

**Stop at the first confident hit.** This is the property that makes the thing a
cascade rather than a fan-out, and it is what Part 1's "≥90% resolved without
touching Google" is measured against. Calling every level and keeping the first
answer would produce identical output and an unbounded bill.

**Escalate on doubt, not on failure alone.** A level that misses falls through -
that is ordinary. A level that *answers* but answers doubtfully (the matched PIN
contradicts the customer's, or the provider flags a partial match) is worth one
second opinion, and that is where PLAN 1.3's escalation rule finally bites: if
the two answers are more than 2 km apart we queue the address for a human
instead of picking a winner. Without this, a strict stop-at-first cascade never
has two opinions to compare and the rule is decoration.

Every paid level is wrapped in ``meter()`` before it reaches this module - see
``cascade.build_cascade`` and ``providers/metered.py``.
"""

from __future__ import annotations

import dataclasses
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
from app.domain.resolution.providers.base import Geocoder, GeocoderError, GeocodeResult
from app.metering import QuotaExceededError
from app.models.geocode import GeocodeCache

#: Metres. Two geocoders further apart than this are not rounding differences on
#: the same place; they found different places, and PLAN 1.3 says queue it rather
#: than pick one.
DEFAULT_DISAGREEMENT_M = 2000

#: How many opinions the cascade will ever hold at once. One working answer plus
#: one corroboration; a third would cost money to break a tie we have already
#: decided not to break (a disagreement goes to a human, not to a vote).
MAX_OPINIONS = 2


class GeocodeStatus(enum.StrEnum):
    HIT = "hit"  # a geocoder resolved it this run
    CACHED = "cached"  # served from L1 without a call
    MISS = "miss"  # no geocoder resolved it -> manual queue (L6)


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
    #: The matched address's own PIN, as the provider reported it. Each parser
    #: extracts this from its own response shape, so anything downstream reads
    #: one field instead of reaching into a provider-specific blob.
    #: NULL on a cache hit - ``geocode_cache`` does not store it, and the two
    #: better sources of a PIN (the customer's, and the polygon at the point)
    #: are both still available there.
    postcode: str | None = None
    #: The provider's own handle for the match: Mappls eLoc, Google place_id.
    place_id: str | None = None
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


def doubt_about(normalised: NormalisedAddress, result: GeocodeResult) -> str | None:
    """Why this answer is worth a second opinion, or None if it is not. Pure.

    Only *positive evidence* of a problem counts. "No PIN to check against" is
    not doubt - it is the normal case, and escalating on it would send almost
    every address to a paid level and defeat the cascade.
    """
    if result.partial:
        return (
            f"{result.source} flagged this a partial match - it matched something, "
            "but not what was asked for"
        )
    if normalised.pincode and result.postcode and result.postcode != normalised.pincode:
        return (
            f"{result.source} matched an address in PIN {result.postcode}, not the "
            f"supplied {normalised.pincode}"
        )
    return None


def _downgrade(confidence: Confidence) -> Confidence:
    """One step down, and it never recovers - the same rule as PLAN 1.4."""
    if confidence is Confidence.HIGH:
        return Confidence.MEDIUM
    return Confidence.LOW


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
            reasons=("no geocoder resolved this address; sending it to the manual queue",),
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
        reasons.append(f"{other.source} corroborates {chosen.source} to within {gap / 1000:.1f} km")

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

    # A partial match is a confident wrong answer waiting to happen, so it costs
    # a step even when everything else looked fine.
    if chosen.partial:
        confidence = _downgrade(confidence)
        reasons.append(
            f"{chosen.source} reported a partial match, so confidence drops to {confidence}"
        )

    return GeocodeOutcome(
        status=GeocodeStatus.HIT,
        normalised=normalised,
        lat=chosen.lat,
        lng=chosen.lng,
        source=chosen.source,
        confidence=confidence,
        display_name=chosen.display_name,
        postcode=chosen.postcode,
        place_id=chosen.place_id,
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
        place_id=row.provider_place_id,
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
    row.provider_place_id = outcome.place_id
    # The chosen geocoder's raw body, for later re-derivation without re-paying.
    row.raw_response = outcome.raw
    if now is not None:
        row.fetched_at = now
    session.flush()


def _run_levels(
    geocoders: Sequence[Geocoder],
    client: httpx.Client,
    normalised: NormalisedAddress,
    trail: list[str],
) -> list[GeocodeResult]:
    """Walk the cascade, cheapest first, and stop as soon as we are done.

    Returns at most ``MAX_OPINIONS`` results. Everything that goes wrong at a
    level is turned into a line in ``trail`` and the walk continues: a capped
    Google key must degrade to the manual queue, not fail the request.
    """
    results: list[GeocodeResult] = []

    for level in geocoders:
        try:
            hit = level.search(client, normalised.query, pincode=normalised.pincode)
        except QuotaExceededError as exc:
            # The refusal is our own, and meter() has already written a
            # `capped` row for it - so a cap looks different from an outage.
            trail.append(f"{level.source} skipped: {exc}")
            continue
        except (GeocoderError, httpx.HTTPError) as exc:
            trail.append(f"{level.source} failed: {exc.__class__.__name__}: {exc}")
            continue

        if hit is None:
            trail.append(f"{level.source} found nothing")
            continue

        results.append(hit)

        doubt = doubt_about(normalised, hit)
        if doubt is None:
            break  # confident: stop here rather than pay the next level
        if len(results) >= MAX_OPINIONS:
            break
        trail.append(f"escalating past {level.source}: {doubt}")

    return results


def geocode(
    session: Session,
    raw: str,
    *,
    geocoders: Sequence[Geocoder],
    client: httpx.Client,
    use_cache: bool = True,
    disagreement_limit_m: int = DEFAULT_DISAGREEMENT_M,
) -> GeocodeOutcome:
    """Run the cascade for one address.

    ``geocoders`` is the ordered level list from ``cascade.build_cascade``. The
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

    trail: list[str] = []
    results = _run_levels(geocoders, client, normalised, trail)

    outcome = classify_geocode(normalised, results, disagreement_limit_m=disagreement_limit_m)
    if trail:
        outcome = dataclasses.replace(outcome, reasons=tuple(trail) + outcome.reasons)

    if use_cache:
        cache_put(session, outcome)

    return outcome
