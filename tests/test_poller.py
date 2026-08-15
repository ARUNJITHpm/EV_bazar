"""PART 0.1 - poller tests.

Three things are worth testing here, and they are the three that silently
corrupt three years of history if they are wrong:

  1. Status mapping. An unrecognised status must never become "available".
  2. Source authorisation. An unvetted source must not receive traffic.
  3. The dead-man's switch. Silence must be detected.

The normaliser is pure, so most of this needs no database at all.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.polling import (
    SourceNotAuthorisedError,
    dedupe,
    from_ocpi_locations,
    from_scraped_stations,
    map_ocpi_status,
    map_scrape_status,
    poller_health,
    require_pollable,
    source_health,
)
from app.domain.polling.sources import BY_NAME, SOURCES, AuthMode, SourceSpec
from app.models import Base
from app.models.charger_status import ConnectorStatus, PollOutcome, PollRun

NOW = dt.datetime(2026, 8, 12, 10, 0, tzinfo=dt.UTC)


# --- 1. status mapping -----------------------------------------------------


@pytest.mark.parametrize(
    ("ocpi", "expected"),
    [
        ("AVAILABLE", ConnectorStatus.AVAILABLE),
        ("CHARGING", ConnectorStatus.CHARGING),
        ("BLOCKED", ConnectorStatus.OCCUPIED),
        ("RESERVED", ConnectorStatus.OCCUPIED),
        ("INOPERATIVE", ConnectorStatus.OFFLINE),
        ("OUTOFORDER", ConnectorStatus.OFFLINE),
        ("REMOVED", ConnectorStatus.OFFLINE),
        ("PLANNED", ConnectorStatus.UNKNOWN),
        ("  charging  ", ConnectorStatus.CHARGING),  # whitespace + case
    ],
)
def test_ocpi_status_mapping(ocpi: str, expected: ConnectorStatus) -> None:
    assert map_ocpi_status(ocpi) == expected


@pytest.mark.parametrize("value", ["", None, "SOMETHING_NEW", "🙂"])
def test_unknown_status_never_becomes_available(value: str | None) -> None:
    """Inventing availability corrupts every occupancy average downstream."""
    assert map_ocpi_status(value) == ConnectorStatus.UNKNOWN


# --- normalisation ---------------------------------------------------------

PAYLOAD = {
    "data": [
        {
            "id": "LOC1",
            "evses": [
                {
                    "uid": "EVSE1",
                    "status": "CHARGING",
                    "last_updated": "2026-08-12T09:58:00Z",
                    "connectors": [{"id": "1"}, {"id": "2"}],
                },
                {"uid": "EVSE2", "status": "AVAILABLE", "connectors": [{"id": "1"}]},
            ],
        }
    ]
}


def test_one_row_per_connector_not_per_evse() -> None:
    obs = from_ocpi_locations(PAYLOAD, source="s", observed_at=NOW)
    assert len(obs) == 3
    assert {o.connector_id for o in obs} == {"EVSE1:1", "EVSE1:2", "EVSE2:1"}


def test_source_timestamp_is_preferred_when_present() -> None:
    obs = from_ocpi_locations(PAYLOAD, source="s", observed_at=NOW)
    charging = next(o for o in obs if o.connector_id == "EVSE1:1")
    assert charging.observed_at == dt.datetime(2026, 8, 12, 9, 58, tzinfo=dt.UTC)


def test_missing_or_broken_timestamp_falls_back_to_our_clock() -> None:
    payload = {
        "data": [
            {
                "id": "L",
                "evses": [{"uid": "E", "status": "AVAILABLE", "last_updated": "not-a-date"}],
            }
        ]
    }
    (obs,) = from_ocpi_locations(payload, source="s", observed_at=NOW)
    assert obs.observed_at == NOW


def test_evse_without_connectors_is_still_recorded() -> None:
    """Dropping it would silently lose a whole charge point."""
    payload = {"data": [{"id": "L", "evses": [{"uid": "E", "status": "AVAILABLE"}]}]}
    (obs,) = from_ocpi_locations(payload, source="s", observed_at=NOW)
    assert obs.connector_id == "E"


def test_raw_payload_is_always_kept() -> None:
    """A mapping we get wrong today is only fixable if the blob survived."""
    obs = from_ocpi_locations(PAYLOAD, source="s", observed_at=NOW)
    assert all(o.raw_payload and "evse" in o.raw_payload for o in obs)


def test_malformed_payload_yields_nothing_rather_than_raising() -> None:
    """A bad page must not kill a cycle that still has good pages to fetch."""
    for junk in ({}, {"data": None}, {"data": [{}]}, {"data": ["nope"]}):
        assert from_ocpi_locations(junk, source="s", observed_at=NOW) == ()


def test_dedupe_keeps_the_last_observation_of_a_connector() -> None:
    """Paginated feeds repeat locations; double-counting skews occupancy."""
    dup = {"data": [PAYLOAD["data"][0], PAYLOAD["data"][0]]}
    obs = from_ocpi_locations(dup, source="s", observed_at=NOW)
    assert len(obs) == 6
    assert len(dedupe(obs)) == 3


# --- scraped CPO apps (ChargeZone / Statiq / Kazam / chargeMOD / ...) -------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("available", ConnectorStatus.AVAILABLE),
        ("Available", ConnectorStatus.AVAILABLE),
        ("  CHARGING ", ConnectorStatus.CHARGING),
        ("in_use", ConnectorStatus.CHARGING),
        ("reserved", ConnectorStatus.OCCUPIED),
        ("faulted", ConnectorStatus.OFFLINE),
        ("maintenance", ConnectorStatus.OFFLINE),
    ],
)
def test_scrape_status_mapping(raw: str, expected: ConnectorStatus) -> None:
    assert map_scrape_status(raw) == expected


@pytest.mark.parametrize("value", ["", None, "brand_new_word", "🙂"])
def test_scrape_unknown_status_never_becomes_available(value: str | None) -> None:
    assert map_scrape_status(value) == ConnectorStatus.UNKNOWN


SCRAPE_PAYLOAD = {
    "stations": [
        {
            "id": "KL-TVM-001",
            "connectors": [
                {"id": "A", "status": "available"},
                {"id": "B", "status": "charging"},
            ],
        },
        {"id": "KL-EKM-002", "connectors": [{"id": "1", "status": "faulted"}]},
    ]
}


def test_scrape_one_row_per_connector() -> None:
    obs = from_scraped_stations(SCRAPE_PAYLOAD, source="chargezone", observed_at=NOW)
    assert len(obs) == 3
    assert {(o.source_station_id, o.connector_id) for o in obs} == {
        ("KL-TVM-001", "A"),
        ("KL-TVM-001", "B"),
        ("KL-EKM-002", "1"),
    }
    assert all(o.observed_at == NOW for o in obs)


def test_scrape_tolerates_alternative_field_names() -> None:
    """A minor naming difference must not need a code change - only a genuinely
    different structure does. Each app's shape differs slightly."""
    payload = {
        "data": [  # 'data' instead of 'stations'
            {
                "station_id": "S1",  # 'station_id' instead of 'id'
                "ports": [{"portId": "p1", "state": "busy"}],  # 'ports'/'portId'/'state'
            }
        ]
    }
    (obs,) = from_scraped_stations(payload, source="statiq", observed_at=NOW)
    assert obs.source_station_id == "S1"
    assert obs.connector_id == "p1"
    assert obs.status == ConnectorStatus.CHARGING


