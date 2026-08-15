"""Assembling the cascade - PART 1.3.

    L2 nominatim (free)  ->  L3 ola  ->  L4 mappls  ->  L5 google

One function, and it is the only place a paid geocoder is constructed. Three
rules are enforced here rather than trusted to the caller:

1. **Order is cost order.** Free first, then the largest free tier, then the
   smallest, then the one that bills from call one.
2. **A paid level with no API key is simply absent.** Not disabled with a flag,
   not present-but-skipped: absent from the list. The cascade cannot call what
   it does not hold.
3. **A paid level with a key but no price card refuses to build.** ``card_for``
   raises, and it raises here - at assembly, before a single call - rather than
   at the first geocode. A call that cannot be priced is a call that will not
   appear in the spend report at its real cost, and the report is the artefact
   that has to reconcile.

The key-with-no-cap case is already refused earlier still: ``config.py``
validates it at import, so the process does not boot.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.resolution.providers.base import Geocoder
from app.domain.resolution.providers.google import GoogleGeocoder
from app.domain.resolution.providers.mappls import MapplsGeocoder
from app.domain.resolution.providers.metered import MeteredGeocoder
from app.domain.resolution.providers.nominatim import NominatimGeocoder
from app.domain.resolution.providers.ola import OlaGeocoder

#: Provider key in ``Settings.paid_providers`` -> its client class, in the order
#: the cascade should try them. The key is also the ``provider`` string on the
#: price card and on every usage event, so the three cannot drift apart.
PAID_LEVELS = (
    ("ola_maps", OlaGeocoder),
    ("mappls", MapplsGeocoder),
    ("google_maps", GoogleGeocoder),
)


def build_cascade(
    session: Session,
    settings: Settings,
    *,
    on: dt.date | None = None,
    caused_by: str = "geocode_cascade",
) -> list[Geocoder]:
    """The ordered geocoder list for one unit of work.

    Bound to ``session`` because the metered levels write their usage row
    through it - build it inside the session scope and let it go with the
    session (see ``providers/metered.py``).
    """
    from app.metering.cards import card_for  # local: keeps the free path import-light

    levels: list[Geocoder] = [NominatimGeocoder(settings.nominatim_url)]

    paid = settings.paid_providers
    for name, client_cls in PAID_LEVELS:
        config = paid[name]
        if not config.enabled or config.api_key is None:
            continue
        levels.append(
            MeteredGeocoder(
                client_cls(config.api_key),
                session=session,
                provider=name,
                config=config,
                # Raises PriceCardMissingError if nothing prices this provider.
                card=card_for(session, name, "geocode", on=on),
                caused_by=caused_by,
            )
        )

    return levels
