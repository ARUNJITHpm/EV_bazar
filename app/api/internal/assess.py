"""POST /assess - the funnel's front door. PLAN G.2.

A customer drops a pin and answers up to six taps; the response is the
breakeven utilisation that pin must clear, from pure arithmetic against the
state's typed tariff (``domain/report/teaser.py``). Every pin is logged as a
``sites`` row FIRST, whatever happens next - a pin we cannot price is a lead,
not a failure, and the waitlist it lands on is the expansion roadmap
(OVERVIEW.md §4).

The tier gate (PLAN 1.6) decides which of those two answers a pin gets:
``state_tier`` derives "how much do we know here" from the live tables, the
verdict is stamped on ``sites.data_tier`` (what we knew when the site was
asked about), and Tier 3 pins are waitlisted while still being logged.
Tier 1-2 pins get the teaser - Tier 2 is exactly the claim the teaser makes,
a breakeven number and nothing more.

Mounted on the OPEN group, and that is a decision, not an oversight: the
teaser is the top of the funnel and a customer holds no console login - the
same reasoning as the reports endpoint above it in ``__init__.py``.

Two honesty notes:

* The pin needs no geocoder (the customer placed the point themselves), so
  the site's combined confidence is simply 1.4's district confidence - the
  weaker-claim rule of ``sites.combine`` collapses when the point is given.
* The taps are echoed in the response and ride along in ``raw_input``
  on the lead's first sighting; a real lead schema (which tap answers, which
  contact) is Part 7's, decided by the 0.3 conversations. Until then this
  endpoint must not invent one.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.report.assemble import state_ev_tariff
from app.domain.report.teaser import Taps, compute_teaser
from app.domain.resolution.coverage import state_tier
from app.domain.resolution.geography import resolve
from app.domain.resolution.sites import SiteFacts, upsert_site

router = APIRouter()


class AssessIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    #: The design flow's taps, every one optional (the teaser's whole premise).
    #: "small" | "medium" | "large" - how much space, driving connector count.
    space: str | None = Field(default=None, max_length=16)
    #: An existing transformer's nameplate kVA, and the metres to it.
    transformer_kva: float | None = Field(default=None, gt=0, le=5_000)
    transformer_distance_m: float | None = Field(default=None, ge=0, le=5_000)
    #: What the owner wants the site to do (income / fleet / visitors) -
    #: echoed honestly as "changes the operator match, not this arithmetic".
    intent: str | None = Field(default=None, max_length=32)


class TapOut(BaseModel):
    label: str
    provided: bool
    effect: str


class TeaserOut(BaseModel):
    #: None means the margin is negative at the assumed price - "no
    #: utilisation breaks even" is an answer, and the notes say why.
    breakeven_utilisation: float | None
    breakeven_kwh_year: float | None
    breakeven_kwh_day: float | None
    connectors: int
    rated_kw_each: float
    selling_paise_per_kwh: int
    sanctioned_kva: float
    energy_tariff_paise_per_kwh: int
    tariff_source: str
    taps: list[TapOut]
    notes: list[str]


class AssessOut(BaseModel):
    site_id: uuid.UUID
    #: How many times this exact pin has been asked about - the counter that
    #: makes waitlisted demand visible.
    requests: int
    district: str | None
    state: str | None
    #: high | medium | low - 1.4's confidence in the district.
    confidence: str | None
    #: Another district within 500 m: two tariff regimes, said out loud.
    boundary_ambiguous: bool
    #: PLAN 1.6 - the gate. 1 = full report honest, 2 = breakeven + tariff
    #: audit honest, 3 = waitlist. None when the pin resolved to no district.
    tier: int | None
    tier_why: str | None
    waitlisted: bool
    waitlist_reason: str | None
    teaser: TeaserOut | None


@router.post("/assess", response_model=AssessOut)
def assess(body: AssessIn, session: Session = Depends(get_session)) -> AssessOut:
    resolution = resolve(session, body.lat, body.lng)
    district = resolution.district
    # The tier gate (PLAN 1.6): how much we know about this state, decided by
    # the same function the coverage panel displays.
    verdict = None if district is None else state_tier(session, district.lgd_state_code)

    taps = Taps(
        space=body.space,
        transformer_kva=body.transformer_kva,
        transformer_distance_m=body.transformer_distance_m,
        intent=body.intent,
    )

    # The lead row, before any pricing question is asked. 5 decimals ~ 1 m,
    # so the same spot clicked twice is one site asked about twice.
    site = upsert_site(
        session,
        raw_input=f"pin drop via /assess: {body.lat:.5f}, {body.lng:.5f}; taps={taps}",
        normalised_input=f"pin:{body.lat:.5f},{body.lng:.5f}",
        facts=SiteFacts(
            lat=body.lat,
            lng=body.lng,
            lgd_state_code=district.lgd_state_code if district else None,
            lgd_district_code=district.lgd_district_code if district else None,
            pincode=(
                resolution.pincode_at_point[0] if len(resolution.pincode_at_point) == 1 else None
            ),
            geocode_source="pin",
            confidence=resolution.confidence,
            district_method=resolution.method,
            boundary_ambiguous=resolution.boundary_ambiguous,
            reasons=("pin dropped by the customer on /assess",) + resolution.reasons,
        ),
    )
    # The 1.6 stamp: what we knew when this site was asked about, recorded the
    # same way its geocode confidence is. Re-asking re-stamps - coverage grows.
    site.data_tier = None if verdict is None else verdict.tier

    out = AssessOut(
        site_id=site.site_id,
        requests=site.requests,
        district=district.name if district else None,
        state=district.state_name if district else None,
        confidence=resolution.confidence.value,
        boundary_ambiguous=resolution.boundary_ambiguous,
        tier=None if verdict is None else verdict.tier,
        tier_why=None if verdict is None else verdict.why,
        waitlisted=False,
        waitlist_reason=None,
        teaser=None,
    )

    if district is None or verdict is None:
        out.waitlisted = True
        out.waitlist_reason = (
            "The pin could not be resolved to a district: "
            + (resolution.reasons[-1] if resolution.reasons else "no district within reach.")
            + " It is logged; a human will look."
        )
        return out

    if verdict.tier >= 3:
        out.waitlisted = True
        out.waitlist_reason = (
            f"{district.state_name} is Tier {verdict.tier}: {verdict.why}. "
            f"The pin is logged ({site.requests} request(s) for this spot); the waitlist "
            "decides which state's tariffs load next."
        )
        return out

    tariff_row = state_ev_tariff(session, district.lgd_state_code, dt.date.today())
    if tariff_row is None:
        # Tier 2 needs an effective tariff row; the teaser needs it to be the
        # EV-SPECIFIC one. A state with only a general schedule lands here.
        out.waitlisted = True
        out.waitlist_reason = (
            f"{district.state_name} has a tariff on file but not the EV-specific order, "
            "and pricing EV charging off the general schedule would be a guess. "
            f"The pin is logged ({site.requests} request(s) for this spot)."
        )
        return out

    teaser = compute_teaser(tariff_row, taps)
    out.teaser = TeaserOut(
        breakeven_utilisation=teaser.utilisation,
        breakeven_kwh_year=teaser.kwh_year,
        breakeven_kwh_day=teaser.kwh_day,
        connectors=teaser.connectors,
        rated_kw_each=teaser.rated_kw_each,
        selling_paise_per_kwh=teaser.selling_paise_per_kwh,
        sanctioned_kva=teaser.sanctioned_kva,
        energy_tariff_paise_per_kwh=teaser.energy_tariff_paise_per_kwh,
        tariff_source=teaser.tariff_source,
        taps=[TapOut(label=t.label, provided=t.provided, effect=t.effect) for t in teaser.taps],
        notes=list(teaser.notes),
    )
    return out