def test_scrape_station_without_connectors_is_still_recorded() -> None:
    payload = {"stations": [{"id": "S1", "status": "available"}]}
    (obs,) = from_scraped_stations(payload, source="kazam", observed_at=NOW)
    assert obs.source_station_id == "S1"
    assert obs.connector_id == "S1"
    assert obs.status == ConnectorStatus.AVAILABLE


def test_scrape_bare_list_payload_is_accepted() -> None:
    payload = [{"id": "S1", "connectors": [{"id": "1", "status": "available"}]}]
    (obs,) = from_scraped_stations(payload, source="chargemod", observed_at=NOW)
    assert obs.source_station_id == "S1"


def test_scrape_malformed_payload_yields_nothing_rather_than_raising() -> None:
    for junk in ({}, {"stations": None}, {"stations": [{}]}, {"stations": ["nope"]}):
        assert from_scraped_stations(junk, source="chargezone", observed_at=NOW) == ()


def test_scrape_raw_payload_is_always_kept() -> None:
    obs = from_scraped_stations(SCRAPE_PAYLOAD, source="chargezone", observed_at=NOW)
    assert all(o.raw_payload for o in obs)


def test_scrape_adapter_fetches_and_normalises() -> None:
    import httpx

    from app.domain.polling.adapters import ScrapeAdapter

    spec = BY_NAME["chargezone"]
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert request.headers.get("Authorization") == "Bearer secret"
        return httpx.Response(200, json=SCRAPE_PAYLOAD)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    obs = ScrapeAdapter(
        spec, base_url="https://api.chargezone.test", api_key="secret", path="/v1/stations"
    ).fetch(client, observed_at=NOW)

    assert seen == ["https://api.chargezone.test/v1/stations"]
    assert len(obs) == 3


