"""PART 0.1 - the cycle: capture first, derive second.

PLAN 0.1's storage split only pays off if the ordering actually holds in the
running code, so these drive ``run_cycle`` end to end against a mock endpoint
rather than testing the pieces in isolation.

``test_a_failed_fetch_never_fabricates_a_disappearance`` is the one to keep
green above all others: it guards the only bug in this design that would write
false history into an append-only table.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.polling.adapters import ScrapeAdapter
from app.domain.polling.sources import BY_NAME, SourceSpec
from app.models import Base
from app.models.charger_status import (
    ChargerStatusEvent,
    ConnectorState,
    PollOutcome,
    PollRawPayload,
    PollRun,
)
from workers.poller import run_cycle

NOW = dt.datetime(2026, 8, 12, 10, 0, tzinfo=dt.UTC)


def _env() -> tuple[SourceSpec, Any]:
    """A vetted, configured scrape source and a fresh SQLite session factory."""
    spec = dataclasses.replace(
        BY_NAME["chargezone"],
        base_url="https://cz.test",
        terms_url="https://cz.test/terms",
        terms_note="Reviewed; polling permitted.",
        rate_limit_per_minute=30,
        authorised=True,
        enabled=True,
    )
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        engine,
        tables=[
            PollRawPayload.__table__,
            ChargerStatusEvent.__table__,
            ConnectorState.__table__,
            PollRun.__table__,
        ],
    )
    return spec, sessionmaker(bind=engine)


def _payload(status: str) -> dict[str, Any]:
    return {"stations": [{"id": "ST1", "connectors": [{"id": "1", "status": status}]}]}


def _client(handler: Any) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _adapter(spec: SourceSpec) -> ScrapeAdapter:
    return ScrapeAdapter(spec, base_url="https://cz.test", path="/stations")


def _events(make_session: Any) -> list[tuple[str, str]]:
    with make_session() as session:
        rows = (
            session.execute(
                select(ChargerStatusEvent).order_by(
                    ChargerStatusEvent.observed_at, ChargerStatusEvent.id
                )
            )
            .scalars()
            .all()
        )
    return [(r.status, r.transition) for r in rows]


def _count(make_session: Any, model: Any) -> int:
    with make_session() as session:
        return int(session.execute(select(func.count()).select_from(model)).scalar_one())


def test_a_cycle_archives_the_raw_page_and_derives_a_transition() -> None:
    spec, make_session = _env()
    client = _client(lambda r: httpx.Response(200, json=_payload("available")))

    with make_session() as session:
        assert run_cycle(session, spec, _adapter(spec), client, now=NOW) == PollOutcome.OK

    assert _count(make_session, PollRawPayload) == 1
    assert _events(make_session) == [("available", "appeared")]

    with make_session() as session:
        run = session.execute(select(PollRun)).scalar_one()
    assert (run.raw_pages_written, run.connectors_seen, run.events_written) == (1, 1, 1)


def test_a_second_identical_cycle_archives_again_but_derives_nothing() -> None:
    """The saving, demonstrated: capture every time, append only on change."""
    spec, make_session = _env()
    client = _client(lambda r: httpx.Response(200, json=_payload("available")))

    for offset in (0, 5, 10):
        with make_session() as session:
            run_cycle(session, spec, _adapter(spec), client, now=NOW + dt.timedelta(minutes=offset))

    assert _count(make_session, PollRawPayload) == 3  # nothing thrown away
    assert _count(make_session, ChargerStatusEvent) == 1  # only the first sighting


def test_a_status_change_appends_exactly_one_row() -> None:
    spec, make_session = _env()
    state = {"status": "available"}
    client = _client(lambda r: httpx.Response(200, json=_payload(state["status"])))

    with make_session() as session:
        run_cycle(session, spec, _adapter(spec), client, now=NOW)
    state["status"] = "charging"
    with make_session() as session:
        run_cycle(session, spec, _adapter(spec), client, now=NOW + dt.timedelta(minutes=5))

    assert _events(make_session) == [("available", "appeared"), ("charging", "changed")]


def test_a_vanishing_connector_is_recorded_as_unknown() -> None:
    """Without this row, a delisted station reads as 'available' indefinitely."""
    spec, make_session = _env()
    present = {"yes": True}
    client = _client(
        lambda r: httpx.Response(
            200, json=_payload("available") if present["yes"] else {"stations": []}
        )
    )

    with make_session() as session:
        run_cycle(session, spec, _adapter(spec), client, now=NOW)
    present["yes"] = False
    with make_session() as session:
        run_cycle(session, spec, _adapter(spec), client, now=NOW + dt.timedelta(minutes=5))

    assert _events(make_session) == [
        ("available", "appeared"),
        ("unknown", "disappeared"),
    ]


def test_a_failed_fetch_never_fabricates_a_disappearance() -> None:
    """The most dangerous failure mode in the whole design.

    One 500 from a CPO must not append "vanished" for their entire fleet to an
    append-only table. The cycle fails, nothing is derived, and the next
    successful poll carries on as though nothing happened.
    """
    spec, make_session = _env()
    healthy = {"yes": True}
    client = _client(
        lambda r: (
            httpx.Response(200, json=_payload("available"))
            if healthy["yes"]
            else httpx.Response(500, text="upstream on fire")
        )
    )

    with make_session() as session:
        run_cycle(session, spec, _adapter(spec), client, now=NOW)
    healthy["yes"] = False
    with make_session() as session:
        outcome = run_cycle(
            session, spec, _adapter(spec), client, now=NOW + dt.timedelta(minutes=5)
        )

    assert outcome == PollOutcome.FAILED
    assert _events(make_session) == [("available", "appeared")]  # no disappearance
    assert _count(make_session, PollRawPayload) == 1  # the failed fetch archived nothing


def test_an_empty_but_successful_feed_does_derive_a_disappearance() -> None:
    """The mirror of the test above, and the reason it cannot just catch-all.

    A 200 carrying zero stations is information: the operator says nothing is
    there. That must reach the log, or a network shutting down looks like a
    network permanently busy.
    """
    spec, make_session = _env()
    populated = {"yes": True}
    client = _client(
        lambda r: httpx.Response(
            200, json=_payload("charging") if populated["yes"] else {"stations": []}
        )
    )

    with make_session() as session:
        run_cycle(session, spec, _adapter(spec), client, now=NOW)
    populated["yes"] = False
    with make_session() as session:
        outcome = run_cycle(
            session, spec, _adapter(spec), client, now=NOW + dt.timedelta(minutes=5)
        )

    assert outcome == PollOutcome.OK
    assert _events(make_session)[-1] == ("unknown", "disappeared")


def test_a_derivation_failure_keeps_the_archive_and_reports_partial() -> None:
    """A bug in interpretation must cost a recompute, not a day of history."""
    spec, make_session = _env()
    client = _client(lambda r: httpx.Response(200, json=_payload("available")))

    class BrokenNormaliser(ScrapeAdapter):
        def normalise(self, pages: Any, *, observed_at: dt.datetime) -> Any:
            raise ValueError("status vocabulary blew up")

    adapter = BrokenNormaliser(spec, base_url="https://cz.test", path="/stations")

    with make_session() as session:
        outcome = run_cycle(session, spec, adapter, client, now=NOW)

    assert outcome == PollOutcome.PARTIAL
    assert _count(make_session, PollRawPayload) == 1  # capture survived
    assert _count(make_session, ChargerStatusEvent) == 0

    with make_session() as session:
        run = session.execute(select(PollRun)).scalar_one()
    assert run.raw_pages_written == 1
    assert "derive:" in (run.error or "")
