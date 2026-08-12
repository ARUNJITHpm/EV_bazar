"""PART 0.1 - the status poller's domain logic.

    sources.py    registry; refuses to hand out an unauthorised source
    normalise.py  payload -> observations. PURE.
    derive.py     observations + last known state -> transitions. PURE.
    adapters.py   fetch raw pages for one source (HTTP only)
    ingest.py     archive (1), append (2), and the liveness ledger
    health.py     the dead-man's switch

``workers/poller.py`` is the entrypoint. It schedules; it does not think.

Capture and derivation are separate on purpose: the raw archive is written and
committed before anything interprets it, so a bug in the interpretation costs a
recompute rather than a day of history. This is the one asset that cannot be
acquired retroactively.
"""

from __future__ import annotations

from app.domain.polling.derive import (
    ConnectorKey,
    StatusTransition,
    derive_transitions,
    key_of,
    replay,
)
from app.domain.polling.health import (
    PollerHealth,
    SourceHealth,
    longest_gap,
    poller_health,
    source_health,
)
from app.domain.polling.ingest import (
    finish_run,
    last_known_states,
    last_known_states_from_events,
    start_run,
    update_connector_state,
    write_raw_pages,
    write_transitions,
)
from app.domain.polling.normalise import (
    ChargerObservation,
    dedupe,
    from_ocpi_locations,
    from_scraped_stations,
    map_ocpi_status,
    map_scrape_status,
)
from app.domain.polling.sources import (
    SOURCES,
    SourceNotAuthorisedError,
    SourceSpec,
    pollable_sources,
    require_pollable,
)

__all__ = [
    "SOURCES",
    "ChargerObservation",
    "ConnectorKey",
    "PollerHealth",
    "SourceHealth",
    "SourceNotAuthorisedError",
    "SourceSpec",
    "StatusTransition",
    "dedupe",
    "derive_transitions",
    "finish_run",
    "from_ocpi_locations",
    "from_scraped_stations",
    "key_of",
    "last_known_states",
    "last_known_states_from_events",
    "longest_gap",
    "map_ocpi_status",
    "map_scrape_status",
    "pollable_sources",
    "poller_health",
    "replay",
    "require_pollable",
    "source_health",
    "start_run",
    "update_connector_state",
    "write_raw_pages",
    "write_transitions",
]
