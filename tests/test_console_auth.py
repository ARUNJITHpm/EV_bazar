"""PART C.0 - console access control.

PLAN C.0: "Guard on the server, not in the router. A hidden React route is not
access control - the endpoints are what must refuse."

So the test that matters most is ``test_every_console_endpoint_refuses``: it
walks the live OpenAPI schema rather than a hand-written list, which means a
console endpoint added next month is covered without anyone remembering to add
it here. A guard you have to remember is a guard you will eventually forget.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import (
    COOKIE_NAME,
    PasswordHashError,
    hash_password,
    issue_session,
    read_session,
    verify_password,
)
from app.config import Settings, get_settings
from app.db import get_session
from app.main import create_app
from app.models import Base
from app.models.charger_status import PollRun

PASSWORD = "a-long-enough-password"
SECRET = "test-secret-key"

#: Open on purpose: infra probes and login itself. Everything else under
#: /api/internal must refuse. Listed here so that widening it is a visible
#: diff in a test file, not a quiet change in a router.
PUBLIC_PATHS = {
    "/api/internal/healthz",
    "/api/internal/readyz",
    "/api/internal/poller/alive",
    "/api/internal/console/login",
    "/api/internal/console/logout",
    # Open BY DECISION (api/internal/reports.py): the report page is customer-
    # facing and the customer holds a link, not a console login. The report id
    # is the capability.
    "/api/internal/reports/{report_id}",
}


def _settings() -> Settings:
    """A configured console.

    Takes no arguments on purpose: FastAPI introspects the signature of a
    dependency override, so a ``**kwargs`` here turns every request into a
    422 about missing query parameters rather than the auth result under test.
    """
    # _env_file=None everywhere in this file: these tests assert auth
    # behaviour, and the developer's .env may carry CONSOLE_AUTH_DISABLED=true
    # (or a real password) that would silently change what is being tested.
    return Settings(
        env="test",
        console_secret_key=SECRET,
        console_password_hash=hash_password(PASSWORD),
        _env_file=None,
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[PollRun.__table__])
    make_session = sessionmaker(bind=engine)

    def override_session() -> Iterator[Session]:
        s = make_session()
        try:
            yield s
        finally:
            s.close()

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = _settings
    with TestClient(app) as c:
        yield c


# --- the password primitives -----------------------------------------------


def test_a_correct_password_verifies() -> None:
    assert verify_password(PASSWORD, hash_password(PASSWORD))


def test_a_wrong_password_does_not() -> None:
    assert not verify_password("nearly-the-password", hash_password(PASSWORD))


def test_the_same_password_hashes_differently_each_time() -> None:
    """Salted: two operators with the same password must not look identical."""
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_a_malformed_hash_raises_rather_than_returning_false() -> None:
    """A deployment mistake must refuse everyone loudly, not admit everyone."""
    with pytest.raises(PasswordHashError):
        verify_password(PASSWORD, "not-a-hash")


def test_an_unknown_scheme_is_refused() -> None:
    with pytest.raises(PasswordHashError):
        verify_password(PASSWORD, "md5$1$1$1$c2FsdA$aGFzaA")


# --- the session token ------------------------------------------------------


def test_a_session_round_trips() -> None:
    token = issue_session(SECRET, operator="operator")
    assert read_session(SECRET, token, max_age_seconds=3600) == "operator"


def test_a_session_signed_with_another_key_is_rejected() -> None:
    token = issue_session("some-other-key", operator="operator")
    assert read_session(SECRET, token, max_age_seconds=3600) is None


@pytest.mark.parametrize(
    ("label", "tamper"),
    [
        ("extra byte on the signature", lambda t: t + "A"),
        ("truncated signature", lambda t: t[:-4]),
        ("payload lengthened", lambda t: t.replace(".", ".A", 1)),
        ("first payload byte flipped", lambda t: ("B" if t[0] == "A" else "A") + t[1:]),
        ("separator removed", lambda t: t.replace(".", "", 1)),
    ],
)
def test_a_tampered_session_is_rejected(label: str, tamper: Callable[[str], str]) -> None:
    """Each mutation is deterministic, which the obvious version is not.

    Flipping the token's LAST character looks like tampering and frequently
    is not: base64's final character carries padding bits, so several
    different characters decode to identical bytes. That version passed a
    valid token in and asserted it was rejected, roughly one run in eight -
    a security test that cries wolf until people stop reading it.
    """
    token = issue_session(SECRET, operator="operator")
    tampered = tamper(token)
    assert tampered != token, label
    assert read_session(SECRET, tampered, max_age_seconds=3600) is None, label


def test_an_expired_session_is_rejected() -> None:
    token = issue_session(SECRET, operator="operator")
    assert read_session(SECRET, token, max_age_seconds=-1) is None


# --- the endpoints ----------------------------------------------------------


def test_every_console_endpoint_refuses_without_a_session(client: TestClient) -> None:
    """Walks the schema, so a panel added later is covered automatically."""
    schema = client.get("/openapi.json").json()
    checked = 0

    for path, operations in schema["paths"].items():
        if not path.startswith("/api/internal") or path in PUBLIC_PATHS:
            continue
        for method in operations:
            response = client.request(method.upper(), path)
            assert response.status_code == 401, f"{method.upper()} {path} did not refuse"
            checked += 1

    # A guard test that guards nothing would pass silently forever.
    assert checked > 0


def test_the_public_probes_stay_open(client: TestClient) -> None:
    """An uptime monitor has no session, and must still get a status code."""
    assert client.get("/api/internal/healthz").status_code == 200
    assert client.get("/api/internal/poller/alive").status_code == 200


def test_liveness_leaks_nothing_about_our_sources(client: TestClient) -> None:
    """The unauthenticated probe answers alive/not, and nothing else."""
    body = client.get("/api/internal/poller/alive").json()
    assert set(body) == {"alive", "never_run"}


def test_signing_in_then_reading_a_panel(client: TestClient) -> None:
    assert (
        client.post("/api/internal/console/login", json={"password": PASSWORD}).status_code == 200
    )
    assert client.get("/api/internal/console/me").json() == {"operator": "operator"}
    assert client.get("/api/internal/sources").status_code == 200


def test_the_session_cookie_is_not_readable_by_javascript(client: TestClient) -> None:
    """The console renders operator-entered CPO notes; an XSS must not also
    hand over the session."""
    response = client.post("/api/internal/console/login", json={"password": PASSWORD})
    header = response.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header


def test_the_session_cookie_is_tls_only_in_production() -> None:
    """...and NOT in dev/test, where plain http would drop it silently."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        env="prod",
        console_secret_key=SECRET,
        console_password_hash=hash_password(PASSWORD),
        _env_file=None,
    )
    with TestClient(app) as c:
        response = c.post("/api/internal/console/login", json={"password": PASSWORD})
    assert "secure" in response.headers["set-cookie"].lower()


