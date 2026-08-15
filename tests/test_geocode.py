"""PART 1.3 - geocoding cascade, free levels (L0 normalise, L1 cache, L2 Nominatim).

The subtle failures all live in pure functions, so most of this needs no
database and no network:

  * normalise: the PIN must survive digit-stripping; spellings must collapse.
  * parse: a missing coordinate must become None, never a guessed point.
  * classify: two geocoders that disagree must be queued, not averaged.

The cache round-trip runs against in-memory SQLite via the JSON column variant.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.resolution import (
    Confidence,
    GeocodeResult,
    GeocodeStatus,
    NominatimGeocoder,
    classify_geocode,
    extract_pincode,
    geocode,
    haversine_m,
    normalise_address,
    parse_search,
)
from app.models import Base
from app.models.geocode import GeocodeCache

# --- L0 normalise ----------------------------------------------------------


def test_pincode_is_extracted_before_digits_are_stripped() -> None:
    n = normalise_address("MG Road, Kochi 682035")
    assert n.pincode == "682035"
    assert "682035" not in n.query
    assert n.query == "mg road kochi"


def test_pincode_is_not_plucked_from_a_phone_number() -> None:
    """A 10-digit mobile must not donate six of its digits as a PIN."""
    assert extract_pincode("call 9847012345 for directions") is None


def test_abbreviations_expand_and_proximity_words_are_dropped() -> None:
    n = normalise_address("opp Lulu Mall, MG Rd, Edappally Jn")
    assert "opp" not in n.query.split()
    assert "road" in n.query.split()
    assert "junction" in n.query.split()
    assert n.query == "lulu mall mg road edappally junction"


def test_spelling_variants_collapse_to_one_query() -> None:
    """The cache only pays off if these hit the same key."""
    assert normalise_address("Trivandrum").query == "thiruvananthapuram"
    assert normalise_address("Bangalore").query == "bengaluru"
    assert normalise_address("Calicut").query == "kozhikode"
    # A city is NOT collapsed onto its district - that would misdirect the query.
    assert normalise_address("Kochi").query == "kochi"


def test_diacritics_and_case_are_normalised() -> None:
    assert normalise_address("Bengalūru").query == "bengaluru"


def test_cache_key_separates_places_that_differ_only_by_pin() -> None:
    a = normalise_address("Gandhi Road 500001")
    b = normalise_address("Gandhi Road 682001")
    assert a.query == b.query
    assert a.cache_key != b.cache_key


def test_pin_only_input_is_not_empty() -> None:
    n = normalise_address("682001")
    assert n.query == ""
    assert n.pincode == "682001"
    assert n.is_empty is False


def test_truly_empty_input_is_flagged() -> None:
    assert normalise_address("!!!").is_empty is True


# --- L2 parse (pure) -------------------------------------------------------

NOMINATIM_BODY = [
    {
        "lat": "9.9312",
        "lon": "76.2673",
        "display_name": "MG Road, Kochi, Ernakulam, Kerala, India",
        "importance": 0.42,
        "address": {"postcode": "682035", "state": "Kerala"},
    }
]


def test_parse_takes_the_top_hit_with_its_postcode() -> None:
    r = parse_search(NOMINATIM_BODY)
    assert r is not None
    assert (round(r.lat, 4), round(r.lng, 4)) == (9.9312, 76.2673)
    assert r.postcode == "682035"
    assert r.source == "nominatim"


@pytest.mark.parametrize(
    "body",
    [[], {}, "nope", [{}], [{"lat": "bad", "lon": "76.2"}], [{"lon": "76.2"}]],
)
def test_parse_returns_none_rather_than_a_guessed_point(body: object) -> None:
    assert parse_search(body) is None


# --- L2 fetch (mock transport) ---------------------------------------------


def test_nominatim_constrains_to_india_and_keeps_the_pin_out_of_a_text_query() -> None:
    """The live API returns 400 for ``q`` combined with ``postalcode``
    (FINDINGS D14 - found on the first real call, exactly as G1 predicted).
    With a text query the PIN must stay out of the request; the cross-check
    happens downstream in ``doubt_about`` and 1.4."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=NOMINATIM_BODY)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    r = NominatimGeocoder("http://nominatim.test").search(client, "mg road kochi", pincode="682035")

    assert r is not None
    assert seen["countrycodes"] == "in"
    assert seen["q"] == "mg road kochi"
    assert "postalcode" not in seen


def test_nominatim_uses_the_pin_as_a_structured_filter_when_it_is_all_we_have() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=NOMINATIM_BODY)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    r = NominatimGeocoder("http://nominatim.test").search(client, "", pincode="682001")

    assert r is not None
    assert seen["postalcode"] == "682001"
    assert "q" not in seen


