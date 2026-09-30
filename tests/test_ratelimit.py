"""The /assess throttle - api/internal/ratelimit.py.

/assess is open and writes a lead row on every call, so it carries a per-IP
ceiling. The window logic is pinned here against a fake clock (wall-clock time
makes a rate test flaky), and the dependency's own behaviour - which IP it keys
on, the 429 it raises, the ceiling it reads from settings - is pinned directly,
so none of it needs the database the endpoint otherwise would.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.internal.ratelimit import (
    SlidingWindowLimiter,
    client_key,
    owner_submit_limit,
    rate_limit,
)
from app.config import Settings, get_settings
from app.db import get_session
from app.main import create_app


class FakeClock:
    """A monotonic clock the test drives by hand - no sleeping, no flake."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _limiter(clock: FakeClock, window: float = 60.0) -> SlidingWindowLimiter:
    return SlidingWindowLimiter(window_seconds=window, clock=clock)


# --- the window -------------------------------------------------------------


def test_calls_under_the_limit_are_allowed() -> None:
    limiter = _limiter(FakeClock())
    assert all(limiter.check("1.2.3.4", limit=5).allowed for _ in range(5))


def test_one_past_the_limit_is_refused_with_a_retry_after() -> None:
    clock = FakeClock()
    limiter = _limiter(clock)
    for _ in range(3):
        assert limiter.check("1.2.3.4", limit=3).allowed
    decision = limiter.check("1.2.3.4", limit=3)
    assert not decision.allowed
    # All three hits landed at t0 into a 60 s window, so a slot frees in 60 s.
    assert decision.retry_after == pytest.approx(60.0)


def test_the_window_slides_and_frees_slots() -> None:
    clock = FakeClock()
    limiter = _limiter(clock)
    for _ in range(3):
        assert limiter.check("1.2.3.4", limit=3).allowed
    assert not limiter.check("1.2.3.4", limit=3).allowed
    # Once the oldest hit ages out of the 60 s window, the next call is allowed.
    clock.advance(61)
    assert limiter.check("1.2.3.4", limit=3).allowed


def test_each_key_has_its_own_window() -> None:
    limiter = _limiter(FakeClock())
    for _ in range(3):
        assert limiter.check("1.1.1.1", limit=3).allowed
    assert not limiter.check("1.1.1.1", limit=3).allowed
    # A different caller is unaffected by the first one's exhausted window.
    assert limiter.check("2.2.2.2", limit=3).allowed


# --- the client key ---------------------------------------------------------


def _request(headers: dict[str, str], client: tuple[str, int] | None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": client})


def test_client_key_prefers_the_leftmost_forwarded_ip() -> None:
    # Caddy and HF's proxy append; the leftmost entry is the original caller.
    req = _request({"x-forwarded-for": "203.0.113.9, 10.0.0.1, 127.0.0.1"}, ("127.0.0.1", 8001))
    assert client_key(req) == "203.0.113.9"


def test_client_key_falls_back_to_the_socket_peer() -> None:
    req = _request({}, ("198.51.100.7", 4444))
    assert client_key(req) == "198.51.100.7"


# --- the dependency ---------------------------------------------------------


def test_the_dependency_raises_429_past_the_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.internal.ratelimit._limiter", _limiter(FakeClock()))
    settings = Settings(env="test", assess_rate_limit_per_minute=2, _env_file=None)
    req = _request({"x-forwarded-for": "203.0.113.9"}, ("127.0.0.1", 8001))

    rate_limit(req, settings)  # 1st - fine
    rate_limit(req, settings)  # 2nd - fine
    with pytest.raises(HTTPException) as caught:
        rate_limit(req, settings)  # 3rd - over the ceiling
    assert caught.value.status_code == 429
    assert "Retry-After" in caught.value.headers


def test_a_zero_ceiling_disables_the_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.internal.ratelimit._limiter", _limiter(FakeClock()))
    settings = Settings(env="test", assess_rate_limit_per_minute=0, _env_file=None)
    req = _request({"x-forwarded-for": "203.0.113.9"}, ("127.0.0.1", 8001))
    # Far more calls than any ceiling, and not one is refused.
    for _ in range(50):
        rate_limit(req, settings)


# --- the wiring -------------------------------------------------------------


def test_the_throttle_actually_fires_on_the_assess_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """A guard that works in isolation is worthless if it is not on the route.

    The unit tests above prove ``rate_limit`` refuses; this drives the real
    routing stack to prove the live /assess route runs it - so a mis-edit in
    api/internal/__init__.py that dropped the dependency fails here rather than
    in production. (Asserting it through behaviour, not introspection, on
    purpose: this FastAPI build applies an include's dependencies at match time
    via a mount context, not on the route's own ``dependant``.)

    The session is a mock, so the endpoint body raises once the guard lets it
    through - hence the first call's 500, which is not what is under test. What
    is under test is the SECOND call: with the ceiling at 1, the throttle must
    refuse it with a 429 before the body is ever reached.
    """
    monkeypatch.setattr("app.api.internal.ratelimit._limiter", _limiter(FakeClock()))
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        env="test", assess_rate_limit_per_minute=1, _env_file=None
    )
    app.dependency_overrides[get_session] = lambda: (yield MagicMock())

    body = {"lat": 8.5, "lng": 76.9}
    with TestClient(app, raise_server_exceptions=False) as c:
        first = c.post("/api/internal/assess", json=body)
        second = c.post("/api/internal/assess", json=body)

    assert first.status_code != 429  # the guard let the first through
    assert second.status_code == 429
    assert second.headers["retry-after"] == "60"


