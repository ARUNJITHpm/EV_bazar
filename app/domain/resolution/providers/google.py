"""L5 of the cascade - Google. PART 1.3. **Last resort, and the expensive one.**

Part 1's exit criterion is that ≥90% of addresses resolve without reaching this
module. It is here for the tail that Nominatim, Ola and Mappls all miss, and
every call it makes is reviewed (PLAN 1.3: "every Google-escalated case
reviewed → normalisation backlog written").

Two things this module gets right that a three-line wrapper would not:

**Status is not the same as emptiness.** Google returns HTTP 200 for
``REQUEST_DENIED`` and ``OVER_QUERY_LIMIT``. Reading ``results`` and finding it
empty would record "this address does not exist" for every address we asked
while the key was revoked - and the geocode cache does not expire, so that
mistake outlives the outage that caused it. Only ``ZERO_RESULTS`` is a miss.

**``partial_match`` is carried through.** It is Google saying "I matched
something, but not what you asked for" - typically the district headquarters
when you asked for a village. That is a confident, well-formed, wrong answer,
and it is the doubt signal that makes the cascade's escalation rule fire.

Billing note (PLAN 1.3 L5): bill through an Indian entity - 70k free Essentials
calls/month against 10k global. The price card ships with the conservative
10,000; see ``app/metering/cards.py``.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.domain.resolution.providers.base import (
    GeocoderError,
    GeocodeResult,
    component,
    to_float,
)

SOURCE = "google_maps"


def parse_geocode(payload: Any, *, source: str = SOURCE) -> GeocodeResult | None:
    """Top hit from a Google ``/geocode/json`` body, or None. Pure."""
    if not isinstance(payload, dict):
        raise GeocoderError(source, f"expected an object, got {type(payload).__name__}")

    status = str(payload.get("status", ""))
    if status == "ZERO_RESULTS":
        return None
    if status != "OK":
        # OVER_QUERY_LIMIT, REQUEST_DENIED, INVALID_REQUEST, UNKNOWN_ERROR, or
        # something Google added since. All of them mean "no answer", none of
        # them means "no such place".
        detail = payload.get("error_message")
        raise GeocoderError(source, f"status={status}" + (f": {detail}" if detail else ""))

    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return None
    top = results[0]
    if not isinstance(top, dict):
        return None

    location = top.get("geometry", {})
    location = location.get("location") if isinstance(location, dict) else None
    if not isinstance(location, dict):
        return None

    lat = to_float(location.get("lat"))
    lng = to_float(location.get("lng"))
    if lat is None or lng is None:
        return None

    place_id = top.get("place_id")
    return GeocodeResult(
        lat=lat,
        lng=lng,
        source=source,
        display_name=top.get("formatted_address"),
        postcode=component(top.get("address_components"), "postal_code"),
        raw=top,
        partial=bool(top.get("partial_match")),
        place_id=str(place_id) if place_id else None,
    )


class GoogleGeocoder:
    """Google Geocoding API, constrained to India."""

    source = SOURCE

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://maps.googleapis.com",
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search(
        self, client: httpx.Client, query: str, *, pincode: str | None = None
    ) -> GeocodeResult | None:
        if not query and not pincode:
            return None

        # ``components`` is a hard filter, not a hint: it stops "Salem" landing
        # in Oregon, and a supplied PIN becomes a real constraint rather than
        # another token competing with the street name.
        components = ["country:IN"]
        if pincode:
            components.append(f"postal_code:{pincode}")

        params: dict[str, str] = {
            "components": "|".join(components),
            "key": self.api_key,
        }
        if query:
            params["address"] = query

        response = client.get(
            f"{self.base_url}/maps/api/geocode/json", params=params, timeout=self.timeout
        )
        response.raise_for_status()
        return parse_geocode(response.json(), source=self.source)
