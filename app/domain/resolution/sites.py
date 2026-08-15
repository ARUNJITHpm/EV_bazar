"""Address in, site row out. PART 1.5 - the seam where Part 1 becomes Part 2.

    raw text --1.3--> a coordinate --1.4--> a district --1.5--> a `sites` row

Nothing new is decided about geography here. What *is* decided is how two
independent verdicts combine into one row that a report can be built on, and
that is where the interesting mistake lives: the cascade says how sure it is of
the **point**, 1.4 says how sure it is of the **district**, and they are not the
same claim. A Google hit with a matching PIN (high) that lands 3 km outside
every polygon and resolves by nearest-fallback (low) is a low-confidence site,
not a high-confidence one.

So ``combine`` is pure, takes both verdicts, and keeps the weaker - one
downgrade per doubt, never recovering, exactly as 1.3 and 1.4 each do
internally. Both reason trails are concatenated, in cascade-then-district
order, because that is the order a human retraces them in.

``resolve_site`` is the shell: run the cascade, run the point-in-polygon, upsert.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.resolution.geocode import (
    DEFAULT_DISAGREEMENT_M,
    GeocodeOutcome,
    geocode,
)
from app.domain.resolution.geography import (
    DEFAULT_AMBIGUOUS_M,
    DEFAULT_MAX_FALLBACK_M,
    Confidence,
    Method,
    Resolution,
    resolve,
)
from app.domain.resolution.providers.base import Geocoder
from app.models.site import Site

#: Weakest last. Used only by ``_weaker``; a dict rather than relying on the
#: enum's declaration order, which is not a contract.
_RANK = {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.LOW: 1}


def _weaker(a: Confidence | None, b: Confidence | None) -> Confidence | None:
    """The less confident of two labels. ``None`` means "not claimed at all"
    and loses to everything, because an absent claim is not a strong one."""
    if a is None or b is None:
        return a if b is None else b
    return a if _RANK[a] <= _RANK[b] else b


@dataclass(frozen=True)
class SiteFacts:
    """Everything a ``sites`` row asserts, decided without touching a database."""

    lat: float | None = None
    lng: float | None = None
    lgd_state_code: int | None = None
    lgd_district_code: int | None = None
    pincode: str | None = None
    geocode_source: str | None = None
    confidence: Confidence | None = None
    district_method: Method | None = None
    boundary_ambiguous: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def located(self) -> bool:
        return self.lat is not None and self.lng is not None

    @property
    def resolved(self) -> bool:
        return self.lgd_district_code is not None


def choose_pincode(outcome: GeocodeOutcome, resolution: Resolution | None) -> str | None:
    """Which PIN the site records. Pure.

    Preference order, and each step is a judgement:

    1. **The PIN the customer supplied.** It came from a human who knows the
       place; a geocoder's postcode came from a match we are less sure of.
    2. The PIN polygon the point falls in, **but only if there is exactly one**.
       Several overlapping PIN polygons is India Post's delivery rounds showing
       through, and picking one of them would be inventing a fact.
    3. The matched address's own postcode. Last because it is the geocoder
       agreeing with itself: if the match was wrong, so is its PIN.
    """
    if outcome.normalised.pincode:
        return outcome.normalised.pincode
    if resolution is not None and len(resolution.pincode_at_point) == 1:
        return resolution.pincode_at_point[0]
    return outcome.postcode[:6] if outcome.postcode else None


def combine(outcome: GeocodeOutcome, resolution: Resolution | None) -> SiteFacts:
    """Fold the cascade's verdict and 1.4's verdict into one. Pure.

    ``resolution`` is ``None`` when the cascade never produced a coordinate to
    resolve - the site is a lead with no location, which is a real and expected
    state, not an error.
    """
    if not outcome.resolved or resolution is None:
        return SiteFacts(
            pincode=choose_pincode(outcome, None),
            reasons=outcome.reasons,
        )

    district = resolution.district
    return SiteFacts(
        lat=outcome.lat,
        lng=outcome.lng,
        lgd_state_code=district.lgd_state_code if district else None,
        lgd_district_code=district.lgd_district_code if district else None,
        pincode=choose_pincode(outcome, resolution),
        geocode_source=outcome.source,
        # The report shows one number, and it must be the weaker claim. A
        # perfectly geocoded point in an unresolvable district is not a
        # high-confidence site.
        confidence=_weaker(outcome.confidence, resolution.confidence),
        district_method=resolution.method,
        boundary_ambiguous=resolution.boundary_ambiguous,
        reasons=outcome.reasons + resolution.reasons,
    )


# ---------------------------------------------------------------------------
# The shell.
# ---------------------------------------------------------------------------


def get_site(session: Session, normalised_input: str) -> Site | None:
    return session.execute(
        select(Site).where(Site.normalised_input == normalised_input)
    ).scalar_one_or_none()


def upsert_site(
    session: Session,
    *,
    raw_input: str,
    normalised_input: str,
    facts: SiteFacts,
    now: dt.datetime | None = None,
) -> Site:
    """Create or update the site for this address.

    Re-resolution **overwrites** the geography: reference boundaries change,
    districts split, and a site must reflect the polygons we hold now. What is
    reproducible is not the old row but the old *inputs* - ``reference_layers``
    records which boundaries were loaded when, and the raw input is kept here.
    """
    moment = now or dt.datetime.now(dt.UTC)
    site = get_site(session, normalised_input)

    if site is None:
        site = Site(
            raw_input=raw_input,
            normalised_input=normalised_input,
            requests=1,
            first_requested_at=moment,
        )
        session.add(site)
    else:
        site.requests += 1

    site.last_requested_at = moment
    site.lat = facts.lat
    site.lng = facts.lng
    site.lgd_state_code = facts.lgd_state_code
    site.lgd_district_code = facts.lgd_district_code
    site.pincode = facts.pincode
    site.geocode_source = facts.geocode_source
    site.geocode_confidence = facts.confidence.value if facts.confidence else None
    site.district_method = facts.district_method.value if facts.district_method else None
    site.boundary_ambiguous = facts.boundary_ambiguous
    site.reasons = "\n".join(facts.reasons) or None
    # Only a run that actually placed the point counts as a resolution; a lead
    # we could not locate must not look freshly resolved.
    if facts.located:
        site.resolved_at = moment

    session.flush()
    return site


def resolve_site(
    session: Session,
    raw_input: str,
    *,
    geocoders: Sequence[Geocoder],
    client: httpx.Client,
    use_cache: bool = True,
    disagreement_limit_m: int = DEFAULT_DISAGREEMENT_M,
    max_fallback_m: int = DEFAULT_MAX_FALLBACK_M,
    ambiguous_m: int = DEFAULT_AMBIGUOUS_M,
    now: dt.datetime | None = None,
) -> tuple[Site, SiteFacts]:
    """Run all of Part 1 for one address and write the row.

    Returns the site and the facts behind it, so a caller that wants to explain
    the answer does not have to re-read it back out of the database.
    """
    outcome = geocode(
        session,
        raw_input,
        geocoders=geocoders,
        client=client,
        use_cache=use_cache,
        disagreement_limit_m=disagreement_limit_m,
    )

    resolution: Resolution | None = None
    if outcome.resolved and outcome.lat is not None and outcome.lng is not None:
        resolution = resolve(
            session,
            outcome.lat,
            outcome.lng,
            # The customer's PIN is the cross-check 1.4 was built around.
            expected_pincode=outcome.normalised.pincode,
            max_fallback_m=max_fallback_m,
            ambiguous_m=ambiguous_m,
        )

    facts = combine(outcome, resolution)
    site = upsert_site(
        session,
        raw_input=raw_input,
        normalised_input=outcome.normalised.cache_key,
        facts=facts,
        now=now,
    )
    return site, facts
