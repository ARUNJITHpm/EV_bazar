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

from app.api.internal.ratelimit import SlidingWindowLimiter, client_key, rate_limit
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
