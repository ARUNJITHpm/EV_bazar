"""PART 0.1 - the derivation from raw archive (1) to transition log (2).

This is now the most dangerous code in the poller. The old ingest wrote every
observation, so a bug lost nothing; the derived log is what occupancy queries
actually read, and a missed transition is a wrong number that looks right.

The presence rules get the most attention here, because they are the ones with
no natural feedback: nothing goes red when a delisted station keeps its
"available" status for eight months.
"""

from __future__ import annotations

import datetime as dt

import pytest

from app.domain.polling.derive import (
    apply,
    derive_transitions,
    key_of,
    replay,
)
from app.domain.polling.normalise import ChargerObservation
from app.models.charger_status import ConnectorStatus, Transition

SOURCE = "chargezone"
T0 = dt.datetime(2026, 8, 12, 10, 0, tzinfo=dt.UTC)
T1 = T0 + dt.timedelta(minutes=5)
T2 = T0 + dt.timedelta(minutes=10)


def obs(
    connector: str,
    status: ConnectorStatus,
    *,
    at: dt.datetime = T0,
    station: str = "ST1",
    source: str = SOURCE,
) -> ChargerObservation:
    return ChargerObservation(
        source=source,
        source_station_id=station,
        connector_id=connector,
        status=status,
        observed_at=at,
    )


# --- appearance ------------------------------------------------------------


def test_first_sighting_is_an_appearance() -> None:
    out = derive_transitions(
        {}, [obs("C1", ConnectorStatus.AVAILABLE)], source=SOURCE, observed_at=T0
    )
    assert [(t.connector_id, t.transition, t.status) for t in out] == [
        ("C1", Transition.APPEARED, ConnectorStatus.AVAILABLE)
    ]


def test_an_unchanged_connector_writes_nothing() -> None:
    """The whole point of the change log: a quiet cycle costs zero rows."""
    previous = {(SOURCE, "ST1", "C1"): ConnectorStatus.AVAILABLE}
    out = derive_transitions(
        previous, [obs("C1", ConnectorStatus.AVAILABLE, at=T1)], source=SOURCE, observed_at=T1
    )
    assert out == ()


def test_a_status_change_is_recorded_with_the_observation_timestamp() -> None:
    previous = {(SOURCE, "ST1", "C1"): ConnectorStatus.AVAILABLE}
    out = derive_transitions(
        previous, [obs("C1", ConnectorStatus.CHARGING, at=T1)], source=SOURCE, observed_at=T2
    )
    assert len(out) == 1
    assert out[0].transition is Transition.CHANGED
    # T1, not T2: the source told us when, and its answer beats our clock.
    assert out[0].observed_at == T1


# --- disappearance: the expensive one to get wrong --------------------------


def test_a_connector_that_stops_appearing_is_marked_unknown() -> None:
    """Otherwise a delisted station stays 'available' forever."""
    previous = {(SOURCE, "ST1", "C1"): ConnectorStatus.AVAILABLE}
    out = derive_transitions(previous, [], source=SOURCE, observed_at=T1)
    assert len(out) == 1
    assert out[0].transition is Transition.DISAPPEARED
    assert out[0].status is ConnectorStatus.UNKNOWN
    # Our clock: there is no source timestamp for something unmentioned.
    assert out[0].observed_at == T1


def test_disappearance_is_recorded_once_not_every_cycle() -> None:
    """A station delisted in March must not write a row every 5 minutes until December."""
    state: dict[tuple[str, str, str], ConnectorStatus] = {
        (SOURCE, "ST1", "C1"): ConnectorStatus.AVAILABLE
    }
    first = derive_transitions(state, [], source=SOURCE, observed_at=T1)
    state = apply(state, first)
    second = derive_transitions(state, [], source=SOURCE, observed_at=T2)

    assert len(first) == 1
    assert second == ()


def test_a_returning_connector_is_recorded_again() -> None:
    state: dict[tuple[str, str, str], ConnectorStatus] = {
        (SOURCE, "ST1", "C1"): ConnectorStatus.AVAILABLE
    }
    state = apply(state, derive_transitions(state, [], source=SOURCE, observed_at=T1))
    back = derive_transitions(
        state, [obs("C1", ConnectorStatus.CHARGING, at=T2)], source=SOURCE, observed_at=T2
    )
    assert [t.transition for t in back] == [Transition.CHANGED]
    assert back[0].status is ConnectorStatus.CHARGING


def test_one_source_going_quiet_says_nothing_about_another() -> None:
    """Sources are polled independently; absence from one is not absence from all."""
    previous = {
        (SOURCE, "ST1", "C1"): ConnectorStatus.AVAILABLE,
        ("statiq", "ST9", "C9"): ConnectorStatus.AVAILABLE,
    }
    out = derive_transitions(previous, [], source=SOURCE, observed_at=T1)
    assert [t.source for t in out] == [SOURCE]


