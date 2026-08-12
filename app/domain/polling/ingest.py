"""Write the archive, then the derivation. Append-only - PART 0.1.

Thin by design: the interesting logic lives in ``normalise.py`` and
``derive.py`` where it can be tested without a database. This module only
turns things into rows.

Three writes, in this order, and the order is the point:

    1. write_raw_pages()   the lossless capture. Committed on its own, before
                           anything interprets it.
    2. write_transitions() the derived log, from derive.py.
    3. finish_run()        the liveness ledger.

If step 2 has a bug, step 1 already happened and the day is recoverable. If
they were one transaction, a derivation bug would roll back the capture too -
which is the failure this whole design exists to prevent.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import Executable, Select, func, select
from sqlalchemy.orm import Session

from app.domain.polling.adapters import RawPage
from app.domain.polling.derive import ConnectorKey, StatusTransition
from app.models.charger_status import (
    ChargerStatusEvent,
    ConnectorState,
    ConnectorStatus,
    PollOutcome,
    PollRawPayload,
    PollRun,
)


def write_raw_pages(
    session: Session,
    pages: Iterable[RawPage],
    *,
    poll_run_id: uuid.UUID,
    source: str,
    observed_at: dt.datetime,
) -> int:
    """Archive this cycle's response bodies verbatim into table (1).

    Pages keep their arrival order in ``page_no``: replay must feed them back
    the way they came, because "last one wins" dedupe means order carries
    meaning.
    """
    rows = [
        PollRawPayload(
            poll_run_id=poll_run_id,
            source=source,
            observed_at=observed_at,
            page_no=index,
            raw_payload=page,
        )
        for index, page in enumerate(pages)
    ]
    if not rows:
        return 0
    session.add_all(rows)
    session.flush()
    return len(rows)


def write_transitions(
    session: Session,
    transitions: Iterable[StatusTransition],
    *,
    poll_run_id: uuid.UUID,
) -> int:
    """Append derived transitions to table (2). Returns rows written.

    A cycle where nothing changed writes zero rows. That is the normal case
    and is not a fault - liveness is proven by ``poll_runs``, not by this
    table having grown.
    """
    rows = [
        ChargerStatusEvent(
            source=t.source,
            source_station_id=t.source_station_id,
            connector_id=t.connector_id,
            status=t.status.value,
            transition=t.transition.value,
            observed_at=t.observed_at,
            poll_run_id=poll_run_id,
        )
        for t in transitions
    ]
    if not rows:
        return 0
    session.add_all(rows)
    session.flush()
    return len(rows)


# ---------------------------------------------------------------------------
# Last known state
#
# The derivation needs one thing from the database: what each connector was
# doing last time. Two ways to get it, and they must agree.
# ---------------------------------------------------------------------------


def last_known_states(session: Session, *, source: str) -> dict[ConnectorKey, ConnectorStatus]:
    """Fast path: read the ``connector_state`` cache.

    One row per connector (~100k nationwide) rather than a scan over a
    transition log that grows forever. This runs every five minutes, so it
    cannot be O(history).
    """
    rows = session.execute(
        select(
            ConnectorState.source,
            ConnectorState.source_station_id,
            ConnectorState.connector_id,
            ConnectorState.status,
        ).where(ConnectorState.source == source)
    ).all()
    return {(r[0], r[1], r[2]): ConnectorStatus(r[3]) for r in rows}


def last_known_states_from_events(
    session: Session, *, source: str
) -> dict[ConnectorKey, ConnectorStatus]:
    """Authoritative path: derive the same map from table (2) itself.

    Slow - it reads the whole transition history for the source - so it is not
    what the poller calls. It exists because ``connector_state`` is a *cache*,
    and a cache nobody can rebuild is just undeclared state. Use it to rebuild
    after a restore, and to assert the two agree in tests.
    """
    event = ChargerStatusEvent
    ranked = (
        select(
            event.source,
            event.source_station_id,
            event.connector_id,
            event.status,
            func.row_number()
            .over(
                partition_by=(event.source, event.source_station_id, event.connector_id),
                # id breaks ties: two transitions can share a timestamp when a
                # source stamps a whole page with one `last_updated`.
                order_by=(event.observed_at.desc(), event.id.desc()),
            )
            .label("rn"),
        )
        .where(event.source == source)
        .subquery()
    )
    stmt: Select[tuple[str, str, str, str]] = select(
        ranked.c.source,
        ranked.c.source_station_id,
        ranked.c.connector_id,
        ranked.c.status,
    ).where(ranked.c.rn == 1)

    return {(r[0], r[1], r[2]): ConnectorStatus(r[3]) for r in session.execute(stmt).all()}


def _upsert_state(session: Session, rows: list[dict[str, object]]) -> Executable:
    """Dialect-specific ON CONFLICT for ``connector_state``.

    Postgres and SQLite expose the same upsert API from different modules and
    with unrelated types, so the branch is kept here, small and typed loosely,
    rather than spread through the caller.
    """
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt: Any = pg_insert(ConnectorState)
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(ConnectorState)
    else:  # pragma: no cover - we ship on Postgres and test on SQLite
        raise RuntimeError(f"connector_state upsert not implemented for {dialect!r}")

    stmt = stmt.values(rows)
    upsert: Executable = stmt.on_conflict_do_update(
        index_elements=["source", "source_station_id", "connector_id"],
        set_={
            "status": stmt.excluded.status,
            "last_status_at": stmt.excluded.last_status_at,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    return upsert


def update_connector_state(
    session: Session,
    transitions: Iterable[StatusTransition],
    *,
    now: dt.datetime,
) -> int:
    """Advance the cache. Transitions only - never the whole feed.

    Writing a row per connector per cycle would be ~100k upserts every five
    minutes to restate what did not change, which is the volume this design
    exists to avoid. So the cache moves exactly when the log does, and a
    connector's absence from this cycle reaches it as a DISAPPEARED
    transition like any other change.
    """
    # Last write wins if a key somehow appears twice: an upsert with a
    # repeated conflict target errors on Postgres rather than picking one.
    values: dict[ConnectorKey, dict[str, object]] = {
        t.key: {
            "source": t.source,
            "source_station_id": t.source_station_id,
            "connector_id": t.connector_id,
            "status": t.status.value,
            "last_status_at": t.observed_at,
            "updated_at": now,
        }
        for t in transitions
    }
    if not values:
        return 0

    session.execute(_upsert_state(session, list(values.values())))
    session.flush()
    return len(values)


# ---------------------------------------------------------------------------
# The liveness ledger
# ---------------------------------------------------------------------------


def start_run(session: Session, *, source: str, now: dt.datetime) -> PollRun:
    """Open a poll run *before* any network call.

    Recorded up front so a cycle that dies mid-flight still leaves evidence
    that it was attempted. A crash that leaves no trace is indistinguishable
    from a poller that was never scheduled.
    """
    run = PollRun(
        id=uuid.uuid4(),
        source=source,
        started_at=now,
        outcome=PollOutcome.FAILED.value,  # optimistic completion overwrites this
        events_written=0,
        raw_pages_written=0,
        connectors_seen=0,
        stations_seen=0,
    )
    session.add(run)
    session.flush()
    return run


def finish_run(
    session: Session,
    run: PollRun,
    *,
    outcome: PollOutcome,
    events_written: int = 0,
    raw_pages_written: int = 0,
    connectors_seen: int = 0,
    stations_seen: int = 0,
    error: str | None = None,
    now: dt.datetime,
) -> None:
    """Close a poll run.

    ``poll_runs`` is a status ledger rather than an immutable event log, so
    this is the one place a row is updated - and only ever from its own
    in-flight state to its terminal one. The tables it describes stay strictly
    append-only.
    """
    run.finished_at = now
    run.outcome = outcome.value
    run.events_written = events_written
    run.raw_pages_written = raw_pages_written
    run.connectors_seen = connectors_seen
    run.stations_seen = stations_seen
    run.error = error
    # started_at can come back naive - after a commit that expired the object,
    # or from a backend without a timezone-aware type. Everything the poller
    # writes is UTC, so assume it rather than crash while closing a run: a run
    # left open reads as a crash, which is the one thing this ledger exists to
    # tell the truth about.
    started_at = run.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=dt.UTC)
    run.duration_ms = max(0, int((now - started_at).total_seconds() * 1000))
    session.flush()
