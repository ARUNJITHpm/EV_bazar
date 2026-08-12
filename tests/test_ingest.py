"""PART 0.1 - the write path: archive (1), transitions (2), state cache.

Runs on SQLite. Partitioning and the append-only RULES are Postgres features
and are exercised by the migration against a real database, not here - but the
things that can be wrong in ordinary logic (page ordering, cache drift) are
exactly what this file pins down.

The cache test that matters is ``test_cache_agrees_with_the_events_it_caches``:
``connector_state`` is a derived convenience, and a derived convenience nobody
checks is just undeclared state.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.polling.derive import apply, derive_transitions
from app.domain.polling.ingest import (
    finish_run,
    last_known_states,
    last_known_states_from_events,
    start_run,
    update_connector_state,
    write_raw_pages,
    write_transitions,
)
from app.domain.polling.normalise import ChargerObservation
from app.models import Base
from app.models.charger_status import (
    ChargerStatusEvent,
    ConnectorState,
    ConnectorStatus,
    PollOutcome,
    PollRawPayload,
    PollRun,
)

SOURCE = "chargezone"
T0 = dt.datetime(2026, 8, 12, 10, 0, tzinfo=dt.UTC)
T1 = T0 + dt.timedelta(minutes=5)
T2 = T0 + dt.timedelta(minutes=10)

TABLES = [
    PollRawPayload.__table__,
    ChargerStatusEvent.__table__,
    ConnectorState.__table__,
    PollRun.__table__,
]


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=TABLES)
    with sessionmaker(bind=engine)() as s:
        yield s


def obs(connector: str, status: ConnectorStatus, *, at: dt.datetime = T0) -> ChargerObservation:
    return ChargerObservation(
        source=SOURCE,
        source_station_id="ST1",
        connector_id=connector,
        status=status,
        observed_at=at,
    )


# --- (1) the archive --------------------------------------------------------


def test_pages_keep_their_arrival_order(session: Session) -> None:
    """Replay dedupes last-one-wins, so page order carries meaning."""
    run_id = uuid.uuid4()
    written = write_raw_pages(
        session,
        [{"page": "first"}, {"page": "second"}, {"page": "third"}],
        poll_run_id=run_id,
        source=SOURCE,
        observed_at=T0,
    )
    assert written == 3

    rows = (
        session.execute(
            select(PollRawPayload.page_no, PollRawPayload.raw_payload).order_by(
                PollRawPayload.page_no
            )
        )
        .tuples()
        .all()
    )
    assert [(n, p["page"]) for n, p in rows] == [(0, "first"), (1, "second"), (2, "third")]


def test_a_bare_list_payload_is_archived_intact(session: Session) -> None:
    """Some CPO apps return the station list at the top level. Keep it as-is."""
    write_raw_pages(
        session, [[{"id": "ST1"}]], poll_run_id=uuid.uuid4(), source=SOURCE, observed_at=T0
    )
    stored = session.execute(select(PollRawPayload.raw_payload)).scalar_one()
    assert stored == [{"id": "ST1"}]


def test_archiving_nothing_writes_nothing(session: Session) -> None:
    assert (
        write_raw_pages(session, [], poll_run_id=uuid.uuid4(), source=SOURCE, observed_at=T0) == 0
    )


# --- (2) the transition log -------------------------------------------------


def test_transitions_record_why_they_exist(session: Session) -> None:
    run_id = uuid.uuid4()
    transitions = derive_transitions(
        {}, [obs("C1", ConnectorStatus.AVAILABLE)], source=SOURCE, observed_at=T0
    )
    assert write_transitions(session, transitions, poll_run_id=run_id) == 1

    row = session.execute(select(ChargerStatusEvent)).scalar_one()
    assert (row.status, row.transition) == ("available", "appeared")
    assert row.poll_run_id == run_id


def test_a_quiet_cycle_writes_no_rows(session: Session) -> None:
    assert write_transitions(session, [], poll_run_id=uuid.uuid4()) == 0
    assert session.execute(select(ChargerStatusEvent)).all() == []


# --- the cache --------------------------------------------------------------


def test_cache_round_trips_the_last_known_status(session: Session) -> None:
    transitions = derive_transitions(
        {}, [obs("C1", ConnectorStatus.AVAILABLE)], source=SOURCE, observed_at=T0
    )
    update_connector_state(session, transitions, now=T0)

    assert last_known_states(session, source=SOURCE) == {
        (SOURCE, "ST1", "C1"): ConnectorStatus.AVAILABLE
    }


def test_cache_is_scoped_per_source(session: Session) -> None:
    """A read for one source must not inherit another's connectors."""
    update_connector_state(
        session,
        derive_transitions(
            {}, [obs("C1", ConnectorStatus.AVAILABLE)], source=SOURCE, observed_at=T0
        ),
        now=T0,
    )
    assert last_known_states(session, source="statiq") == {}


