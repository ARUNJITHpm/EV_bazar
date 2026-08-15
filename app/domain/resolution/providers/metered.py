"""The wrapper that makes a paid geocoder a metered geocoder - PART 1.3 / C.1.

AGENTS.md constraint 10 says every metered external call writes an
``api_usage_events`` row before its response is used. There are two ways to
honour that: ask each provider module to remember, or make it impossible to add
a paid provider to the cascade without it. This is the second.

``build_cascade`` is the only place a paid geocoder is constructed, and it
constructs them wrapped. A provider added without a wrapper is not a provider
that quietly skips metering - it is a provider the cascade has no way to reach.

**This object is bound to one Session and one unit of work.** That is the
deliberate cost of keeping the provider modules free of any database: the
metering has to get the session from somewhere, and a constructor argument is
visible where a hidden global is not. Build the cascade inside the session
scope; do not stash the list on a module or hand it to another thread.
"""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.config import PaidProvider
from app.domain.resolution.providers.base import Geocoder, GeocodeResult
from app.metering import PriceCard, meter
from app.models.api_usage import UsageStatus


class MeteredGeocoder:
    """Wraps a geocoder so that every call it makes is priced and recorded."""

    def __init__(
        self,
        inner: Geocoder,
        *,
        session: Session,
        provider: str,
        config: PaidProvider,
        card: PriceCard,
        caused_by: str = "geocode_cascade",
        operation: str = "geocode",
    ) -> None:
        self.inner = inner
        #: Plain attribute, not a property: the ``Geocoder`` protocol declares
        #: ``source`` as a settable variable, and a read-only property does not
        #: satisfy it. The wrapper reports the wrapped provider's name so the
        #: cascade trail and the usage rows agree on what to call this level.
        self.source = inner.source
        self.session = session
        self.provider = provider
        self.config = config
        self.card = card
        self.caused_by = caused_by
        self.operation = operation

    def search(
        self, client: httpx.Client, query: str, *, pincode: str | None = None
    ) -> GeocodeResult | None:
        """Meter, then call.

        Nothing is caught here. ``meter()`` writes the usage row in a ``finally``,
        so an error or a refusal at cap is recorded *before* the exception
        leaves this method; deciding whether the cascade should continue past
        that failure is the cascade's job, not the wrapper's, and it is made in
        exactly one place (``geocode.py``).
        """
        with meter(
            self.session,
            provider=self.provider,
            operation=self.operation,
            config=self.config,
            card=self.card,
            caused_by=self.caused_by,
        ) as measurement:
            result = self.inner.search(client, query, pincode=pincode)
            # One call, one billable unit - a miss costs exactly what a hit
            # costs, which is the whole reason the free levels come first.
            measurement.record(
                units_in=1,
                status=UsageStatus.OK,
                resolved=result is not None,
                query_chars=len(query),
            )
            return result
