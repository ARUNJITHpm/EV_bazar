"""Status scraping is deferred: with SCRAPER_ENABLED off, nothing scraper-related runs or shows."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.internal.poller import require_scraper
from app.config import Settings, get_settings
from app.main import create_app


def _settings(enabled: bool = False) -> Settings:
    return Settings(env="test", console_auth_disabled=True, scraper_enabled=enabled, _env_file=None)


def _off() -> Settings:  # no parameters: FastAPI reads a dependency override's signature
    return _settings()


def test_the_flag_defaults_to_off() -> None:
    assert Settings(env="test", _env_file=None).scraper_enabled is False


def test_poller_routes_do_not_exist_when_off() -> None:
    with pytest.raises(HTTPException) as exc:
        require_scraper(_settings())
    assert exc.value.status_code == 404
    require_scraper(_settings(True))  # no error


def test_poller_endpoints_404_when_off_and_features_say_so() -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = _off
    client = TestClient(app)
    for path in (
        "/api/internal/poller/alive",
        "/api/internal/poller/health",
        "/api/internal/sources",
    ):
        assert client.get(path).status_code == 404, path


def test_features_endpoint_reports_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(create_app())
    assert client.get("/api/internal/features").json() == {"scraper_enabled": False}
    monkeypatch.setenv("SCRAPER_ENABLED", "true")
    get_settings.cache_clear()
    assert client.get("/api/internal/features").json() == {"scraper_enabled": True}


def test_the_poller_process_refuses_to_run_when_off(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from workers import poller

    monkeypatch.setattr("sys.argv", ["poller"])
    ran: list[bool] = []
    monkeypatch.setattr(poller, "poll_once", lambda *_a, **_k: ran.append(True))
    with caplog.at_level("WARNING"):
        poller.main()
    assert ran == []
    assert "switched off" in caplog.text