def test_a_wrong_password_is_refused(client: TestClient) -> None:
    response = client.post("/api/internal/console/login", json={"password": "wrong"})
    assert response.status_code == 401
    assert client.get("/api/internal/sources").status_code == 401


def test_signing_out_ends_the_session(client: TestClient) -> None:
    client.post("/api/internal/console/login", json={"password": PASSWORD})
    assert client.post("/api/internal/console/logout").status_code == 204
    client.cookies.clear()
    assert client.get("/api/internal/console/me").status_code == 401


def test_a_forged_cookie_does_not_get_in(client: TestClient) -> None:
    client.cookies.set(COOKIE_NAME, "eyJvcGVyYXRvciI6Im9wZXJhdG9yIn0.forged.signature")
    assert client.get("/api/internal/sources").status_code == 401


def test_an_unconfigured_console_refuses_rather_than_opens() -> None:
    """The state that usually goes wrong: not set up yet.

    "We have not chosen a password" must not mean "anyone may read the CPO
    terms". It means 503.
    """
    app = create_app()
    # _env_file=None or this asserts against whatever the developer happens to
    # have in .env - which passed only for as long as nobody had configured a
    # console locally, and then failed for a reason that looks nothing like
    # its cause.
    app.dependency_overrides[get_settings] = lambda: Settings(env="dev", _env_file=None)
    with TestClient(app) as c:
        assert c.get("/api/internal/sources").status_code == 503
        assert c.post("/api/internal/console/login", json={"password": PASSWORD}).status_code == 503


def test_production_will_not_boot_without_a_console_password() -> None:
    """Same shape as the quota-cap rule: loud, at startup."""
    with pytest.raises(ValueError, match="PLAN C.0"):
        Settings(env="prod", _env_file=None)


def test_the_dev_bypass_opens_the_console_without_a_session() -> None:
    """CONSOLE_AUTH_DISABLED=true: no login, every request is the operator."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        env="dev", console_auth_disabled=True, _env_file=None
    )
    with TestClient(app) as c:
        me = c.get("/api/internal/console/me")
        assert me.status_code == 200
        assert me.json() == {"operator": "operator"}
        assert c.get("/api/internal/sources").status_code == 200


def test_production_will_not_boot_with_the_bypass_set() -> None:
    """The bypass is a local convenience; prod dies loudly rather than opening.
    Even with a password ALSO configured - the flag itself is the mistake."""
    with pytest.raises(ValueError, match="console_auth_disabled"):
        Settings(
            env="prod",
            console_auth_disabled=True,
            console_secret_key=SECRET,
            console_password_hash=hash_password(PASSWORD),
            _env_file=None,
        )


def test_production_boots_once_it_is_configured() -> None:
    settings = Settings(
        env="prod",
        console_secret_key=SECRET,
        console_password_hash=hash_password(PASSWORD),
        _env_file=None,
    )
    assert settings.console_configured
