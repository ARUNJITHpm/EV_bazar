"""PART 1.5 - folding two verdicts into one site row.

``sites`` carries a PostGIS geometry column, so the table cannot be created on
SQLite and the round-trip is verified against live Postgres instead (see
``scripts/resolve_site.py --selftest``). That costs nothing here, because all
the judgement in 1.5 is in ``combine`` and ``choose_pincode`` - both pure, both
tested exhaustively below. The database part is an upsert.

The test that matters most is
``test_a_perfect_geocode_in_an_unresolvable_district_is_not_high_confidence``.
The cascade and the point-in-polygon step make *different claims* - "this is
the right point" and "this is the right district" - and the tempting shortcut
is to report the geocoder's number, which is the one that will usually be
higher and is not the one the report depends on.
"""

from __future__ import annotations

import pytest

from app.domain.resolution import (
    Confidence,
    DistrictHit,
    GeocodeOutcome,
    GeocodeStatus,
    Method,
    Resolution,
    SiteFacts,
    choose_pincode,
    combine,
    normalise_address,
)

ERNAKULAM = DistrictHit(
    lgd_district_code=304, lgd_state_code=32, name="Ernakulam", state_name="Kerala"
)
THRISSUR = DistrictHit(
    lgd_district_code=310, lgd_state_code=32, name="Thrissur", state_name="Kerala"
)


def hit(
    address: str = "MG Road Kochi 682035",
    *,
    confidence: Confidence = Confidence.HIGH,
    lat: float = 9.9312,
    lng: float = 76.2673,
    source: str = "nominatim",
    **kw: object,
) -> GeocodeOutcome:
    return GeocodeOutcome(
        status=GeocodeStatus.HIT,
        normalised=normalise_address(address),
        lat=lat,
        lng=lng,
        source=source,
        confidence=confidence,
        reasons=("geocoded",),
        **kw,  # type: ignore[arg-type]
    )


def miss(address: str = "behind the old tyre shop") -> GeocodeOutcome:
    return GeocodeOutcome(
        status=GeocodeStatus.MISS,
        normalised=normalise_address(address),
        reasons=("no geocoder resolved this address",),
    )


def district(
    *,
    confidence: Confidence = Confidence.HIGH,
    method: Method = Method.CONTAINED,
    hit_: DistrictHit | None = ERNAKULAM,
    **kw: object,
) -> Resolution:
    return Resolution(
        method=method,
        confidence=confidence,
        district=hit_,
        reasons=("point-in-polygon",),
        **kw,  # type: ignore[arg-type]
    )


# --- the combination rule ---------------------------------------------------


def test_two_confident_verdicts_make_a_confident_site() -> None:
    facts = combine(hit(), district())
    assert facts.resolved
    assert facts.confidence is Confidence.HIGH
    assert facts.lgd_district_code == 304
    assert facts.lgd_state_code == 32


def test_a_perfect_geocode_in_an_unresolvable_district_is_not_high_confidence() -> None:
    """The two steps claim different things, and the report needs the weaker.

    A Google hit whose PIN matches (high) that lands 3 km outside every polygon
    and resolves by nearest-fallback (low) is a low-confidence site.
    """
    facts = combine(
        hit(confidence=Confidence.HIGH),
        district(confidence=Confidence.LOW, method=Method.NEAREST),
    )
    assert facts.confidence is Confidence.LOW


def test_a_shaky_geocode_in_a_clean_district_is_also_downgraded() -> None:
    """...and it works the other way round, which a naive `min` on the wrong
    field would get right by accident and for the wrong reason."""
    facts = combine(hit(confidence=Confidence.LOW), district(confidence=Confidence.HIGH))
    assert facts.confidence is Confidence.LOW


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (Confidence.HIGH, Confidence.MEDIUM, Confidence.MEDIUM),
        (Confidence.MEDIUM, Confidence.HIGH, Confidence.MEDIUM),
        (Confidence.MEDIUM, Confidence.LOW, Confidence.LOW),
        (Confidence.HIGH, Confidence.HIGH, Confidence.HIGH),
    ],
)
def test_the_weaker_label_always_wins(a: Confidence, b: Confidence, expected: Confidence) -> None:
    assert combine(hit(confidence=a), district(confidence=b)).confidence is expected