def test_all_scrape_sources_ship_unauthorised() -> None:
    """No CPO app is polled until its terms are read - traffic never a default."""
    for name in ("chargezone", "statiq", "kazam", "chargemod", "tata_power_ez", "jio_bp"):
        spec = BY_NAME[name]
        assert spec.adapter == "scrape"
        assert spec.authorised is False
        assert spec.pollable is False


def test_scrape_source_needs_both_config_and_authorisation() -> None:
    """Config supplies the endpoint; the registry supplies permission. Both.

    A configured-but-unvetted source is still refused - config alone is not
    consent to poll somebody's app.
    """
    from app.config import ScrapeSource, Settings
    from workers.poller import build_targets, resolve_scrape_spec

    # Configured endpoint, but registry still has authorised=False.
    # _env_file=None: the developer's .env will one day carry REAL endpoints,
    # and this test must keep testing its fixture, not that machine.
    configured = Settings(chargezone=ScrapeSource(base_url="https://cz.test"), _env_file=None)
    spec = resolve_scrape_spec("chargezone", configured)
    assert spec.enabled is True  # endpoint is set
    assert spec.pollable is False  # ...but not authorised
    assert "authorised=False" in (spec.blocking_reason() or "")
    assert build_targets(configured) == []


def test_scrape_source_polls_once_authorised_and_configured() -> None:
    """The two locks lined up: authorised in the registry AND an endpoint set."""
    import dataclasses
    from unittest.mock import patch

    from app.config import ScrapeSource, Settings
    from workers import poller as poller_mod

    # Simulate a human having read ChargeZone's terms and authorised it.
    vetted = dataclasses.replace(
        poller_mod.BY_NAME["chargezone"],
        terms_url="https://chargezone.test/terms",
        terms_note="Reviewed 2026-08; automated polling permitted.",
        authorised=True,
    )
    patched = dict(poller_mod.BY_NAME)
    patched["chargezone"] = vetted

    configured = Settings(chargezone=ScrapeSource(base_url="https://cz.test"), _env_file=None)
    # build_targets resolves through the module-level BY_NAME reference.
    with patch.object(poller_mod, "BY_NAME", patched):
        targets = poller_mod.build_targets(configured)
    assert [spec.name for spec, _ in targets] == ["chargezone"]