# --- the owner submission cap -------------------------------------------------


def test_the_owner_cap_is_hourly_and_refuses_past_the_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    monkeypatch.setattr(
        "app.api.internal.ratelimit._submit_limiter", _limiter(clock, window=3600.0)
    )
    settings = Settings(env="test", owner_submit_limit_per_hour=2, _env_file=None)
    req = _request({"x-forwarded-for": "203.0.113.9"}, ("127.0.0.1", 8001))

    owner_submit_limit(req, settings)
    owner_submit_limit(req, settings)
    with pytest.raises(HTTPException) as caught:
        owner_submit_limit(req, settings)
    assert caught.value.status_code == 429
    assert caught.value.headers["Retry-After"] == "3600"

    # The slot frees once the first hit is an hour old, not a minute.
    clock.advance(60)
    with pytest.raises(HTTPException):
        owner_submit_limit(req, settings)
    clock.advance(3600)
    owner_submit_limit(req, settings)


def test_the_owner_cap_is_per_caller_and_can_be_switched_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.internal.ratelimit._submit_limiter", _limiter(FakeClock(), window=3600.0)
    )
    one = Settings(env="test", owner_submit_limit_per_hour=1, _env_file=None)
    a = _request({"x-forwarded-for": "203.0.113.1"}, ("127.0.0.1", 8001))
    b = _request({"x-forwarded-for": "203.0.113.2"}, ("127.0.0.1", 8001))
    owner_submit_limit(a, one)
    owner_submit_limit(b, one)  # another caller has an allowance of its own
    with pytest.raises(HTTPException):
        owner_submit_limit(a, one)

    off = Settings(env="test", owner_submit_limit_per_hour=0, _env_file=None)
    for _ in range(50):
        owner_submit_limit(a, off)


def test_the_owner_cap_fires_on_the_route_and_other_owner_calls_do_not_spend_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Through the real routing stack, so dropping the dependency from the POST fails here.

    The caller holds no owner session, so a POST that gets past the throttle is
    answered 401 - that first status is not what is under test. The SECOND POST,
    with the hourly cap at 1, must be refused with a 429, and the reads between
    them must not have used the allowance up first.
    """
    monkeypatch.setattr("app.api.internal.ratelimit._limiter", _limiter(FakeClock()))
    monkeypatch.setattr(
        "app.api.internal.ratelimit._submit_limiter", _limiter(FakeClock(), window=3600.0)
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        env="test", owner_submit_limit_per_hour=1, _env_file=None
    )
    app.dependency_overrides[get_session] = lambda: (yield MagicMock())

    with TestClient(app, raise_server_exceptions=False) as c:
        for _ in range(5):
            assert c.get("/api/internal/owner/me").status_code != 429
        first = c.post("/api/internal/owner/onboard", json={})
        second = c.post("/api/internal/owner/onboard", json={})

    assert first.status_code != 429
    assert second.status_code == 429
    assert second.headers["retry-after"] == "3600"


def test_signup_and_login_have_their_own_hourly_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.internal.ratelimit import owner_auth_limit

    monkeypatch.setattr(
        "app.api.internal.ratelimit._auth_limiter", _limiter(FakeClock(), window=3600.0)
    )
    settings = Settings(env="test", owner_auth_limit_per_hour=2, _env_file=None)
    req = _request({"x-forwarded-for": "203.0.113.7"}, ("127.0.0.1", 8001))
    owner_auth_limit(req, settings)
    owner_auth_limit(req, settings)
    with pytest.raises(HTTPException) as caught:
        owner_auth_limit(req, settings)
    assert caught.value.status_code == 429
    owner_auth_limit(req, Settings(env="test", owner_auth_limit_per_hour=0, _env_file=None))


# --- the client key behind the Space's front proxy -----------------------------


def test_client_key_uses_the_end_of_the_chain_the_front_proxy_wrote() -> None:
    # The caller wrote "4.4.4.4" (spoofed); the front proxy appended the real one.
    req = _request(
        {"x-client-chain": "4.4.4.4, 8.8.8.8", "x-forwarded-for": "10.20.0.5"},
        ("127.0.0.1", 8001),
    )
    assert client_key(req) == "8.8.8.8"


def test_client_key_skips_private_hops_at_the_end_of_the_chain() -> None:
    req = _request({"x-client-chain": "8.8.8.8, 10.1.2.3, 127.0.0.1"}, ("127.0.0.1", 8001))
    assert client_key(req) == "8.8.8.8"


def test_a_spoofed_leftmost_entry_does_not_change_the_key() -> None:
    a = _request({"x-client-chain": "5.5.5.5, 8.8.8.8"}, ("127.0.0.1", 8001))
    b = _request({"x-client-chain": "6.6.6.6, 8.8.8.8"}, ("127.0.0.1", 8001))
    assert client_key(a) == client_key(b) == "8.8.8.8"


def test_client_key_falls_back_when_the_chain_is_empty_or_all_private() -> None:
    # Caddy sets the header to "" when the front proxy sent no X-Forwarded-For.
    empty = _request({"x-client-chain": "", "x-forwarded-for": "8.8.4.4"}, ("127.0.0.1", 1))
    assert client_key(empty) == "8.8.4.4"
    private = _request({"x-client-chain": "10.0.0.1, garbage"}, ("192.0.2.7", 1))
    assert client_key(private) == "192.0.2.7"