def test_both_reason_trails_survive_in_order() -> None:
    """The assumption ledger is retraced cascade-first, then district."""
    facts = combine(hit(), district())
    assert facts.reasons == ("geocoded", "point-in-polygon")


# --- the states that are not the happy path ---------------------------------


def test_an_address_nobody_could_place_is_still_a_site() -> None:
    """PLAN 1.6: log the site anyway. It is a lead, and it is the row the
    manual queue's answer eventually lands in."""
    facts = combine(miss(), None)
    assert not facts.located
    assert not facts.resolved
    assert facts.confidence is None
    assert facts.reasons == ("no geocoder resolved this address",)


def test_a_point_in_no_district_keeps_its_coordinates_but_claims_nothing() -> None:
    """Overlapping source polygons: 1.4 refuses, and 1.5 must not paper over it
    by falling back to the coordinates' state."""
    facts = combine(
        hit(), district(method=Method.OVERLAPPING, hit_=None, confidence=Confidence.LOW)
    )
    assert facts.located
    assert not facts.resolved
    assert facts.lgd_state_code is None
    assert facts.district_method is Method.OVERLAPPING


def test_a_pin_override_is_recorded_as_such() -> None:
    """The coordinates and the district disagree on purpose. Part 2 computes
    road and POI features at a point that is NOT inside the district Part 3
    will charge it against, so the method has to stay visible."""
    facts = combine(
        hit(),
        district(
            method=Method.PIN_OVERRIDE,
            confidence=Confidence.LOW,
            hit_=THRISSUR,
            pin_conflict=True,
        ),
    )
    assert facts.district_method is Method.PIN_OVERRIDE
    assert facts.lgd_district_code == 310
    assert (facts.lat, facts.lng) == (9.9312, 76.2673)  # still Kochi's point


def test_boundary_ambiguity_carries_through_to_the_row() -> None:
    facts = combine(hit(), district(boundary_ambiguous=True, confidence=Confidence.MEDIUM))
    assert facts.boundary_ambiguous is True


def test_an_unclaimed_confidence_loses_to_a_claimed_one() -> None:
    """An absent claim is not a strong one."""
    facts = combine(hit(confidence=None), district(confidence=Confidence.HIGH))  # type: ignore[arg-type]
    assert facts.confidence is Confidence.HIGH
    facts = combine(hit(confidence=Confidence.HIGH), district(confidence=None))  # type: ignore[arg-type]
    assert facts.confidence is Confidence.HIGH


# --- which PIN the site records ---------------------------------------------


def test_the_customers_pin_beats_the_polygon() -> None:
    """It came from a human who knows the place."""
    facts = combine(hit("MG Road Kochi 682035"), district(pincode_at_point=("682011",)))
    assert facts.pincode == "682035"


def test_a_single_polygon_pin_is_taken_when_the_customer_gave_none() -> None:
    facts = combine(hit("MG Road Kochi"), district(pincode_at_point=("682011",)))
    assert facts.pincode == "682011"


def test_several_overlapping_pin_polygons_yield_no_pin_rather_than_a_guess() -> None:
    """India Post defines delivery rounds, not areas. Picking one of three
    would be inventing a fact about the site."""
    facts = combine(hit("MG Road Kochi"), district(pincode_at_point=("682011", "682016")))
    assert facts.pincode is None


def test_the_matched_addresss_own_postcode_is_the_last_resort() -> None:
    """Read off ``GeocodeOutcome.postcode``, which each parser fills from its
    own response shape - not by reaching into a provider-specific raw blob."""
    outcome = hit("MG Road Kochi", postcode="682035")
    assert choose_pincode(outcome, district()) == "682035"


def test_the_polygon_beats_the_geocoders_own_postcode() -> None:
    """A PIN from the geocoder is the geocoder agreeing with itself: if the
    match was wrong, so is its PIN. The polygon at the point is independent."""
    outcome = hit("MG Road Kochi", postcode="600001")
    assert choose_pincode(outcome, district(pincode_at_point=("682011",))) == "682011"


def test_facts_default_to_claiming_nothing() -> None:
    """A default-constructed SiteFacts must not look like a resolved site."""
    facts = SiteFacts()
    assert not facts.located and not facts.resolved
    assert facts.confidence is None and facts.boundary_ambiguous is False
