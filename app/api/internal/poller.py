"""Poller health for the console - PART 0.1 / C.5.

Surfaces the dead-man's switch. This endpoint is also a reasonable target
for an external uptime monitor: it returns 503 when the poller is silent,
so a generic "is this URL healthy" checker becomes a second, independent
alarm that does not depend on our own logging working.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.domain.polling import poller_health, source_health
from app.domain.polling.sources import SOURCES

router = APIRouter()

#: Endpoints an external uptime monitor can reach without a session. Keep this
#: to liveness alone - a monitor needs a status code, not our source list.
public_router = APIRouter()


class AliveOut(BaseModel):
    alive: bool
    never_run: bool


@public_router.get("/poller/alive", response_model=AliveOut)
def poller_alive(session: Session = Depends(get_session)) -> JSONResponse:
    """Unauthenticated liveness for an external uptime monitor.

    Returns 503 when nothing is being recorded, so a generic "is this URL
    healthy" checker becomes a second alarm that does not depend on our own
    logging, our own alerting, or our own process being alive to send it.

    Deliberately says nothing else. Which networks we poll, and what they last
    told us, is console data and lives behind the guard.
    """
    settings = get_settings()
    names = tuple(s.name for s in SOURCES)
    health = poller_health(
        session,
        names,
        now=dt.datetime.now(dt.UTC),
        threshold_minutes=settings.poller_deadman_minutes,
    )
    # Nothing authorised to poll yet is not an outage - it is the resting
    # state of a project whose first source has not been cleared.
    any_pollable = any(s.pollable for s in SOURCES)
    payload = AliveOut(alive=health.alive, never_run=health.never_run)
    return JSONResponse(
        payload.model_dump(), status_code=200 if (health.alive or not any_pollable) else 503
    )


class SourceHealthOut(BaseModel):
    source: str
    pollable: bool
    blocking_reason: str | None
    last_success_at: dt.datetime | None
    last_error: str | None
    #: Transitions written by the last successful run. Table (2) is a change
    #: log, so zero here is normal and is NOT a health signal - the console
    #: must not render it as one.
    events_last_run: int
    #: Connectors the source reported. This is the "is anything coming back"
    #: number: zero on a successful run means an empty feed wearing a 200.
    connectors_last_run: int
    #: Pages archived into the lossless table. Zero on a successful run is the
    #: one genuinely unrecoverable failure.
    raw_pages_last_run: int
    silent_for_seconds: float | None
    stale: bool


class PollerHealthOut(BaseModel):
    alive: bool
    never_run: bool
    threshold_minutes: int
    checked_at: dt.datetime
    stale_sources: list[str]
    sources: list[SourceHealthOut]


@router.get("/poller/health", response_model=PollerHealthOut)
def poller_health_endpoint(session: Session = Depends(get_session)) -> JSONResponse:
    settings = get_settings()
    now = dt.datetime.now(dt.UTC)
    threshold = dt.timedelta(minutes=settings.poller_deadman_minutes)

    names = tuple(s.name for s in SOURCES)
    health = poller_health(
        session, names, now=now, threshold_minutes=settings.poller_deadman_minutes
    )
    by_name = {s.source: s for s in health.sources}

    sources: list[SourceHealthOut] = []
    for spec in SOURCES:
        state = by_name[spec.name]
        silent = state.silent_for
        sources.append(
            SourceHealthOut(
                source=spec.name,
                pollable=spec.pollable,
                blocking_reason=spec.blocking_reason(),
                last_success_at=state.last_success_at,
                last_error=state.last_error,
                events_last_run=state.events_last_run,
                connectors_last_run=state.connectors_last_run,
                raw_pages_last_run=state.raw_pages_last_run,
                silent_for_seconds=None if silent is None else silent.total_seconds(),
                # A source nobody has authorised is not "stale" - it was never
                # meant to be running, and flagging it would train us to
                # ignore the alarm that matters.
                stale=spec.pollable and state.is_stale(threshold),
            )
        )

    payload = PollerHealthOut(
        alive=health.alive,
        never_run=health.never_run,
        threshold_minutes=settings.poller_deadman_minutes,
        checked_at=now,
        stale_sources=[s.source for s in sources if s.stale],
        sources=sources,
    )

    # 503 when nothing is being recorded, so an external uptime monitor can
    # act as a second alarm independent of our own logging.
    any_pollable = any(s.pollable for s in sources)
    status_code = 200 if (health.alive or not any_pollable) else 503

    return JSONResponse(payload.model_dump(mode="json"), status_code=status_code)


class CpoSourceOut(BaseModel):
    """One scraped/roamed CPO source, for the console CPO panel (PLAN C.4)."""

    source: str
    kind: str  # "scrape" | "ocpi" | other adapter name
    #: Governance: has a human read the terms and authorised polling?
    authorised: bool
    configured: bool  # is an endpoint set in settings?
    pollable: bool
    blocking_reason: str | None
    terms_url: str | None
    terms_note: str | None
    rate_limit_per_minute: int | None
    #: Researched route to this network's availability without OCPI/app-capture
    #: (CPO_SOURCES.md, 2026-08-15). Which networks are public-web occupancy
    #: targets vs app-only - the answer to "can we just scrape all of them".
    public_route: str | None
    #: Observed from our own poll runs, not claimed by the operator.
    last_success_at: dt.datetime | None
    last_error: str | None
    stations_last_run: int
    connectors_last_run: int
    events_last_run: int


class CpoSourcesOut(BaseModel):
    checked_at: dt.datetime
    sources: list[CpoSourceOut]


@router.get("/sources", response_model=CpoSourcesOut)
def cpo_sources_endpoint(session: Session = Depends(get_session)) -> CpoSourcesOut:
    """The CPO/source registry with governance + measured status side by side.

    Feeds the console CPO panel: which networks we scrape, whether each is
    authorised and configured, and what our own poller last saw from it -
    uptime we measured, not uptime the operator claimed.
    """
    settings = get_settings()
    now = dt.datetime.now(dt.UTC)
    scrape_cfg = settings.scrape_sources

    out: list[CpoSourceOut] = []
    for spec in SOURCES:
        health = source_health(session, spec.name, now=now)
        cfg = scrape_cfg.get(spec.name)
        out.append(
            CpoSourceOut(
                source=spec.name,
                kind=spec.adapter,
                authorised=spec.authorised,
                configured=cfg.configured if cfg is not None else bool(spec.base_url),
                pollable=spec.pollable,
                blocking_reason=spec.blocking_reason(),
                terms_url=spec.terms_url,
                terms_note=spec.terms_note,
                rate_limit_per_minute=spec.rate_limit_per_minute,
                public_route=spec.public_route,
                last_success_at=health.last_success_at,
                last_error=health.last_error,
                stations_last_run=health.stations_last_run,
                connectors_last_run=health.connectors_last_run,
                events_last_run=health.events_last_run,
            )
        )

    return CpoSourcesOut(checked_at=now, sources=out)
