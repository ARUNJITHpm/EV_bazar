"""Overpass API client - the fetch half of PART 2.1/2.2.

OpenStreetMap's query endpoint: free, keyless, and the planned source for the
road and POI layers (PLAN 2.1-2.2 name OSM outright). Same discipline as the
Nominatim geocoder: an identifying User-Agent and a politeness throttle are
enforced structurally here rather than remembered by callers, and this module
does HTTP and nothing else - ``roads.parse_roads`` and ``poi.parse_pois`` are
pure functions over the response body, testable from fixtures.

No quota counter: Overpass is free and unkeyed, so there is nothing to meter
(the ``api_usage_events`` discipline exists for *paid* clients - AGENTS.md
rule 7/10). The public instance's fair-use policy is the constraint, and the
throttle plus the fact that context features are computed once per site and
stored keeps us far inside it.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

#: Same convention as the Nominatim layer: the public instance bans anonymous
#: default agents and asks for a contact.
USER_AGENT = "EVSiteIntelligence/0.1 (software@chargemod.com)"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

#: Fair-use politeness for the public instance, same shape as Nominatim's.
MIN_INTERVAL_S = 1.0


class OverpassClient:
    """Thin, throttled POST wrapper. Fetching only - parsing lives elsewhere."""

    def __init__(
        self,
        base_url: str = OVERPASS_URL,
        *,
        timeout_s: float = 60.0,
        min_interval_s: float = MIN_INTERVAL_S,
    ) -> None:
        self.base_url = base_url
        self.timeout_s = timeout_s
        self.min_interval_s = min_interval_s
        self._last_request = 0.0

    def query(self, overpass_ql: str) -> dict[str, Any]:
        """Run one Overpass QL query, returning the decoded JSON body.

        Raises ``httpx.HTTPError`` on network failure and ``ValueError`` on a
        non-JSON body - callers degrade to "feature pending" rather than
        inventing a road (the context layer's version of "refuse rather than
        guess").
        """
        wait = self.min_interval_s - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

        response = httpx.post(
            self.base_url,
            content=overpass_ql.encode(),
            headers={"User-Agent": USER_AGENT, "Content-Type": "text/plain; charset=utf-8"},
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("Overpass returned a non-object JSON body")
        return body
