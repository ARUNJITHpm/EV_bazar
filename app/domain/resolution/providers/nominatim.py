"""L2 of the cascade - Nominatim. PART 1.3.

Nominatim is the ⭐ layer: free and uncapped, and PLAN 1.3 wants ≥90% of
addresses resolved before any paid geocoder is touched. So this is the
workhorse, and L3-L5 (Ola, Mappls, Google) exist only for what it misses.

Two deployments, one class:

* the **public instance** (nominatim.openstreetmap.org) - no account, no key,
  but a usage policy: an identifying User-Agent and at most 1 request/second.
  Both are enforced structurally here (``USER_AGENT``, ``min_interval_s``)
  rather than remembered by callers - at hundreds of reports a month this is
  comfortably inside the policy, and the cache means no address is ever asked
  twice.
* **self-hosted** from the India OSM extract - parked until volume demands it
  (a 40-80 GB import). Same API, so switching is one URL in ``.env``.

Fetching and parsing are kept apart, the same way the poller's adapters are:
``search`` does HTTP and nothing else; ``parse_search`` is a pure function over
the response body. A status vocabulary or a coordinate we read wrong is then a
bug in a tested pure function, not something entangled with the network.

No quota counter here: this layer is free. The ``meter()`` wrapper enters the
cascade at L3, its first paying caller.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.domain.resolution.providers.base import GeocodeResult, to_float

#: The public instance's policy bans anonymous default agents (httpx's
#: ``python-httpx/x.y`` included) and asks for a contact. Sent on every
#: Nominatim request, self-hosted or not - it costs nothing there.
USER_AGENT = "EVSiteIntelligence/0.1 (software@chargemod.com)"

#: Hostname of the public instance, used by ``build_cascade`` to switch the
#: politeness throttle on without anyone remembering to.
PUBLIC_HOST = "nominatim.openstreetmap.org"

#: Re-exported: ``GeocodeResult`` moved to ``base.py`` when Ola/Mappls/Google
#: joined the cascade and needed to return the same type. Imports of it from
#: here still work, and should - it is the shape a *geocoder* returns.
__all__ = ["GeocodeResult", "NominatimGeocoder", "parse_search"]


def parse_search(payload: Any, *, source: str = "nominatim") -> GeocodeResult | None:
    """First usable hit from a Nominatim ``/search`` body, or None. Pure.

    Nominatim returns a JSON array ordered by relevance. A missing or unparseable
    lat/lon yields None rather than a guessed coordinate - inventing a location
    is the one failure this whole cascade is built to avoid.
    """
    if not isinstance(payload, list) or not payload:
        return None
    top = payload[0]
    if not isinstance(top, dict):
        return None

    lat = to_float(top.get("lat"))
    lng = to_float(top.get("lon"))
    if lat is None or lng is None:
        return None

    address = top.get("address")
    postcode = address.get("postcode") if isinstance(address, dict) else None

    return GeocodeResult(
        lat=lat,
        lng=lng,
        source=source,
        display_name=top.get("display_name"),
        postcode=str(postcode) if postcode else None,
        importance=to_float(top.get("importance")),
        raw=top,
        place_id=str(top["osm_id"]) if top.get("osm_id") else None,
    )


class NominatimGeocoder:
    """Self-hosted Nominatim ``/search``.

    ``countrycodes=in`` is not an optimisation - it stops a bare "Salem" or
    "Palakkad" resolving to a namesake in Oregon or the USA, which on Indian
    input is a wrong answer that looks perfectly confident.
    """

    source = "nominatim"

    def __init__(
        self, base_url: str, *, timeout: float = 10.0, min_interval_s: float = 0.0
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        #: Politeness floor between requests. 0 for self-hosted; ~1.1 s for the
        #: public instance (its policy is "an absolute maximum of 1/second").
        self.min_interval_s = min_interval_s
        self._last_request = 0.0

    def search(
        self, client: httpx.Client, query: str, *, pincode: str | None = None
    ) -> GeocodeResult | None:
        """Resolve one address. Returns None on a clean miss (empty result set).

        The PIN is a structured ``postalcode`` filter ONLY when it is all we
        have. The live API **refuses** ``q`` combined with any structured
        parameter (400: "cannot be used together with 'q'") - a fact the docs
        did not make obvious and the first real call did (FINDINGS D14). So
        with a text query the PIN stays out of the request entirely; it still
        does its work downstream, where ``doubt_about`` compares the match's
        postcode against it and 1.4 cross-checks the polygon.
        """
        if not query and not pincode:
            return None

        params: dict[str, str | int] = {
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "in",
            "addressdetails": 1,
        }
        if query:
            params["q"] = query
        elif pincode:
            params["postalcode"] = pincode

        if self.min_interval_s:
            wait = self.min_interval_s - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)

        response = client.get(
            f"{self.base_url}/search",
            params=params,
            timeout=self.timeout,
            headers={"User-Agent": USER_AGENT},
        )
        self._last_request = time.monotonic()
        response.raise_for_status()
        return parse_search(response.json(), source=self.source)
