"""Part 1.1 smoke tests.

These do not need a database. They assert the things that would make every
later Part quietly wrong if they broke: the app boots, the two API surfaces
stay separate, and the quota-cap guard actually refuses bad configuration.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import PaidProvider, Settings
from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def test_app_boots(client: TestClient) -> None:
    assert client.get("/api/internal/healthz").json() == {"status": "ok"}


def test_partner_api_is_mounted_separately(client: TestClient) -> None:
    assert client.get("/api/v1/ping").json()["api_version"] == "v1"


def test_backend_renders_no_html(client: TestClient) -> None:
    """The SPA owns every page. A stray HTML route means the split leaked."""
    schema = create_app().openapi()
    for path, methods in schema["paths"].items():
        for method, op in methods.items():
            for status, response in op.get("responses", {}).items():
                content = response.get("content", {})
                assert "text/html" not in content, (
                    f"{method.upper()} {path} -> {status} returns HTML; "
                    "this backend is JSON only (AGENTS.md)"
                )


def test_every_route_is_under_api(client: TestClient) -> None:
    schema = create_app().openapi()
    stray = [p for p in schema["paths"] if not p.startswith("/api/")]
    assert not stray, f"routes outside /api: {stray}"


# --- AGENTS.md constraint 7 -------------------------------------------------


def test_provider_without_key_needs_no_cap() -> None:
    assert PaidProvider().enabled is False


def test_api_key_without_cap_is_rejected() -> None:
    with pytest.raises(ValidationError, match="monthly_cap"):
        PaidProvider(api_key="secret")


def test_api_key_with_cap_but_unconfirmed_console_is_rejected() -> None:
    """The client-side counter alone is not sufficient. Two locks, both required."""
    with pytest.raises(ValidationError, match="console"):
        PaidProvider(api_key="secret", monthly_cap=1000)


def test_api_key_with_both_locks_is_accepted() -> None:
    provider = PaidProvider(api_key="secret", monthly_cap=1000, console_cap_confirmed=True)
    assert provider.enabled is True


def test_settings_default_to_no_paid_providers_enabled() -> None:
    settings = Settings(_env_file=None)
    assert not any(p.enabled for p in settings.paid_providers.values())


# --- Hosted-provider URLs paste in unedited --------------------------------


@pytest.mark.parametrize(
    "given",
    [
        "postgresql://u:p@host.neon.tech/db?sslmode=require",
        "postgres://u:p@host.neon.tech/db?sslmode=require",
        "postgresql+psycopg://u:p@host.neon.tech/db?sslmode=require",
    ],
)
def test_database_url_is_coerced_onto_psycopg3(given: str) -> None:
    settings = Settings(_env_file=None, database_url=given)
    assert settings.database_url.startswith("postgresql+psycopg://")
    # the credentials and query string must survive the rewrite untouched
    assert settings.database_url.endswith("@host.neon.tech/db?sslmode=require")
