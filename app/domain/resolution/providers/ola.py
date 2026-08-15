"""L3 of the cascade - Ola Maps. PART 1.3. **The first paid level.**

500,000 free calls a month and India-only coverage, which is why it sits ahead
of Mappls and Google: it is the cheapest place to escalate to, and its gazetteer
was built for exactly the addresses we send it.

Ola copied Google's response shape (``geocodingResults`` with
``geometry.location`` and Google-style ``address_components``), so the parsing
here is nearly the same as ``google.py`` - deliberately duplicated rather than
abstracted, because the two will drift and a shared parser would then have to
grow a flag for each divergence.

This module does **not** meter itself. It is wrapped by
``providers/metered.py`` when the cascade is assembled, so a provider cannot be
added to the cascade and quietly skip the usage row.
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

SOURCE = "ola_maps"

#: Ola returns a lowercase ``status``. Only this one means "we looked and found
#: nothing"; anything else unrecognised is an error, not an empty result.
_ZERO = {"zero_results", "not_found"}
_OK = {"ok", "success"}


def parse_geocode(payload: Any, *, source: str = SOURCE) -> GeocodeResult | None:
    """Top hit from an Ola ``/places/v1/geocode`` body, or None. Pure.

    Raises ``GeocoderError`` on a status we do not recognise: a quota or auth
    failure must never be cached as "this address does not exist".
    """
    if not isinstance(payload, dict):
        raise GeocoderError(source, f"expected an object, got {type(payload).__name__}")

    status = str(payload.get("status", "")).lower()
    results = payload.get("geocodingResults")

    if status in _ZERO:
        return None
    if status and status not in _OK:
        raise GeocoderError(
            source, f"status={status!r} {payload.get('error_message') or ''}".strip()
        )

    if not isinstance(results, list) or not results:
        # A 200 with an empty list and no status is still a clean miss.
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
        place_id=str(place_id) if place_id else None,
    )


class OlaGeocoder:
    """Ola Maps forward geocoding.

    The key travels as a query parameter because that is the only form the API
    accepts. It therefore lands in any HTTP access log along the way, which is
    a reason to keep the cap tight rather than a reason not to use it.
    """

    source = SOURCE

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.olamaps.io",
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search(
        self, client: httpx.Client, query: str, *, pincode: str | None = None
    ) -> GeocodeResult | None:
        # Ola has no structured postcode filter, so the PIN goes into the text.
        # It is a strong token for an Indian gazetteer even unstructured.
        address = f"{query} {pincode}".strip() if pincode else query
        if not address:
            return None

        response = client.get(
            f"{self.base_url}/places/v1/geocode",
            params={"address": address, "language": "English", "api_key": self.api_key},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return parse_geocode(response.json(), source=self.source)
