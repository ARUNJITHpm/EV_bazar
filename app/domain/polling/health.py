"""The dead-man's switch - PART 0.1.

    "Dead-man's-switch alert: if no rows in 30 min -> notify"

Silence is the failure mode, and silence is invisible unless something
watches for it. A poller that dies quietly looks exactly like a poller that
is running against a quiet night, right up until you notice three weeks are
missing and cannot get them back.

Reads ``poll_runs``, not the event table: counting rows across monthly
partitions to answer "are we alive?" gets slow precisely when you most need
the answer.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.charger_status import PollOutcome, PollRun


@dataclass(frozen=True)
class SourceHealth:
    source: str
    last_success_at: dt.datetime | None
    last_attempt_at: dt.datetime | None
    last_error: str | None

    #: Transitions appended by the last successful run. Since table (2) is a
    #: change log, a healthy poller writes ZERO here on most cycles. Never
    #: treat this as a liveness signal - that is what ``silent_for`` and
    #: ``connectors_last_run`` are for.
    events_last_run: int
    #: Connectors the source actually reported. This is the "is anything
    #: coming back" number, and zero on a successful run means the endpoint
    #: answered with an empty feed - which is a real problem wearing a 200.
    connectors_last_run: int
    #: Raw pages archived. Zero on a successful run means the capture failed,
    #: which is the only unrecoverable failure in the poller.
    raw_pages_last_run: int
    stations_last_run: int

    silent_for: dt.timedelta | None

    def is_stale(self, threshold: dt.timedelta) -> bool:
        return self.silent_for is None or self.silent_for > threshold


@dataclass(frozen=True)
class PollerHealth:
    checked_at: dt.datetime
    threshold_minutes: int
    sources: tuple[SourceHealth, ...]

    @property
    def alive(self) -> bool:
        """True only if at least one source produced a success in the window.

        Deliberately "any", not "all": a single working source still means
        data is arriving. A stalled *individual* source is reported per-source
        so it is visible without tripping the global alarm.
        """
        threshold = dt.timedelta(minutes=self.threshold_minutes)
        return any(not s.is_stale(threshold) for s in self.sources)

    @property
    def stale_sources(self) -> tuple[str, ...]:
        threshold = dt.timedelta(minutes=self.threshold_minutes)
        return tuple(s.source for s in self.sources if s.is_stale(threshold))

    @property
    def never_run(self) -> bool:
        return all(s.last_success_at is None for s in self.sources)


def source_health(session: Session, source: str, *, now: dt.datetime) -> SourceHealth:
    last_success = session.execute(
        select(PollRun)
        .where(PollRun.source == source, PollRun.outcome == PollOutcome.OK.value)
        .order_by(PollRun.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    last_attempt = session.execute(
        select(PollRun).where(PollRun.source == source).order_by(PollRun.started_at.desc()).limit(1)
    ).scalar_one_or_none()

    last_success_at = last_success.started_at if last_success else None
    if last_success_at is not None and last_success_at.tzinfo is None:
        last_success_at = last_success_at.replace(tzinfo=dt.UTC)

    return SourceHealth(
        source=source,
        last_success_at=last_success_at,
        last_attempt_at=last_attempt.started_at if last_attempt else None,
        last_error=last_attempt.error if last_attempt else None,
        events_last_run=last_success.events_written if last_success else 0,
        connectors_last_run=last_success.connectors_seen if last_success else 0,
        raw_pages_last_run=last_success.raw_pages_written if last_success else 0,
        stations_last_run=last_success.stations_seen if last_success else 0,
        silent_for=None if last_success_at is None else now - last_success_at,
    )


def poller_health(
    session: Session,
    sources: tuple[str, ...],
    *,
    now: dt.datetime,
    threshold_minutes: int,
) -> PollerHealth:
    return PollerHealth(
        checked_at=now,
        threshold_minutes=threshold_minutes,
        sources=tuple(source_health(session, s, now=now) for s in sources),
    )


def events_in_window(session: Session, *, since: dt.datetime, source: str | None = None) -> int:
    """Transitions recorded since a moment.

    NOT a liveness measure. Table (2) is a change log, so a perfectly healthy
    quiet night legitimately produces very few rows. Use ``longest_gap`` for
    the "zero gaps > 15 min" exit criterion.
    """
    from app.models.charger_status import ChargerStatusEvent

    stmt = (
        select(func.count())
        .select_from(ChargerStatusEvent)
        .where(ChargerStatusEvent.observed_at >= since)
    )
    if source:
        stmt = stmt.where(ChargerStatusEvent.source == source)
    return int(session.execute(stmt).scalar_one())


def longest_gap(
    session: Session, *, source: str, since: dt.datetime, until: dt.datetime
) -> dt.timedelta:
    """Longest stretch with no successful poll - the PLAN 0.1 exit criterion.

    Measured on ``poll_runs``, because that is what "we were watching" means.
    The window's own edges count: a poller that started late or died an hour
    ago has a gap, and only comparing successes to each other would hide both.
    """
    starts = [
        s.replace(tzinfo=dt.UTC) if s.tzinfo is None else s
        for s in session.execute(
            select(PollRun.started_at)
            .where(
                PollRun.source == source,
                PollRun.outcome == PollOutcome.OK.value,
                PollRun.started_at >= since,
                PollRun.started_at <= until,
            )
            .order_by(PollRun.started_at)
        )
        .scalars()
        .all()
    ]

    if not starts:
        return until - since

    gap = max(starts[0] - since, until - starts[-1])
    for earlier, later in zip(starts, starts[1:], strict=False):
        gap = max(gap, later - earlier)
    return gap
