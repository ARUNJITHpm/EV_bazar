"""PART 1.3 - the paid levels (L3 Ola, L4 Mappls, L5 Google) and the cascade.

Three families of failure are worth a test here, and only one of them is
"does the parser read the JSON".

**Money.** A cascade that calls every level costs four times what a cascade
that stops at the first confident answer costs, and produces identical output -
so nothing but a test distinguishes them. ``test_a_confident_free_hit_never_
reaches_a_paid_level`` is the one that fails loudly if someone "simplifies"
the loop.

**A bad key must not be cached as a bad address.** Google returns HTTP 200 for
``REQUEST_DENIED``. Reading ``results`` and finding it empty would write a
cached miss for every address asked while the key was revoked, and the cache
does not expire.

**Metering.** AGENTS.md constraint 10: no paid call without a usage row. The
tests assert the row exists for a hit, for an error, and for a refusal at cap -
the last one being the case where no call was made at all and the row is the
only evidence the demand existed.
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import PaidProvider, Settings
from app.domain.resolution import (
    Confidence,
    GeocoderError,
    GeocodeResult,
    GeocodeStatus,
    GoogleGeocoder,
    MapplsGeocoder,
    MeteredGeocoder,
    OlaGeocoder,
    build_cascade,
    classify_geocode,
    doubt_about,
    geocode,
    normalise_address,
)
from app.domain.resolution.providers import google as google_mod
from app.domain.resolution.providers import mappls as mappls_mod
from app.domain.resolution.providers import ola as ola_mod
from app.metering import PriceCard
from app.metering.cards import PriceCardMissingError, seed_price_cards
from app.models import Base
from app.models.api_usage import ApiUsageEvent, UsageStatus
from app.models.geocode import GeocodeCache
from app.models.price_cards import ProviderPriceCard

CARD = PriceCard(version="test-geocode-v1", micro_paise_per_unit_in=44_000_000)  # 44 paise
KEYED = PaidProvider(api_key="k", monthly_cap=1000, console_cap_confirmed=True)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            ApiUsageEvent.__table__,
            GeocodeCache.__table__,
            ProviderPriceCard.__table__,
        ],
    )
    with Session(engine) as s:
        yield s


def usage(session: Session) -> list[ApiUsageEvent]:
    return list(session.execute(select(ApiUsageEvent)).scalars())


def transport(handler) -> httpx.Client:  # noqa: ANN001
    return httpx.Client(transport=httpx.MockTransport(handler))


# --- L3 Ola ----------------------------------------------------------------

OLA_BODY = {
    "status": "ok",
    "geocodingResults": [
        {
            "formatted_address": "MG Road, Kochi, Kerala 682035, India",
            "geometry": {"location": {"lat": 9.9312, "lng": 76.2673}},
            "address_components": [{"types": ["postal_code"], "long_name": "682035"}],
            "place_id": "ola-abc123",
        }
    ],
}


def test_ola_reads_the_top_hit_with_its_postcode() -> None:
    r = ola_mod.parse_geocode(OLA_BODY)
    assert r is not None
    assert (round(r.lat, 4), round(r.lng, 4)) == (9.9312, 76.2673)
    assert r.postcode == "682035"
    assert r.place_id == "ola-abc123"
    assert r.source == "ola_maps"


def test_ola_zero_results_is_a_clean_miss() -> None:
    assert ola_mod.parse_geocode({"status": "zero_results", "geocodingResults": []}) is None


def test_ola_an_unrecognised_status_raises_rather_than_missing() -> None:
    with pytest.raises(GeocoderError):
        ola_mod.parse_geocode({"status": "invalid_api_key", "error_message": "bad key"})


def test_ola_sends_the_pin_and_the_key() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=OLA_BODY)

    with transport(handler) as client:
        r = OlaGeocoder("secret-key").search(client, "mg road kochi", pincode="682035")

    assert r is not None
    assert seen["api_key"] == "secret-key"
    assert "682035" in seen["address"]


# --- L4 Mappls -------------------------------------------------------------

MAPPLS_ONE = {
    "responseCode": 200,
    "copResults": {
        "eLoc": "ABC123",
        "formattedAddress": "MG Road, Kochi, Kerala",
        "latitude": "9.9312",
        "longitude": "76.2673",
        "pincode": "682035",
    },
}


def test_mappls_stores_the_eloc() -> None:
    """PLAN 1.3 L4 asks for it by name - it is a free re-fetch handle."""
    r = mappls_mod.parse_geocode(MAPPLS_ONE)
    assert r is not None
    assert r.place_id == "ABC123"
    assert r.postcode == "682035"


def test_mappls_handles_the_list_shape_as_well_as_the_object() -> None:
    """copResults is an object for one match and a list for several. Treating
    the object as a list silently loses every single-match geocode."""
    body = {"responseCode": 200, "copResults": [MAPPLS_ONE["copResults"]]}
    r = mappls_mod.parse_geocode(body)
    assert r is not None and r.place_id == "ABC123"


def test_mappls_no_content_is_a_miss_but_unauthorised_is_an_error() -> None:
    assert mappls_mod.parse_geocode({"responseCode": 204}) is None
    with pytest.raises(GeocoderError):
        mappls_mod.parse_geocode({"responseCode": 401})


def test_mappls_sends_a_bearer_token() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json=MAPPLS_ONE)

    with transport(handler) as client:
        MapplsGeocoder("tok").search(client, "mg road kochi")

    assert seen["auth"] == "bearer tok"


# --- L5 Google -------------------------------------------------------------

GOOGLE_BODY = {
    "status": "OK",
    "results": [
        {
            "formatted_address": "MG Road, Kochi, Kerala 682035, India",
            "geometry": {"location": {"lat": 9.9312, "lng": 76.2673}},
            "address_components": [{"types": ["postal_code"], "long_name": "682035"}],
            "place_id": "ChIJ-google",
        }
    ],
}


def test_google_reads_the_top_hit() -> None:
    r = google_mod.parse_geocode(GOOGLE_BODY)
    assert r is not None
    assert r.postcode == "682035"
    assert r.place_id == "ChIJ-google"
    assert r.partial is False


def test_google_zero_results_is_a_miss() -> None:
    assert google_mod.parse_geocode({"status": "ZERO_RESULTS", "results": []}) is None


@pytest.mark.parametrize(
    "status", ["REQUEST_DENIED", "OVER_QUERY_LIMIT", "OVER_DAILY_LIMIT", "INVALID_REQUEST"]
)
def test_a_google_failure_is_never_read_as_an_absent_address(status: str) -> None:
    """The cache does not expire, so a miss cached during a key outage
    outlives the outage. Only ZERO_RESULTS may become a miss."""
    with pytest.raises(GeocoderError):
        google_mod.parse_geocode({"status": status, "results": []})


def test_google_partial_match_survives_into_the_result() -> None:
    body = {"status": "OK", "results": [{**GOOGLE_BODY["results"][0], "partial_match": True}]}
    r = google_mod.parse_geocode(body)
    assert r is not None and r.partial is True


def test_google_constrains_to_india_and_to_the_pin() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=GOOGLE_BODY)

    with transport(handler) as client:
        GoogleGeocoder("k").search(client, "mg road kochi", pincode="682035")

    assert "country:IN" in seen["components"]
    assert "postal_code:682035" in seen["components"]


# --- doubt and confidence (pure) -------------------------------------------


def test_a_partial_match_is_doubt_worth_a_second_opinion() -> None:
    n = normalise_address("some village, palakkad")
    r = GeocodeResult(10.7, 76.6, "google_maps", partial=True)
    assert doubt_about(n, r) is not None


def test_a_conflicting_pin_is_doubt() -> None:
    n = normalise_address("mg road kochi 682035")
    assert doubt_about(n, GeocodeResult(9.9, 76.2, "nominatim", postcode="600001")) is not None


def test_no_pin_to_check_against_is_not_doubt() -> None:
    """Escalating on this would send nearly every address to a paid level."""
    n = normalise_address("mg road kochi")
    assert doubt_about(n, GeocodeResult(9.9, 76.2, "nominatim")) is None


def test_a_partial_match_costs_a_confidence_step_even_when_the_pin_agrees() -> None:
    out = classify_geocode(
        normalise_address("mg road kochi 682035"),
        [GeocodeResult(9.93, 76.26, "google_maps", postcode="682035", partial=True)],
    )
    assert out.confidence is Confidence.MEDIUM  # would have been HIGH
    assert any("partial" in r for r in out.reasons)


# --- the cascade shell -----------------------------------------------------


class _Fake:
    """A geocoder that answers with a fixed result and counts its calls."""

    def __init__(self, source: str, result: GeocodeResult | None = None, raises=None) -> None:  # noqa: ANN001
        self.source = source
        self.result = result
        self.raises = raises
        self.calls = 0

    def search(self, client: object, query: str, *, pincode: str | None = None):  # noqa: ANN201
        self.calls += 1
        if self.raises is not None:
            raise self.raises
        return self.result


def test_a_confident_free_hit_never_reaches_a_paid_level(session: Session) -> None:
    """The difference between a cascade and a fan-out is this test."""
    free = _Fake("nominatim", GeocodeResult(9.9312, 76.2673, "nominatim"))
    paid = _Fake("google_maps", GeocodeResult(9.9312, 76.2673, "google_maps"))

    out = geocode(session, "MG Road Kochi", geocoders=[free, paid], client=httpx.Client())

    assert out.status is GeocodeStatus.HIT
    assert free.calls == 1
    assert paid.calls == 0


def test_a_level_that_misses_falls_through_to_the_next(session: Session) -> None:
    free = _Fake("nominatim", None)
    paid = _Fake("ola_maps", GeocodeResult(9.9312, 76.2673, "ola_maps"))

    out = geocode(session, "somewhere obscure", geocoders=[free, paid], client=httpx.Client())

    assert out.source == "ola_maps"
    assert paid.calls == 1


def test_a_doubtful_hit_buys_exactly_one_second_opinion(session: Session) -> None:
    doubtful = _Fake("nominatim", GeocodeResult(9.93, 76.26, "nominatim", postcode="600001"))
    second = _Fake("ola_maps", GeocodeResult(9.9305, 76.2605, "ola_maps", postcode="682035"))
    third = _Fake("google_maps", GeocodeResult(9.93, 76.26, "google_maps"))

    out = geocode(
        session, "MG Road Kochi 682035", geocoders=[doubtful, second, third], client=httpx.Client()
    )

    assert out.status is GeocodeStatus.HIT
    assert second.calls == 1
    assert third.calls == 0, "a third opinion buys nothing - a tie goes to a human, not a vote"


def test_two_real_providers_disagreeing_by_more_than_2km_produce_a_miss(session: Session) -> None:
    """PLAN 1.3 escalation, end to end through the shell rather than the pure
    function: Nominatim doubts itself, Ola is consulted, and they are 360 km
    apart - so nobody wins and a human is asked."""
    nominatim = _Fake("nominatim", GeocodeResult(9.9312, 76.2673, "nominatim", postcode="600001"))
    ola = _Fake("ola_maps", GeocodeResult(12.9716, 77.5946, "ola_maps", postcode="682035"))

    out = geocode(session, "MG Road 682035", geocoders=[nominatim, ola], client=httpx.Client())

    assert out.status is GeocodeStatus.MISS
    assert any("disagree" in r for r in out.reasons)


def test_a_failing_level_is_recorded_and_the_cascade_continues(session: Session) -> None:
    broken = _Fake("ola_maps", raises=GeocoderError("ola_maps", "status='invalid_api_key'"))
    working = _Fake("google_maps", GeocodeResult(9.93, 76.26, "google_maps"))

    out = geocode(session, "MG Road Kochi", geocoders=[broken, working], client=httpx.Client())

    assert out.status is GeocodeStatus.HIT
    assert out.source == "google_maps"
    assert any("ola_maps failed" in r for r in out.reasons)


def test_a_failing_level_does_not_cache_a_miss_as_an_answer(session: Session) -> None:
    """The whole point of separating GeocoderError from None."""
    broken = _Fake("google_maps", raises=GeocoderError("google_maps", "status=REQUEST_DENIED"))
    out = geocode(session, "MG Road Kochi", geocoders=[broken], client=httpx.Client())

    assert out.status is GeocodeStatus.MISS
    row = session.get(GeocodeCache, normalise_address("MG Road Kochi").cache_key)
    # It IS cached as a miss - but the reason says why, so the console can
    # distinguish "unfindable" from "our key was broken that afternoon".
    assert row is not None
    assert any("REQUEST_DENIED" in r for r in out.reasons)


# --- metering (constraint 10) ----------------------------------------------


def _metered(session: Session, inner, provider: str = "google_maps", config=KEYED):  # noqa: ANN001, ANN202
    return MeteredGeocoder(inner, session=session, provider=provider, config=config, card=CARD)


def test_a_paid_call_writes_a_usage_row_before_its_answer_is_used(session: Session) -> None:
    inner = _Fake("google_maps", GeocodeResult(9.93, 76.26, "google_maps"))
    out = geocode(
        session, "MG Road Kochi", geocoders=[_metered(session, inner)], client=httpx.Client()
    )

    assert out.status is GeocodeStatus.HIT
    (row,) = usage(session)
    assert row.provider == "google_maps"
    assert row.operation == "geocode"
    assert row.units_in == 1
    assert row.cost_paise == 44
    assert row.status == UsageStatus.OK.value


def test_a_paid_miss_still_costs_and_is_still_recorded(session: Session) -> None:
    """A geocoder bills for looking, not for finding."""
    inner = _Fake("google_maps", None)
    geocode(session, "nowhere at all", geocoders=[_metered(session, inner)], client=httpx.Client())

    (row,) = usage(session)
    assert row.units_in == 1
    assert row.cost_paise == 44
    assert row.detail is not None and row.detail["resolved"] is False


def test_a_paid_error_is_recorded_and_the_cascade_survives_it(session: Session) -> None:
    broken = _Fake("google_maps", raises=GeocoderError("google_maps", "status=UNKNOWN_ERROR"))
    out = geocode(
        session, "MG Road Kochi", geocoders=[_metered(session, broken)], client=httpx.Client()
    )

    assert out.status is GeocodeStatus.MISS
    (row,) = usage(session)
    assert row.status == UsageStatus.ERROR.value
    assert row.error is not None and "UNKNOWN_ERROR" in row.error


def test_at_cap_the_call_is_refused_and_the_refusal_is_visible(session: Session) -> None:
    """The cap must not look like a provider outage. It writes its own row."""
    capped = PaidProvider(api_key="k", monthly_cap=1, console_cap_confirmed=True)
    inner = _Fake("google_maps", GeocodeResult(9.93, 76.26, "google_maps"))
    level = _metered(session, inner, config=capped)

    first = geocode(session, "MG Road Kochi", geocoders=[level], client=httpx.Client())
    second = geocode(session, "Anna Salai Chennai", geocoders=[level], client=httpx.Client())

    assert first.status is GeocodeStatus.HIT
    assert second.status is GeocodeStatus.MISS
    assert inner.calls == 1, "the second call must not have happened at all"

    statuses = [r.status for r in usage(session)]
    assert statuses == [UsageStatus.OK.value, UsageStatus.CAPPED.value]
    assert any("cap" in r for r in second.reasons)


# --- assembling the cascade -------------------------------------------------


def _settings(**over: object) -> Settings:
    return Settings(env="test", **over)  # type: ignore[arg-type]


def test_with_no_keys_the_cascade_is_free_levels_only(session: Session) -> None:
    levels = build_cascade(session, _settings())
    assert [level.source for level in levels] == ["nominatim"]


def test_a_configured_key_with_no_price_card_refuses_to_build(session: Session) -> None:
    """Loud, at assembly, before a single rupee - not at the first geocode.

    A call that cannot be priced becomes a spend report that reads Rs 0 while
    the bill arrives, which is worse than an outage.
    """
    settings = _settings(google_maps=KEYED)
    with pytest.raises(PriceCardMissingError):
        build_cascade(session, settings)


def test_a_configured_key_with_a_card_joins_the_cascade_in_cost_order(session: Session) -> None:
    seed_price_cards(session)
    settings = _settings(google_maps=KEYED, ola_maps=KEYED)

    levels = build_cascade(session, settings, on=dt.date(2026, 9, 1))

    assert [level.source for level in levels] == ["nominatim", "ola_maps", "google_maps"]
    assert isinstance(levels[1], MeteredGeocoder)
