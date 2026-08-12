"""PART 0.1 - the append-only occupancy record.

This is the one asset that cannot be acquired retroactively. Every day not
polling is a day permanently lost, and no amount of money buys back last
Tuesday's occupancy.

Capture and query are deliberately separate tables (PLAN 0.1, "raw archive +
derived events"). The capture is irreplaceable and must be lossless; the
queryable layer must be cheap. Compressing at ingest - the one irreproducible
moment - using diff logic we will tweak for months is the wrong place to be
clever.

  (1) poll_raw_payloads      LOSSLESS. Every page of every response, exactly
                             as received. Unindexed on the payload, highly
                             compressible, never read by a normal query. This
                             is the insurance: any bug downstream costs a
                             recompute, not data.

  (2) charger_status_events  DERIVED from (1): one row per appear / status
                             change / disappear. This is where occupancy
                             queries run. Carries no raw payload - (1) has it.

      poll_runs              one row per cycle per source. Liveness lives
                             here, so the dead-man's switch never counts rows
                             in a partitioned event table to ask "are we
                             alive?", and occupancy reconstruction gets its
                             denominator from cadence + liveness rather than
                             from 288 identical ticks per connector per day.

      connector_state        a cache of (2)'s latest row per connector, so the
                             derivation does not scan history every five
                             minutes. Rebuildable; not data of record.

Never UPDATE and never DELETE on (1) or (2) - database rules enforce it.
``poll_runs`` and ``connector_state`` are ledgers and are updated in place.
"""

from __future__ import annotations

import datetime as dt
import enum
import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Identity,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

JsonColumn = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")
BigIntPk = BigInteger().with_variant(Integer(), "sqlite")


class ConnectorStatus(enum.StrEnum):
    """Normalised status vocabulary (PLAN 0.1).

    Deliberately small. Sources disagree about vocabulary, so we map into
    these five and keep the source's own word in ``raw_payload``. If a
    mapping turns out wrong, the raw blob lets us re-derive history.
    """

    AVAILABLE = "available"
    CHARGING = "charging"
    OCCUPIED = "occupied"  # plugged/blocked/reserved - present but not drawing
    OFFLINE = "offline"  # inoperative, out of order, unreachable
    UNKNOWN = "unknown"


class PollOutcome(enum.StrEnum):
    OK = "ok"
    PARTIAL = "partial"  # some sources succeeded
    FAILED = "failed"
    SKIPPED = "skipped"  # rate limit or source disabled


class Transition(enum.StrEnum):
    """Why a derived event row exists (PLAN 0.1, table 2).

    DISAPPEARED is the one that is easy to forget and expensive to omit: a
    connector that stops appearing in the feed keeps its last known status
    forever unless something writes it down, so a delisted station reads as
    "available all year". It is recorded as UNKNOWN rather than OFFLINE - we
    know we stopped being told, not that the hardware went down.
    """

    APPEARED = "appeared"
    CHANGED = "changed"
    DISAPPEARED = "disappeared"


class PollRawPayload(Base):
    """(1) The lossless archive. One row per response page per cycle.

    Pages are stored as received rather than merged: where a page boundary
    fell is part of what we saw, and a merge is a transformation we would be
    unable to undo.

    Nothing queries this table in normal operation. It exists so that a
    mistake in the derivation - a status word mapped wrong, a presence rule
    that turns out to be too eager - costs an afternoon of recompute instead
    of a permanent hole in the record. Deliberately no index on the payload;
    it is written once, read rarely, and compresses hard because consecutive
    cycles are nearly identical.
    """

    __tablename__ = "poll_raw_payloads"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    observed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )

    poll_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    #: 0-based position in a paginated fetch. Replay must feed pages back in
    #: the order they arrived or a "last one wins" dedupe changes meaning.
    page_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: The response body, untouched. A top-level JSON array is legal here,
    #: which is why this is typed loosely - some CPO apps return a bare list.
    #: Nullable: a source may legitimately answer 200 with an empty body, and
    #: recording that we asked and got nothing is more useful than refusing
    #: to record the cycle at all.
    raw_payload: Mapped[Any | None] = mapped_column(JsonColumn)

    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # Replay reads by source over a window, in order.
        Index("ix_prp_source_time", "source", "observed_at", "page_no"),
        Index("ix_prp_run", "poll_run_id"),
        {"postgresql_partition_by": "RANGE (observed_at)"},
    )


class ChargerStatusEvent(Base):
    """(2) One *transition* of one connector: appeared, changed, or vanished.

    Derived from ``poll_raw_payloads``, never written straight off the wire.
    A connector holds its status from one row until the next, and whether the
    poller was actually watching during that stretch is answered by
    ``poll_runs`` - which is why 288 identical rows a day are not needed to
    make the occupancy denominator honest.

    Partitioned by ``observed_at`` monthly, so the primary key must include
    the partition key - Postgres requires it.
    """

    __tablename__ = "charger_status_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    observed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_station_id: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_id: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False)

    #: Why this row exists. Keeps a disappearance distinguishable from a
    #: source genuinely reporting UNKNOWN, which is a different fact.
    transition: Mapped[str] = mapped_column(String(16), nullable=False)

    #: Which poll cycle observed this transition. Joins to the raw archive and
    #: to liveness, so gap analysis is a join rather than a window function
    #: over hundreds of millions of rows.
    poll_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())

    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # The occupancy query: one connector's history over a window. Also the
        # index that answers "what was each connector's last known status".
        Index(
            "ix_cse_connector_time",
            "source",
            "source_station_id",
            "connector_id",
            "observed_at",
        ),
        Index("ix_cse_observed_at", "observed_at"),
        {"postgresql_partition_by": "RANGE (observed_at)"},
    )


class ConnectorState(Base):
    """A cache: what each connector was last known to be doing.

    NOT data of record. Every value here is recoverable from
    ``charger_status_events`` (see ``ingest.last_known_states_from_events``),
    which is in turn recoverable from ``poll_raw_payloads``. It exists purely
    so the five-minute derivation is O(connectors) instead of O(history) -
    without it, every cycle would scan a transition log that grows forever.

    Unpartitioned, ~one row per connector nationwide, and the only table in
    the poller besides ``poll_runs`` that is ever updated in place.
    """

    __tablename__ = "connector_state"

    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_station_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    connector_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False)
    #: When the status it currently holds began.
    #:
    #: There is deliberately no ``last_seen_at``. It would need refreshing for
    #: every connector on every cycle - ~100k upserts every five minutes - to
    #: record something already recorded: a connector that stops being
    #: reported gets a DISAPPEARED row within one cycle, so "not reported
    #: since Tuesday" is ``status = 'unknown'`` with ``last_status_at`` on
    #: Tuesday. Writing only transitions keeps this table's write volume
    #: proportional to what changed, like the log it caches.
    last_status_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_connector_state_source_status", "source", "status"),)


class PollRun(Base):
    """One poll cycle against one source.

    The dead-man's switch reads this table, not the event table.
    """

    __tablename__ = "poll_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Rows appended to (2) - transitions, not observations. Usually small,
    #: and a cycle writing zero is the normal case, not a fault.
    events_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Pages archived into (1). Zero here on an OK run means the capture
    #: failed silently, which is the serious failure - a cycle that derived
    #: nothing is recoverable, a cycle that archived nothing is not.
    raw_pages_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Connectors present in the feed this cycle. Distinct from
    #: ``events_written``: this is what we saw, that is what changed.
    connectors_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stations_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_poll_runs_source_started", "source", "started_at"),
        Index("ix_poll_runs_started", "started_at"),
    )