def test_a_connector_already_unknown_does_not_re_disappear() -> None:
    previous = {(SOURCE, "ST1", "C1"): ConnectorStatus.UNKNOWN}
    assert derive_transitions(previous, [], source=SOURCE, observed_at=T1) == ()


# --- within-cycle hygiene ---------------------------------------------------


def test_a_repeated_connector_in_one_cycle_counts_once() -> None:
    """A paginated feed can repeat a location; counting it twice doubles it later."""
    out = derive_transitions(
        {},
        [obs("C1", ConnectorStatus.AVAILABLE), obs("C1", ConnectorStatus.CHARGING)],
        source=SOURCE,
        observed_at=T0,
    )
    assert len(out) == 1
    assert out[0].status is ConnectorStatus.CHARGING  # last one wins


def test_apply_does_not_mutate_the_input() -> None:
    previous = {(SOURCE, "ST1", "C1"): ConnectorStatus.AVAILABLE}
    apply(previous, derive_transitions(previous, [], source=SOURCE, observed_at=T1))
    assert previous == {(SOURCE, "ST1", "C1"): ConnectorStatus.AVAILABLE}


def test_key_of_matches_the_state_map_key() -> None:
    assert key_of(obs("C1", ConnectorStatus.AVAILABLE)) == (SOURCE, "ST1", "C1")


# --- replay: the reason the archive exists ----------------------------------


def test_replay_reconstructs_a_days_transitions_in_order() -> None:
    cycles = [
        (T0, (obs("C1", ConnectorStatus.AVAILABLE, at=T0),)),
        (T1, (obs("C1", ConnectorStatus.CHARGING, at=T1),)),
        (T2, (obs("C1", ConnectorStatus.CHARGING, at=T2),)),  # unchanged
    ]
    out = replay(cycles, source=SOURCE)
    assert [(t.transition, t.observed_at) for t in out] == [
        (Transition.APPEARED, T0),
        (Transition.CHANGED, T1),
    ]


def test_replay_is_deterministic_and_idempotent() -> None:
    """Re-deriving the same archive twice must give byte-identical output.

    If it does not, "a bug costs a recompute" is not true and the archive
    buys nothing.
    """
    cycles = [
        (
            T0,
            (
                obs("C1", ConnectorStatus.AVAILABLE, at=T0),
                obs("C2", ConnectorStatus.OFFLINE, at=T0),
            ),
        ),
        (T1, (obs("C1", ConnectorStatus.CHARGING, at=T1),)),  # C2 vanishes
        (
            T2,
            (
                obs("C1", ConnectorStatus.CHARGING, at=T2),
                obs("C2", ConnectorStatus.AVAILABLE, at=T2),
            ),
        ),
    ]
    assert replay(cycles, source=SOURCE) == replay(cycles, source=SOURCE)


def test_replay_reproduces_incremental_derivation_exactly() -> None:
    """The live poller and a cold replay must not disagree.

    The poller derives cycle by cycle against the database; replay derives the
    same cycles in memory. If these ever diverge, the archive cannot be used
    to check the live path, which is most of its value.
    """
    cycles = [
        (
            T0,
            (
                obs("C1", ConnectorStatus.AVAILABLE, at=T0),
                obs("C2", ConnectorStatus.AVAILABLE, at=T0),
            ),
        ),
        (T1, (obs("C1", ConnectorStatus.CHARGING, at=T1),)),
        (T2, (obs("C2", ConnectorStatus.OFFLINE, at=T2),)),
    ]

    incremental = []
    state: dict[tuple[str, str, str], ConnectorStatus] = {}
    for at, observations in cycles:
        step = derive_transitions(state, observations, source=SOURCE, observed_at=at)
        incremental.extend(step)
        state = apply(state, step)

    assert tuple(incremental) == replay(cycles, source=SOURCE)


def test_replay_picks_up_a_corrected_status_mapping() -> None:
    """The scenario the archive is FOR.

    August is replayed with November's understanding of a status word. The
    connector that was recorded as UNKNOWN comes back as OCCUPIED, and no new
    polling was required to learn that.
    """
    august_understanding = [(T0, (obs("C1", ConnectorStatus.UNKNOWN, at=T0),))]
    november_understanding = [(T0, (obs("C1", ConnectorStatus.OCCUPIED, at=T0),))]

    assert replay(august_understanding, source=SOURCE)[0].status is ConnectorStatus.UNKNOWN
    assert replay(november_understanding, source=SOURCE)[0].status is ConnectorStatus.OCCUPIED


@pytest.mark.parametrize(
    "status",
    [
        ConnectorStatus.AVAILABLE,
        ConnectorStatus.CHARGING,
        ConnectorStatus.OCCUPIED,
        ConnectorStatus.OFFLINE,
    ],
)
def test_every_real_status_can_disappear(status: ConnectorStatus) -> None:
    """Only UNKNOWN is exempt; a charging connector vanishing is still news."""
    previous = {(SOURCE, "ST1", "C1"): status}
    out = derive_transitions(previous, [], source=SOURCE, observed_at=T1)
    assert [t.transition for t in out] == [Transition.DISAPPEARED]
