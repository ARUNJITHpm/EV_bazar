"""L4 of the cascade - Mappls (MapmyIndia). PART 1.3.

Sits below Ola because its free allowance is an order of magnitude smaller, and
above Google because it is still cheaper and its Indian address coverage -
especially informal addresses, which is most of what a charging site has - is
the best of the three.

PLAN 1.3 asks specifically to **store the eLoc**: Mappls' six-character handle
for a place. It goes into ``GeocodeResult.place_id`` (and so into the geocode
cache), which means a site resolved through Mappls can be re-fetched later for
free, and two sites that resolved to the same eLoc are provably the same place.

Auth note: Mappls issues a short-lived OAuth bearer token from a client
id/secret. We carry the configured ``api_key`` as that bearer token, which is
correct for the REST key flow and for a token minted out of band. If we move to
the OAuth flow, the refresh belongs here, and it belongs *outside* ``meter()`` -
a token refresh is not a geocode and must not consume a geocode unit.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.domain.resolution.providers.base import GeocoderError, GeocodeResult, to_float

SOURCE = "mappls"

#: Mappls signals the outcome with an HTTP-style code inside the body.
_NO_RESULT = {204, 404}


def parse_geocode(payload: Any, *, source: str = SOURCE) -> GeocodeResult | None:
    """Top hit from a Mappls ``/places/geocode`` body, or None. Pure.

    ``copResults`` is an object for a single match and a list for several -
    both shapes are real, and treating the object as a list silently loses
    every single-match geocode.
    """
    if not isinstance(payload, dict):
        raise GeocoderError(source, f"expected an object, got {type(payload).__name__}")

    code = payload.get("responseCode")
    if isinstance(code, int) and code in _NO_RESULT:
        return None
    if isinstance(code, int) and code not in (200, 0):
        raise GeocoderError(source, f"responseCode={code}")

    results = payload.get("copResults")
    if isinstance(results, list):
        results = results[0] if results else None
    if not isinstance(results, dict):
        return None

    lat = to_float(results.get("latitude"))
    lng = to_float(results.get("longitude"))
    if lat is None or lng is None:
        return None

    pincode = results.get("pincode")
    eloc = results.get("eLoc")
    return GeocodeResult(
        lat=lat,
        lng=lng,
        source=source,
        display_name=results.get("formattedAddress"),
        postcode=str(pincode) if pincode else None,
        raw=results,
        place_id=str(eloc) if eloc else None,
    )


class MapplsGeocoder:
    """Mappls forward geocoding."""

    source = SOURCE

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://atlas.mappls.com",
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search(
        self, client: httpx.Client, query: str, *, pincode: str | None = None
    ) -> GeocodeResult | None:
        address = f"{query} {pincode}".strip() if pincode else query
        if not address:
            return None

        response = client.get(
            f"{self.base_url}/api/places/geocode",
            params={"address": address, "itemCount": 1},
            headers={"Authorization": f"bearer {self.api_key}"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return parse_geocode(response.json(), source=self.source)