def test_cache_updates_in_place_rather_than_accumulating(session: Session) -> None:
    state = {}
    for at, status in ((T0, ConnectorStatus.AVAILABLE), (T1, ConnectorStatus.CHARGING)):
        transitions = derive_transitions(
            state, [obs("C1", status, at=at)], source=SOURCE, observed_at=at
        )
        update_connector_state(session, transitions, now=at)
        state = apply(state, transitions)

    rows = session.execute(select(ConnectorState)).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "charging"
    assert rows[0].last_status_at.replace(tzinfo=dt.UTC) == T1


def test_cache_agrees_with_the_events_it_caches(session: Session) -> None:
    """The cache is rebuildable, and this proves the rebuild agrees.

    Runs a three-cycle history - appear, change, disappear - through both the
    cache and the transition log, then derives the state map from the log and
    demands the two match. If they ever drift, ``connector_state`` has stopped
    being a cache and become a second source of truth.
    """
    run_id = uuid.uuid4()
    cycles = [
        (
            T0,
            [
                obs("C1", ConnectorStatus.AVAILABLE, at=T0),
                obs("C2", ConnectorStatus.OFFLINE, at=T0),
            ],
        ),
        (
            T1,
            [obs("C1", ConnectorStatus.CHARGING, at=T1), obs("C2", ConnectorStatus.OFFLINE, at=T1)],
        ),
        (T2, [obs("C1", ConnectorStatus.CHARGING, at=T2)]),  # C2 vanishes
    ]

    state: dict[tuple[str, str, str], ConnectorStatus] = {}
    for at, observations in cycles:
        transitions = derive_transitions(state, observations, source=SOURCE, observed_at=at)
        write_transitions(session, transitions, poll_run_id=run_id)
        update_connector_state(session, transitions, now=at)
        state = apply(state, transitions)
    session.flush()

    from_cache = last_known_states(session, source=SOURCE)
    from_events = last_known_states_from_events(session, source=SOURCE)

    assert from_cache == from_events == state
    assert from_cache[(SOURCE, "ST1", "C2")] is ConnectorStatus.UNKNOWN


def test_updating_nothing_is_a_no_op(session: Session) -> None:
    assert update_connector_state(session, [], now=T0) == 0


# --- the liveness ledger ----------------------------------------------------


def test_a_run_records_capture_and_derivation_separately(session: Session) -> None:
    """Zero transitions on a healthy cycle is normal; zero pages is not."""
    run = start_run(session, source=SOURCE, now=T0)
    finish_run(
        session,
        run,
        outcome=PollOutcome.OK,
        events_written=0,
        raw_pages_written=3,
        connectors_seen=140,
        stations_seen=42,
        now=T0 + dt.timedelta(seconds=2),
    )
    stored = session.execute(select(PollRun)).scalar_one()
    assert (stored.events_written, stored.raw_pages_written) == (0, 3)
    assert (stored.connectors_seen, stored.stations_seen) == (140, 42)
    assert stored.duration_ms == 2000


def test_a_run_starts_pessimistic(session: Session) -> None:
    """An unfinished run must not read as a success."""
    start_run(session, source=SOURCE, now=T0)
    assert session.execute(select(PollRun.outcome)).scalar_one() == PollOutcome.FAILED.value
