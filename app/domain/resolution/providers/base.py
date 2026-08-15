"""What every geocoder in the cascade has in common - PART 1.3.

Two things live here and nothing else:

``GeocodeResult``
    One provider's answer, in a shape that is deliberately source-agnostic so
    Nominatim's answer can be compared against Ola's or Google's. The
    disagreement rule in ``geocode.classify_geocode`` only works because these
    are the same type.

``Geocoder``
    A structural protocol. No base class: a geocoder is anything with a
    ``source`` and a ``search``, which keeps the test fakes honest (they
    implement the protocol rather than inheriting a half-mocked parent) and
    keeps a provider module importable without dragging the cascade in.

Note what is *not* here: a session, a quota counter, a price. A provider does
HTTP and parses the reply. Metering is applied from the outside by
``providers/metered.py``, so "every paid call is metered" is a property of how
the cascade is assembled rather than a rule each provider must remember.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx


class GeocoderError(RuntimeError):
    """The provider answered, but not with an address.

    Distinct from "no result" on purpose. A revoked key, an exhausted quota or
    a malformed request must NOT look like "this address does not exist" -
    that would cache a miss for every address we asked while the key was bad,
    and the cache does not expire.
    """

    def __init__(self, source: str, detail: str) -> None:
        super().__init__(f"{source}: {detail}")
        self.source = source
        self.detail = detail


@dataclass(frozen=True)
class GeocodeResult:
    """One geocoder's answer for one query."""

    lat: float
    lng: float
    source: str
    display_name: str | None = None
    #: The matched address's own PIN, when the provider returns one - used to
    #: corroborate the PIN the customer supplied.
    postcode: str | None = None
    #: Nominatim's 0-1 importance. A weak signal, kept for the console and for
    #: tie-breaking, never trusted as a calibrated probability.
    importance: float | None = None
    raw: dict[str, Any] | None = None

    #: The provider matched only part of the query - Google says so explicitly
    #: with ``partial_match``. This is the single most useful doubt signal any
    #: geocoder gives us, because a partial match is confident and wrong: ask
    #: for a village and get the district headquarters, with no error at all.
    partial: bool = False

    #: The provider's own stable handle for the place: Mappls ``eLoc`` (PLAN
    #: 1.3 L4 asks for it by name), Google ``place_id``, Ola ``place_id``.
    #: Worth keeping because it re-fetches the same match for free later.
    place_id: str | None = None


@runtime_checkable
class Geocoder(Protocol):
    """One level of the cascade.

    ``search`` returns ``None`` for a clean miss (the provider looked and found
    nothing) and raises ``GeocoderError`` or an ``httpx`` error for anything
    else. The cascade treats those differently: a miss falls through quietly, a
    failure is recorded as a reason and *then* falls through.
    """

    source: str

    def search(
        self, client: httpx.Client, query: str, *, pincode: str | None = None
    ) -> GeocodeResult | None: ...


def to_float(value: Any) -> float | None:
    """Coordinates arrive as strings from about half of these APIs."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def component(components: Any, wanted: str) -> str | None:
    """Pull one Google-style address component (``types``/``long_name``).

    Ola Maps copied Google's response shape, so both use this.
    """
    if not isinstance(components, list):
        return None
    for item in components:
        if not isinstance(item, dict):
            continue
        types = item.get("types")
        if isinstance(types, list) and wanted in types:
            value = item.get("long_name") or item.get("short_name")
            return str(value) if value else None
    return None