def test_cpo_sources_endpoint_lists_registry_with_measured_status() -> None:
    """The console CPO panel data: governance + what our poller last saw."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine as _create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.auth import hash_password
    from app.config import Settings, get_settings
    from app.db import get_session
    from app.main import create_app

    # StaticPool shares one in-memory connection across sessions; a plain
    # sqlite:// gives each new connection its own empty database.
    engine = _create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[PollRun.__table__])
    make_session = sessionmaker(bind=engine)
    with make_session() as seed:
        seed.add(
            PollRun(
                id=uuid.uuid4(),
                source="chargezone",
                started_at=NOW,
                finished_at=NOW,
                outcome=PollOutcome.OK.value,
                events_written=42,
                raw_pages_written=2,
                connectors_seen=118,
                stations_seen=7,
            )
        )
        seed.commit()

    def override() -> Session:
        s = make_session()
        try:
            yield s
        finally:
            s.close()

    app = create_app()
    app.dependency_overrides[get_session] = override
    # This panel is behind the console guard (PLAN C.0), so the test signs in
    # like an operator rather than reaching past it.
    app.dependency_overrides[get_settings] = lambda: Settings(
        env="test",
        console_secret_key="k",
        console_password_hash=hash_password("password-1234"),
        _env_file=None,
    )
    client = TestClient(app)
    assert (
        client.post("/api/internal/console/login", json={"password": "password-1234"}).status_code
        == 200
    )

    body = client.get("/api/internal/sources").json()
    by_name = {s["source"]: s for s in body["sources"]}

    # Every registered network is present, scraped ones flagged unauthorised.
    assert "chargezone" in by_name
    assert by_name["chargezone"]["kind"] == "scrape"
    assert by_name["chargezone"]["authorised"] is False
    # ...and the measured status came through from the seeded poll run.
    assert by_name["chargezone"]["events_last_run"] == 42
    assert by_name["chargezone"]["connectors_last_run"] == 118
    assert by_name["chargezone"]["stations_last_run"] == 7
    # Kazam is in the set too, per this change.
    assert "kazam" in by_name


# --- 2. source authorisation ----------------------------------------------


def test_registry_ships_with_nothing_enabled() -> None:
    """Traffic requires a deliberate change, never a default."""
    assert all(not s.enabled for s in SOURCES)


def test_unauthorised_source_is_refused() -> None:
    with pytest.raises(SourceNotAuthorisedError, match="not enabled"):
        require_pollable("plugshare")


def test_unknown_source_is_refused() -> None:
    with pytest.raises(SourceNotAuthorisedError, match="not in the registry"):
        require_pollable("some_random_api")


def test_enabled_but_unvetted_source_is_still_refused() -> None:
    """Enabling is not the same as having read the terms."""
    spec = SourceSpec(
        name="x",
        adapter="ocpi",
        base_url="https://example.test",
        terms_url=None,
        terms_note=None,
        rate_limit_per_minute=None,
        auth_mode=AuthMode.OCPI_TOKEN,
        authorised=False,
        enabled=True,
    )
    assert spec.pollable is False
    assert "authorised=False" in (spec.blocking_reason() or "")


def test_authorised_source_without_recorded_terms_is_refused() -> None:
    spec = SourceSpec(
        name="x",
        adapter="ocpi",
        base_url="https://example.test",
        terms_url=None,
        terms_note=None,
        rate_limit_per_minute=60,
        authorised=True,
        enabled=True,
    )
    assert "terms_url" in (spec.blocking_reason() or "")


def test_fully_recorded_source_is_pollable_and_has_a_rate_gap() -> None:
    spec = SourceSpec(
        name="x",
        adapter="ocpi",
        base_url="https://example.test",
        terms_url="https://example.test/terms",
        terms_note="Partner agreement 2026-08; automated polling permitted.",
        rate_limit_per_minute=30,
        authorised=True,
        enabled=True,
    )
    assert spec.pollable is True
    assert spec.min_interval_seconds() == 2.0


# --- 3. the dead-man's switch ---------------------------------------------


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[PollRun.__table__])
    with Session(engine) as s:
        yield s


def _run(session: Session, *, source: str, at: dt.datetime, outcome: PollOutcome) -> None:
    session.add(
        PollRun(
            id=uuid.uuid4(),
            source=source,
            started_at=at,
            finished_at=at,
            outcome=outcome.value,
            events_written=10,
            stations_seen=3,
        )
    )
    session.flush()


def test_never_having_run_is_reported_as_dead(session: Session) -> None:
    health = poller_health(session, ("ocpi_partner",), now=NOW, threshold_minutes=30)
    assert health.never_run is True
    assert health.alive is False


def test_a_recent_success_is_alive(session: Session) -> None:
    _run(session, source="ocpi_partner", at=NOW - dt.timedelta(minutes=4), outcome=PollOutcome.OK)
    health = poller_health(session, ("ocpi_partner",), now=NOW, threshold_minutes=30)
    assert health.alive is True
    assert health.stale_sources == ()


def test_silence_past_the_threshold_is_dead(session: Session) -> None:
    _run(session, source="ocpi_partner", at=NOW - dt.timedelta(minutes=31), outcome=PollOutcome.OK)
    health = poller_health(session, ("ocpi_partner",), now=NOW, threshold_minutes=30)
    assert health.alive is False
    assert health.stale_sources == ("ocpi_partner",)


def test_failures_do_not_count_as_liveness(session: Session) -> None:
    """A source failing every 5 minutes is not a source that is working."""
    _run(
        session, source="ocpi_partner", at=NOW - dt.timedelta(minutes=1), outcome=PollOutcome.FAILED
    )
    health = poller_health(session, ("ocpi_partner",), now=NOW, threshold_minutes=30)
    assert health.alive is False


def test_one_live_source_keeps_the_system_alive_but_flags_the_stalled_one(
    session: Session,
) -> None:
    _run(session, source="a", at=NOW - dt.timedelta(minutes=2), outcome=PollOutcome.OK)
    _run(session, source="b", at=NOW - dt.timedelta(hours=5), outcome=PollOutcome.OK)
    health = poller_health(session, ("a", "b"), now=NOW, threshold_minutes=30)
    assert health.alive is True
    assert health.stale_sources == ("b",)


def test_source_health_surfaces_the_last_error(session: Session) -> None:
    _run(session, source="a", at=NOW - dt.timedelta(minutes=10), outcome=PollOutcome.OK)
    session.add(
        PollRun(
            id=uuid.uuid4(),
            source="a",
            started_at=NOW - dt.timedelta(minutes=1),
            outcome=PollOutcome.FAILED.value,
            error="ConnectTimeout: partner endpoint",
        )
    )
    session.flush()

    health = source_health(session, "a", now=NOW)
    assert health.last_error == "ConnectTimeout: partner endpoint"
    # last *success* is still 10 minutes ago, so within a 30-minute threshold
    assert health.is_stale(dt.timedelta(minutes=30)) is False


# --- pagination ------------------------------------------------------------


def test_next_link_is_followed_verbatim_without_reapplying_params() -> None:
    """Regression: httpx replaces the query string when `params` is passed.

    Re-sending `limit` on page 2 wiped the cursor, the server re-served page
    one, and the feed looked complete while containing only its first page.
    Found by an end-to-end run against a mock OCPI endpoint, not by a unit
    test - which is why this one exists.
    """
    import httpx

    from app.domain.polling.adapters import OcpiAdapter
    from app.domain.polling.sources import AuthMode

    spec = SourceSpec(
        name="mock",
        adapter="ocpi",
        base_url="https://ocpi.test",
        terms_url="https://ocpi.test/terms",
        terms_note="mock",
        rate_limit_per_minute=60,
        auth_mode=AuthMode.OCPI_TOKEN,
        authorised=True,
        enabled=True,
    )

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if "page=2" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "L2",
                            "evses": [
                                {"uid": "E2", "status": "AVAILABLE", "connectors": [{"id": "1"}]}
                            ],
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "L1",
                        "evses": [{"uid": "E1", "status": "CHARGING", "connectors": [{"id": "1"}]}],
                    }
                ]
            },
            headers={"Link": '<https://ocpi.test/locations?page=2>; rel="next"'},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    obs = OcpiAdapter(spec, token="t").fetch(client, observed_at=NOW)

    assert len(seen) == 2
    assert "limit=100" in seen[0]
    # the cursor must survive: no params re-applied on the follow-up
    assert seen[1] == "https://ocpi.test/locations?page=2"
    assert {o.source_station_id for o in obs} == {"L1", "L2"}


def test_pagination_is_bounded() -> None:
    """A feed that paginates forever must not eat the next poll's slot."""
    import httpx

    from app.domain.polling.adapters import OcpiAdapter
    from app.domain.polling.sources import AuthMode

    spec = SourceSpec(
        name="mock",
        adapter="ocpi",
        base_url="https://ocpi.test",
        terms_url="https://ocpi.test/terms",
        terms_note="mock",
        rate_limit_per_minute=60,
        auth_mode=AuthMode.OCPI_TOKEN,
        authorised=True,
        enabled=True,
    )

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            200,
            json={"data": []},
            headers={"Link": '<https://ocpi.test/locations?page=x>; rel="next"'},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    OcpiAdapter(spec, token="t").fetch(client, observed_at=NOW)
    assert calls["n"] == OcpiAdapter.MAX_PAGES
