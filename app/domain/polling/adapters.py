"""Source adapters - PART 0.1.

Fetching and interpreting are two jobs and this module keeps them apart:

    fetch_raw()   HTTP only. Returns the response bodies, untouched, in the
                  order they arrived. Nothing here decides what a status word
                  means, so nothing here can be wrong in a way that costs data.
    normalise()   pure, delegates to ``normalise.py``.

They are separate because the raw pages are archived *before* anything
interprets them (PLAN 0.1, table 1). Fusing the two - which is what this
module used to do - means a payload only ever exists in its already-parsed
form, and a parsing mistake is then permanent.

An adapter does not decide whether it is allowed to run.
``sources.require_pollable`` does that, before one is ever constructed.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Protocol

import httpx

from app.domain.polling.normalise import (
    ChargerObservation,
    dedupe,
    from_ocpi_locations,
    from_scraped_stations,
)
from app.domain.polling.sources import SourceSpec

#: One response body. A bare JSON array is legal - some CPO apps return the
#: station list at the top level rather than under a key.
RawPage = dict[str, Any] | list[Any]


class Adapter(Protocol):
    """Fetch current availability for one source."""

    spec: SourceSpec

    def fetch_raw(self, client: httpx.Client) -> tuple[RawPage, ...]: ...

    def normalise(
        self, pages: tuple[RawPage, ...], *, observed_at: dt.datetime
    ) -> tuple[ChargerObservation, ...]: ...

    def fetch(
        self, client: httpx.Client, *, observed_at: dt.datetime
    ) -> tuple[ChargerObservation, ...]: ...


class OcpiAdapter:
    """OCPI 2.2 ``GET /locations``, paginated.

    OCPI is an open roaming protocol: a partner issues a token, and
    machine-readable availability is the protocol's entire purpose. This is
    the path to prefer over scraping a consumer app, and most CPOs will issue
    a credential because roaming visibility drives their utilisation too.
    """

    #: Stop after this many pages. A feed that paginates forever - or a
    #: cursor bug on their side - must not turn one 5-minute cycle into an
    #: unbounded crawl that misses the next one.
    MAX_PAGES = 200

    def __init__(self, spec: SourceSpec, token: str, base_url: str | None = None) -> None:
        self.spec = spec
        self.token = token
        self.base_url = (base_url or spec.base_url).rstrip("/")

    def fetch_raw(self, client: httpx.Client) -> tuple[RawPage, ...]:
        """Every page of the feed, in order, exactly as received.

        Raises on any non-2xx. A partial crawl must fail the whole cycle
        rather than return what it managed: the caller derives disappearance
        from absence, so a truncated page 3 would read as "everything after
        page 2 has vanished".
        """
        pages: list[RawPage] = []
        url: str | None = f"{self.base_url}/locations"
        headers = {
            "Authorization": f"Token {self.token}",
            "Accept": "application/json",
        }

        for page in range(self.MAX_PAGES):
            if url is None:
                break

            # Only the FIRST request carries params. A `next` URL already has
            # the cursor in its query string, and httpx *replaces* the query
            # when `params` is passed - so re-sending them silently resets
            # pagination to page one. The feed then looks complete while
            # containing only its first page, which is exactly the kind of
            # invisible loss this dataset cannot tolerate.
            response = (
                client.get(url, headers=headers, params={"limit": 100})
                if page == 0
                else client.get(url, headers=headers)
            )
            response.raise_for_status()
            pages.append(response.json())

            # OCPI paginates via a Link header; absence means we are done.
            url = _next_link(response.headers.get("Link"))

        return tuple(pages)

    def normalise(
        self, pages: tuple[RawPage, ...], *, observed_at: dt.datetime
    ) -> tuple[ChargerObservation, ...]:
        observations: list[ChargerObservation] = []
        for page in pages:
            if isinstance(page, dict):
                observations.extend(
                    from_ocpi_locations(page, source=self.spec.name, observed_at=observed_at)
                )
        return dedupe(tuple(observations))

    def fetch(
        self, client: httpx.Client, *, observed_at: dt.datetime
    ) -> tuple[ChargerObservation, ...]:
        """Convenience for --dry-run and tests. The poller uses the two halves
        separately so it can archive the raw pages in between."""
        return self.normalise(self.fetch_raw(client), observed_at=observed_at)


class ScrapeAdapter:
    """One scraped CPO app's stations endpoint - the scrape-first path (0.1).

    Generic across every scraped source (ChargeZone, Statiq, Kazam, chargeMOD,
    Tata Power EZ, Ather Grid, Jio-bp): they differ only in endpoint and status
    words, both handled by config + ``from_scraped_stations``. One instance per
    source, its ``base_url``/``path``/``api_key`` supplied by the poller from
    settings.

    One GET, one JSON body. If a real endpoint paginates, add a loop in
    ``fetch_raw`` modelled on ``OcpiAdapter`` - but most single-operator "all
    my stations" endpoints return everything at once.
    """

    def __init__(
        self,
        spec: SourceSpec,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        path: str = "/stations",
    ) -> None:
        self.spec = spec
        self.base_url = (base_url or spec.base_url).rstrip("/")
        self.api_key = api_key
        #: The endpoint path discovered from the app's traffic. Override via
        #: config once captured; the default is a placeholder.
        self.path = path

    def fetch_raw(self, client: httpx.Client) -> tuple[RawPage, ...]:
        headers = {"Accept": "application/json"}
        # First-party token if the endpoint needs one; harmless if it does not.
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = client.get(f"{self.base_url}{self.path}", headers=headers)
        response.raise_for_status()
        page: RawPage = response.json()
        return (page,)

    def normalise(
        self, pages: tuple[RawPage, ...], *, observed_at: dt.datetime
    ) -> tuple[ChargerObservation, ...]:
        observations: list[ChargerObservation] = []
        for page in pages:
            observations.extend(
                from_scraped_stations(page, source=self.spec.name, observed_at=observed_at)
            )
        return dedupe(tuple(observations))

    def fetch(
        self, client: httpx.Client, *, observed_at: dt.datetime
    ) -> tuple[ChargerObservation, ...]:
        """Convenience for --dry-run and tests. The poller uses the two halves
        separately so it can archive the raw pages in between."""
        return self.normalise(self.fetch_raw(client), observed_at=observed_at)


class TataEzChargeAdapter:
    """Tata Power EZ Charge's public web-map endpoint - PART 0.1, PLAN 2.3 research.

    Confirmed in a browser (2026-08-15, see CPO_SOURCES.md): the ezcharge map
    loads with NO user login and its station data comes from a single
    ``POST /HobsIntegration/syncRequestHandler?service=GET_CHARGING_STATIONS_ALL``
    that carries live occupancy (``stationStatus``). It differs from the generic
    ``ScrapeAdapter`` in three ways this class handles: it is a POST, it needs a
    ``service`` + per-request ``transid`` in the query string, and the station
    list comes back wrapped under ``statusList`` (handled in ``normalise.py``).

    ⚠️ TWO THINGS ARE UNVERIFIED until one authorised ``--dry-run``, because a
    clean replay without the app's embedded credential returns an app-level 401:

      1. THE AUTH MECHANISM. The token below (from ``api_key`` in config) is sent
         as an ``Authorization: Bearer`` header - a documented ASSUMPTION. The
         real header name / whether it belongs in the body was redacted in
         capture. If dry-run returns a 401 envelope, correct ``_auth_headers``.
      2. THE EXACT SUCCESS FIELDS. ``normalise.from_scraped_stations`` reads
         ``stationStatus`` and a tolerant set of id keys; adjust those if the
         real record names them differently.

    Governance unchanged: this is a scrape of a third party under an app
    credential, so it stays ``authorised=False`` in ``sources.py`` until a human
    reads the ToS and decides - and supplies the token in ``.env``. Nothing here
    grants that permission; it only makes the request the moment permission does.
    """

    SERVICE = "GET_CHARGING_STATIONS_ALL"

    def __init__(
        self,
        spec: SourceSpec,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        path: str = "/HobsIntegration/syncRequestHandler",
    ) -> None:
        self.spec = spec
        self.base_url = (base_url or spec.base_url).rstrip("/")
        self.api_key = api_key
        self.path = path

    def _auth_headers(self) -> dict[str, str]:
        # ASSUMPTION (confirm in dry-run): bearer token. See class docstring.
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def fetch_raw(self, client: httpx.Client) -> tuple[RawPage, ...]:
        response = client.post(
            f"{self.base_url}{self.path}",
            params={"service": self.SERVICE, "transid": str(uuid.uuid4())},
            headers=self._auth_headers(),
            json={},
            timeout=30.0,
        )
        response.raise_for_status()
        page: RawPage = response.json()
        return (page,)

    def normalise(
        self, pages: tuple[RawPage, ...], *, observed_at: dt.datetime
    ) -> tuple[ChargerObservation, ...]:
        observations: list[ChargerObservation] = []
        for page in pages:
            observations.extend(
                from_scraped_stations(page, source=self.spec.name, observed_at=observed_at)
            )
        return dedupe(tuple(observations))

    def fetch(
        self, client: httpx.Client, *, observed_at: dt.datetime
    ) -> tuple[ChargerObservation, ...]:
        """Convenience for --dry-run and tests; the poller uses the halves apart."""
        return self.normalise(self.fetch_raw(client), observed_at=observed_at)


def _next_link(link_header: str | None) -> str | None:
    """Extract ``rel="next"`` from an RFC 5988 Link header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        section = part.split(";")
        if len(section) < 2:
            continue
        if 'rel="next"' in section[1].replace(" ", "").replace("'", '"'):
            return section[0].strip().strip("<>")
    return None
