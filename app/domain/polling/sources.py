"""Availability source registry - PART 0.1.

PLAN 0.1 asks us to "record rate limits and Terms of Service per source".
That is enforced here rather than written in a notebook: a source with no
recorded terms and no explicit authorisation **cannot be polled**. The
registry refuses to hand it out.

Same shape as the quota-cap rule in ``config.py``. A rule that lives only in
a document is a rule somebody skips at 2am.

The registry is code, not a database table, so that enabling a new source is
a reviewable diff rather than a row somebody inserted.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class AuthMode(enum.StrEnum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    OCPI_TOKEN = "ocpi_token"


class SourceNotAuthorisedError(RuntimeError):
    """Raised when code tries to poll a source that has not been cleared.

    Not a technical failure - a governance one. Fix it by completing the
    registry entry, not by catching this.
    """

    def __init__(self, name: str, reason: str) -> None:
        super().__init__(
            f"polling: source {name!r} is not authorised for polling - {reason}. "
            "Complete its registry entry in app/domain/polling/sources.py."
        )


@dataclass(frozen=True)
class SourceSpec:
    """Everything that must be known before a single request is sent."""

    name: str
    adapter: str
    base_url: str

    #: Where the terms permitting this access are written down. Required.
    terms_url: str | None
    #: What those terms actually say about automated access. Required.
    terms_note: str | None
    #: Documented or observed ceiling. Required - "unknown" is not a rate limit.
    rate_limit_per_minute: int | None

    auth_mode: AuthMode = AuthMode.NONE

    #: Set True only after a human has read the terms and confirmed that
    #: 5-minute automated polling is permitted, or a written agreement is in
    #: place. This is the flag that actually gates traffic.
    authorised: bool = False

    #: Turn a source off without deleting its recorded terms.
    enabled: bool = False

    #: Researched (2026-08-15) route to this network's availability WITHOUT OCPI
    #: and WITHOUT an app capture - the finding from CPO_SOURCES.md, surfaced so
    #: the console shows which networks are realistic occupancy targets on the
    #: public web and which are app-only. Descriptive, not a gate.
    public_route: str | None = None

    def blocking_reason(self) -> str | None:
        """Why this source may not be polled, or None if it may."""
        if not self.enabled:
            return "not enabled"
        if not self.authorised:
            return "authorised=False; nobody has confirmed the terms permit polling"
        if not self.terms_url or not self.terms_note:
            return "terms_url/terms_note not recorded (PLAN 0.1)"
        if not self.rate_limit_per_minute or self.rate_limit_per_minute <= 0:
            return "rate_limit_per_minute not recorded"
        return None

    @property
    def pollable(self) -> bool:
        return self.blocking_reason() is None

    def min_interval_seconds(self) -> float:
        """Seconds to wait between requests to respect the recorded limit."""
        if not self.rate_limit_per_minute:
            raise SourceNotAuthorisedError(self.name, "no rate limit recorded")
        return 60.0 / self.rate_limit_per_minute


# ---------------------------------------------------------------------------
# The registry
#
# Strategy (PLAN 0.1, decided): SCRAPE FIRST, OCPI WHEN PARTNERED. The
# dataset cannot be backfilled, so polling starts on each app's own JSON
# endpoint (discovered once via mitmproxy/devtools) and upgrades to the
# operator's official OCPI feed when a partner token lands from the PLAN 0.3
# conversations. `source` on every event row records which rows came from
# which - scraped history stays, official data takes over from that date.
#
# Every CPO app below (ChargeZone, Statiq, Kazam, chargeMOD, Tata Power EZ,
# Ather Grid, Jio-bp) is a `scrape` source, handled by one generic adapter and
# one tolerant normaliser. They differ only in endpoint and status vocabulary.
#
# ⚠️ These networks OVERLAP. Many physical chargers roam over OCPI, so the same
# unit surfaces in several apps under different station ids. We deliberately
# keep every source's own observation - the overlap is signal (it maps the
# roaming graph and cross-checks occupancy), and it is deduped downstream at
# analysis time on distance + operator + connector fingerprint (PLAN 2.3),
# never thrown away at poll time.
#
# Scrape-first does NOT mean scrape-silently. Scraping a consumer app's
# private endpoint is a decision with legal weight, so every source is a
# recorded decision: read the terms, write down what they say and the rate
# limit, then flip `authorised` - that flip IS the recorded decision, and it
# is a reviewable diff. The registry refuses traffic to any source where
# that has not happened. Operational config (endpoint, rate limit) then comes
# from settings; config alone never grants permission.
#
# OCPI ships authorised because it is an open roaming standard designed for
# exactly this: the operator's token is the permission. Fill in base_url and
# a token per partner as CPO conversations conclude.
# ---------------------------------------------------------------------------


def _scrape_todo(app: str) -> str:
    return (
        f"TODO: discover {app}'s JSON stations endpoint (mitmproxy/devtools), read "
        "its ToS, record terms_url + terms_note + rate_limit here, then flip "
        "authorised (PLAN 0.1 scrape-first). Set the endpoint in settings. "
        "Upgrade to OCPI when a partner token lands (0.3)."
    )


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        name="ocpi_partner",
        adapter="ocpi",
        base_url="",  # per-partner, from config
        terms_url="https://evroaming.org/ocpi/",
        terms_note=(
            "Open roaming protocol. Access is granted per-partner via a "
            "credentials handshake; the token itself is the permission."
        ),
        rate_limit_per_minute=60,
        auth_mode=AuthMode.OCPI_TOKEN,
        authorised=True,
        enabled=False,  # flip on once a partner token exists
        public_route="OCPI roaming feed (the later-upgrade path, per partner token)",
    ),
    SourceSpec(
        name="plugshare",
        adapter="unimplemented",
        base_url="https://www.plugshare.com",
        terms_url="https://company.plugshare.com/terms.html",
        terms_note=(
            "TODO: read and summarise. Public site terms generally restrict "
            "automated collection. Seek a data agreement before enabling."
        ),
        rate_limit_per_minute=None,
        authorised=False,
        enabled=False,
        public_route="Commercial license only; real-time is mostly crowd-sourced. ToS "
        "forbids scraping.",
    ),
    # --- Scraped CPO apps. One generic `scrape` adapter serves them all. -----
    # base_url + rate_limit come from settings at poll time; the values here
    # stay blank/None on purpose so the registry holds only governance facts.
    SourceSpec(
        name="chargezone",
        adapter="scrape",
        base_url="",
        terms_url=None,
        terms_note=_scrape_todo("ChargeZone"),
        rate_limit_per_minute=None,
        authorised=False,
        enabled=False,
        public_route="App-only for live status: its public web locator shows locations, no "
        "free/busy. Needs app capture or OCPI.",
    ),
    SourceSpec(
        name="statiq",
        adapter="scrape",
        base_url="",
        terms_url=None,
        terms_note=_scrape_todo("Statiq"),
        rate_limit_per_minute=None,
        authorised=False,
        enabled=False,
        public_route="PUBLIC WEB (2026-08-15): per-connector live status is in the page HTML "
        "(SSR) at statiq.in/ev-charging-station - parse per station, no clean JSON. Robots "
        "permit crawl.",
    ),
    SourceSpec(
        name="kazam",
        adapter="scrape",
        base_url="",
        terms_url=None,
        terms_note=_scrape_todo("Kazam"),
        rate_limit_per_minute=None,
        authorised=False,
        enabled=False,
        public_route="App-only: no public web map; operator CMS is login-gated. Runs an OCPI "
        "platform - ask for a token instead.",
    ),
    SourceSpec(
        name="chargemod",
        adapter="scrape",
        base_url="",
        terms_url=None,
        terms_note=_scrape_todo("chargeMOD"),
        rate_limit_per_minute=None,
        authorised=False,
        enabled=False,
        public_route="OURS - read occupancy from our own backend/CSMS/DB directly. Do NOT "
        "scrape the app (superseded 2026-08-15).",
    ),
    SourceSpec(
        name="tata_power_ez",
        adapter="scrape",
        base_url="",
        terms_url=None,
        terms_note=_scrape_todo("Tata Power EZ"),
        rate_limit_per_minute=None,
        authorised=False,
        enabled=False,
        public_route="CONFIRMED IN BROWSER (2026-08-15): ezcharge.tatapower.com/evselfcare "
        "map loads with NO user login and POSTs to HobsIntegration/syncRequestHandler?service="
        "GET_CHARGING_STATIONS_ALL. Carries LIVE occupancy (app has 'only available/free' "
        "filters; reads stationStatus/availability). BUT the call needs an app-level credential "
        "embedded in the page - a clean replay returns app-level 401 - so treat it like an app "
        "capture (token upkeep + a human authorise), not an open feed. ToS = a customer service "
        "agreement, no explicit anti-scraping clause.",
    ),
    SourceSpec(
        name="ather_grid",
        adapter="scrape",
        base_url="",
        terms_url=None,
        terms_note=_scrape_todo("Ather Grid"),
        rate_limit_per_minute=None,
        authorised=False,
        enabled=False,
        public_route="App-only on its own site (Cloudflare-gated, /api disallowed). Live status "
        "reachable only via Google Maps (Ather feeds Google).",
    ),
    SourceSpec(
        name="jio_bp",
        adapter="scrape",
        base_url="",
        terms_url=None,
        terms_note=_scrape_todo("Jio-bp"),
        rate_limit_per_minute=None,
        authorised=False,
        enabled=False,
        public_route="App-only for live status: the public site lists locations and says to check "
        "availability in the app. Needs app capture or OCPI.",
    ),
)

BY_NAME: dict[str, SourceSpec] = {s.name: s for s in SOURCES}


def pollable_sources() -> tuple[SourceSpec, ...]:
    """Only the sources cleared to receive traffic."""
    return tuple(s for s in SOURCES if s.pollable)


def get(name: str) -> SourceSpec:
    try:
        return BY_NAME[name]
    except KeyError:
        raise SourceNotAuthorisedError(name, "not in the registry") from None


def require_pollable(name: str) -> SourceSpec:
    """Fetch a source, refusing if it is not cleared."""
    spec = get(name)
    reason = spec.blocking_reason()
    if reason:
        raise SourceNotAuthorisedError(name, reason)
    return spec