def test_nominatim_sends_an_identifying_user_agent() -> None:
    """The public instance's policy bans anonymous default agents; an
    unidentified client gets blocked, which would look like an outage."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("user-agent", "")
        return httpx.Response(200, json=NOMINATIM_BODY)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    NominatimGeocoder("http://nominatim.test").search(client, "kochi")
    assert "EVSiteIntelligence" in seen["ua"]
    assert "python-httpx" not in seen["ua"]


def test_nominatim_empty_result_is_a_clean_miss() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=[])))
    assert NominatimGeocoder("http://nominatim.test").search(client, "nowhere") is None


# --- classify (pure) -------------------------------------------------------


def _result(lat: float, lng: float, *, source: str = "nominatim", postcode: str | None = None):
    return GeocodeResult(lat=lat, lng=lng, source=source, postcode=postcode)


def test_no_results_goes_to_the_manual_queue() -> None:
    out = classify_geocode(normalise_address("nowhere at all"), [])
    assert out.status is GeocodeStatus.MISS
    assert not out.resolved


def test_a_single_hit_without_a_pin_is_medium() -> None:
    out = classify_geocode(normalise_address("mg road kochi"), [_result(9.93, 76.26)])
    assert out.status is GeocodeStatus.HIT
    assert out.confidence is Confidence.MEDIUM


def test_a_matching_pin_lifts_confidence_to_high() -> None:
    out = classify_geocode(
        normalise_address("mg road kochi 682035"), [_result(9.93, 76.26, postcode="682035")]
    )
    assert out.confidence is Confidence.HIGH


def test_a_conflicting_pin_drops_confidence_to_low() -> None:
    out = classify_geocode(
        normalise_address("mg road kochi 682035"), [_result(9.93, 76.26, postcode="600001")]
    )
    assert out.confidence is Confidence.LOW


def test_geocoders_that_disagree_by_more_than_2km_are_queued() -> None:
    """PLAN 1.3 escalation: do not pick one, do not average - queue it."""
    a = _result(9.9312, 76.2673, source="nominatim")
    b = _result(12.9716, 77.5946, source="google")  # Bengaluru, ~360 km away
    out = classify_geocode(normalise_address("mg road"), [a, b])
    assert out.status is GeocodeStatus.MISS
    assert "disagree" in out.reasons[0]


def test_geocoders_that_agree_resolve() -> None:
    a = _result(9.9312, 76.2673)
    b = _result(9.9320, 76.2680, source="google")  # ~100 m apart
    out = classify_geocode(normalise_address("mg road"), [a, b])
    assert out.status is GeocodeStatus.HIT


def test_haversine_is_about_right() -> None:
    assert haversine_m(0, 0, 0, 0) == 0.0
    # One degree of latitude is ~111.2 km anywhere.
    assert 110_000 < haversine_m(0, 0, 1, 0) < 112_000


# --- L1 cache round-trip (SQLite) ------------------------------------------


class _FakeGeocoder:
    """Answers once with a fixed result, and counts its calls so the test can
    prove the second lookup never reached it."""

    source = "nominatim"

    def __init__(self, result: GeocodeResult | None) -> None:
        self.result = result
        self.calls = 0

    def search(
        self, client: object, query: str, *, pincode: str | None = None
    ) -> GeocodeResult | None:
        self.calls += 1
        return self.result


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[GeocodeCache.__table__])
    with Session(engine) as s:
        yield s


def test_a_hit_is_cached_and_served_without_a_second_call(session: Session) -> None:
    g = _FakeGeocoder(GeocodeResult(9.9312, 76.2673, "nominatim", postcode="682035"))
    client = httpx.Client()

    first = geocode(session, "MG Road Kochi 682035", geocoders=[g], client=client)
    assert first.status is GeocodeStatus.HIT
    assert g.calls == 1

    second = geocode(session, "MG Road Kochi 682035", geocoders=[g], client=client)
    assert second.status is GeocodeStatus.CACHED
    assert second.lat == 9.9312
    assert g.calls == 1  # the geocoder was not called again


def test_the_full_raw_response_is_stored(session: Session) -> None:
    raw = {"lat": "9.93", "lon": "76.26", "display_name": "x", "address": {"postcode": "682035"}}
    g = _FakeGeocoder(GeocodeResult(9.93, 76.26, "nominatim", postcode="682035", raw=raw))
    geocode(session, "MG Road Kochi", geocoders=[g], client=httpx.Client())

    row = session.get(GeocodeCache, normalise_address("MG Road Kochi").cache_key)
    assert row is not None and row.raw_response == raw


def test_a_miss_is_cached_so_it_is_not_reasked(session: Session) -> None:
    g = _FakeGeocoder(None)
    client = httpx.Client()

    first = geocode(session, "somewhere unfindable", geocoders=[g], client=client)
    assert first.status is GeocodeStatus.MISS
    assert g.calls == 1

    second = geocode(session, "somewhere unfindable", geocoders=[g], client=client)
    assert second.status is GeocodeStatus.MISS
    assert g.calls == 1  # cached miss, no re-ask


def test_an_empty_address_never_calls_a_geocoder(session: Session) -> None:
    g = _FakeGeocoder(GeocodeResult(1.0, 1.0, "nominatim"))
    out = geocode(session, "!!!", geocoders=[g], client=httpx.Client())
    assert out.status is GeocodeStatus.MISS
    assert g.calls == 0
