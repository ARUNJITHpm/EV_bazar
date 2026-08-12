"""Application settings.

Rule 5 / hard constraint 7 from AGENTS.md is enforced here, at import time:

    "No paid API call without a hard quota cap already configured in the
     provider console *and* a client-side counter."

A paid provider that has an API key but no ``monthly_cap`` raises at startup.
The app will not boot. That is deliberate - one runaway loop is Rs 40,000.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PaidProvider(BaseModel):
    """A metered third-party API.

    ``monthly_cap`` is the client-side counter's ceiling. It is not a
    substitute for the cap set in the provider's own console - it is the
    second of the two locks the rule requires.
    """

    api_key: str | None = None
    monthly_cap: int | None = None
    console_cap_confirmed: bool = False

    @property
    def enabled(self) -> bool:
        return self.api_key is not None

    @model_validator(mode="after")
    def _key_requires_cap(self) -> PaidProvider:
        if self.api_key is None:
            return self
        if self.monthly_cap is None or self.monthly_cap <= 0:
            raise ValueError(
                "AGENTS.md constraint 7: an API key was configured without a positive "
                "monthly_cap. Set the cap, or remove the key."
            )
        if not self.console_cap_confirmed:
            raise ValueError(
                "AGENTS.md constraint 7: set console_cap_confirmed=true only after you "
                "have set a hard quota cap in the provider's own console. The "
                "client-side counter alone is not sufficient."
            )
        return self


class ScrapeSource(BaseModel):
    """Operational config for one scraped CPO app (PLAN 0.1).

    The *governance* facts (has anyone read the terms, is it authorised) live
    in ``app/domain/polling/sources.py`` - a reviewable diff, not an env var.
    This holds only the deployment values: the endpoint discovered off the
    app's traffic, and the rate limit observed for it.

    ``base_url`` blank => the source is not configured and is simply not
    polled. It never polls the empty string.
    """

    base_url: str = ""
    stations_path: str = "/stations"
    api_key: str | None = None
    #: Requests/minute the endpoint tolerates. Recorded so the registry has a
    #: real number rather than "unknown" (PLAN 0.1). Adjust to what is observed.
    rate_limit_per_minute: int = 30

    @property
    def configured(self) -> bool:
        return bool(self.base_url)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    env: Literal["dev", "test", "prod"] = "dev"
    debug: bool = False

    # Vite dev server. Dev only - in production Caddy serves dist/ and
    # proxies /api, so the SPA and the API are same-origin.
    frontend_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    database_url: str = "postgresql+psycopg://evsite:evsite@localhost:5432/evsite"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg3_driver(cls, v: str) -> str:
        """Coerce the scheme onto psycopg3.

        Hosted providers (Neon, Supabase, Heroku, RDS consoles) hand out
        ``postgres://`` or ``postgresql://`` URLs. SQLAlchemy maps both to
        psycopg2, which we deliberately do not install - STACK.md pins
        ``psycopg[binary]``, which is psycopg3. Rewriting here means the URL
        can be pasted from any console unedited.
        """
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    # --- Geocoding cascade (PLAN 1.3) -------------------------------------
    # L2 Nominatim is self-hosted, so it is free and has no cap.
    nominatim_url: str = "http://localhost:8080"

    # L3/L4/L5 are metered. Each is gated by the validator above.
    ola_maps: PaidProvider = Field(default_factory=PaidProvider)
    mappls: PaidProvider = Field(default_factory=PaidProvider)
    google_maps: PaidProvider = Field(default_factory=PaidProvider)

    # Two geocoders disagreeing by more than this go to the manual queue
    # instead of being silently resolved. PLAN 1.3 escalation rule.
    geocode_disagreement_limit_m: int = 2000

    # PLAN 1.4 - reject a point that falls further than this from any district
    district_nearest_fallback_m: int = 5000
    # ...and flag it if it sits this close to a district line (two tariff regimes)
    boundary_ambiguous_m: int = 500

    # --- Operations console (PLAN C.0) -------------------------------------
    # One operator, one password, a signed httpOnly cookie. The console
    # exposes CPO commercial terms and our own spend, so it is the most
    # sensitive surface in the product - and the guard is on the server, never
    # in the router.
    #
    # Generate the hash with:  uv run python -m scripts.console_password
    console_operator: str = "operator"
    console_secret_key: str | None = None
    console_password_hash: str | None = None
    #: 12 hours. Long enough not to be a nuisance, short enough that a laptop
    #: left in a cafe is not a standing invitation.
    console_session_max_age_seconds: int = 12 * 3600

    @property
    def console_configured(self) -> bool:
        return bool(self.console_secret_key and self.console_password_hash)

    # --- Poller (PLAN 0.1) -------------------------------------------------
    poller_interval_seconds: int = 300
    poller_deadman_minutes: int = 30

    # Scraped CPO apps (PLAN 0.1). One nested block each; env is e.g.
    # ``CHARGEZONE__BASE_URL=...`` (nested delimiter ``__``). A source is polled
    # only when BOTH its base_url is set here AND it is authorised in
    # sources.py - config alone never grants permission. chargeMOD is one of
    # these like any other; many chargers recur across networks because they
    # roam over OCPI, so the same physical unit is seen from several apps - that
    # overlap is kept and deduped downstream (PLAN 2.3), not at poll time.
    chargezone: ScrapeSource = Field(default_factory=ScrapeSource)
    statiq: ScrapeSource = Field(default_factory=ScrapeSource)
    kazam: ScrapeSource = Field(default_factory=ScrapeSource)
    chargemod: ScrapeSource = Field(default_factory=ScrapeSource)
    tata_power_ez: ScrapeSource = Field(default_factory=ScrapeSource)
    ather_grid: ScrapeSource = Field(default_factory=ScrapeSource)
    jio_bp: ScrapeSource = Field(default_factory=ScrapeSource)

    @property
    def scrape_sources(self) -> dict[str, ScrapeSource]:
        """Scraped sources keyed by the name they carry in the registry."""
        return {
            "chargezone": self.chargezone,
            "statiq": self.statiq,
            "kazam": self.kazam,
            "chargemod": self.chargemod,
            "tata_power_ez": self.tata_power_ez,
            "ather_grid": self.ather_grid,
            "jio_bp": self.jio_bp,
        }

    @property
    def paid_providers(self) -> dict[str, PaidProvider]:
        return {
            "ola_maps": self.ola_maps,
            "mappls": self.mappls,
            "google_maps": self.google_maps,
        }

    @model_validator(mode="after")
    def _console_must_be_locked_in_prod(self) -> Settings:
        """Refuse to boot a production console without a password.

        Same shape as the quota-cap rule above: the failure is loud and at
        startup, rather than quiet and at 2am. In dev the console is allowed
        to be unconfigured, but the guarded endpoints then return 503 rather
        than opening - "not set up" must never mean "not protected".
        """
        if self.env == "prod" and not self.console_configured:
            raise ValueError(
                "PLAN C.0: the console exposes CPO terms and our own spend, and this "
                "deployment has no console_secret_key/console_password_hash. Generate one "
                "with `uv run python -m scripts.console_password`, or do not run prod."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
