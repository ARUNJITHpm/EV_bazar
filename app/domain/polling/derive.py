"""Raw archive -> transition log. Pure functions, no DB, no network.

PLAN 0.1, "raw archive + derived events": table (1) is captured losslessly at
poll time and table (2) is *derived* from it. This module is that derivation,
and it is deliberately a pure function of (previous state, this cycle's
observations) so that:

  * it can be exhaustively tested without a database, and
  * it can be re-run over the archive when we get it wrong - which is the
    entire reason the archive exists.

The rule that is easy to miss and expensive to omit is **presence**. A
connector that stops appearing in a feed has not stayed available; we have
stopped being told anything about it. Without a row marking that, a station
delisted in March is still credited as "available" in December, and every
occupancy average computed over it is wrong in the flattering direction.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.domain.polling.normalise import ChargerObservation
from app.models.charger_status import ConnectorStatus, Transition

#: (source, station, connector). The identity of one physical socket as one
#: source names it. Two sources naming the same socket differently is
#: deliberate - reconciling them happens at analysis time (PLAN 2.3).
ConnectorKey = tuple[str, str, str]


@dataclass(frozen=True)
class StatusTransition:
    """One row destined for ``charger_status_events``."""

    source: str
    source_station_id: str
    connector_id: str
    status: ConnectorStatus
    transition: Transition
    observed_at: dt.datetime

    @property
    def key(self) -> ConnectorKey:
        return (self.source, self.source_station_id, self.connector_id)


def key_of(obs: ChargerObservation) -> ConnectorKey:
    return (obs.source, obs.source_station_id, obs.connector_id)


def derive_transitions(
    previous: Mapping[ConnectorKey, ConnectorStatus],
    observations: Iterable[ChargerObservation],
    *,
    source: str,
    observed_at: dt.datetime,
) -> tuple[StatusTransition, ...]:
    """What changed this cycle, given what we last knew.

    ``previous`` is the last known status of every connector this source has
    ever shown us - not just last cycle's. A connector absent for a week and
    back today is a change from its last known status, not a fresh arrival.

    ``observations`` MUST come from a cycle that actually succeeded. Deriving
    disappearance from a failed or partial fetch would mark the entire fleet
    as vanished on one bad HTTP response, and those rows are append-only.
    That guard belongs to the caller, which is the only layer that knows
    whether the fetch worked; it is restated here because getting it wrong is
    unrecoverable.

    ``observed_at`` is the cycle's own clock and is used only for
    disappearances - there is no source timestamp for something the source
    declined to mention. Appearances and changes keep the observation's own
    timestamp, which for OCPI is the operator's ``last_updated``.
    """
    # Last one wins within a cycle: a paginated feed can repeat a location,
    # and counting it twice would double it in every later average.
    current: dict[ConnectorKey, ChargerObservation] = {}
    for obs in observations:
        current[key_of(obs)] = obs

    out: list[StatusTransition] = []

    for key, obs in current.items():
        was = previous.get(key)
        if was is None:
            out.append(
                StatusTransition(
                    source=obs.source,
                    source_station_id=obs.source_station_id,
                    connector_id=obs.connector_id,
                    status=obs.status,
                    transition=Transition.APPEARED,
                    observed_at=obs.observed_at,
                )
            )
        elif was != obs.status:
            out.append(
                StatusTransition(
                    source=obs.source,
                    source_station_id=obs.source_station_id,
                    connector_id=obs.connector_id,
                    status=obs.status,
                    transition=Transition.CHANGED,
                    observed_at=obs.observed_at,
                )
            )

    # Presence. Only this source's connectors - one source going quiet says
    # nothing about another's, and `previous` may span several.
    vanished = sorted(
        key
        for key, status in previous.items()
        if key[0] == source
        # Already unknown: we have nothing new to record. This is also what
        # stops a permanently delisted station writing one row per cycle
        # forever.
        and status is not ConnectorStatus.UNKNOWN
        and key not in current
    )
    for key in vanished:
        out.append(
            StatusTransition(
                source=key[0],
                source_station_id=key[1],
                connector_id=key[2],
                status=ConnectorStatus.UNKNOWN,
                transition=Transition.DISAPPEARED,
                observed_at=observed_at,
            )
        )

    return tuple(out)


def apply(
    previous: Mapping[ConnectorKey, ConnectorStatus],
    transitions: Iterable[StatusTransition],
) -> dict[ConnectorKey, ConnectorStatus]:
    """Advance the state map. Returns a new dict; does not mutate ``previous``."""
    state = dict(previous)
    for t in transitions:
        state[t.key] = t.status
    return state


def replay(
    cycles: Iterable[tuple[dt.datetime, tuple[ChargerObservation, ...]]],
    *,
    source: str,
    initial: Mapping[ConnectorKey, ConnectorStatus] | None = None,
) -> tuple[StatusTransition, ...]:
    """Re-derive a whole stretch of history from the archive.

    This is what makes table (1) worth its disk. Feed it every successful
    cycle's normalised observations in chronological order and it reproduces
    the transition log exactly - so a status mapping we fix in November can be
    applied to August, which is impossible if the raw was dropped at ingest.

    Only successful cycles belong here. A failed fetch is an absence of
    information, and feeding it in as an empty cycle would fabricate a
    fleet-wide disappearance.
    """
    state: dict[ConnectorKey, ConnectorStatus] = dict(initial or {})
    out: list[StatusTransition] = []

    for observed_at, observations in cycles:
        transitions = derive_transitions(
            state, observations, source=source, observed_at=observed_at
        )
        out.extend(transitions)
        state = apply(state, transitions)

    return tuple(out)
