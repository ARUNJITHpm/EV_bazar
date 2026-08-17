"""PART 0.1 entrypoint - the status poller. It schedules; it does not think.

    python -m workers.poller              # loop forever on the interval
    python -m workers.poller --once       # one sweep, then exit
    python -m workers.poller --dry-run    # fetch + print counts, NO database

``--dry-run`` needs no database at all: it fetches each configured source and
prints how many stations / connectors / statuses came back. Use it to validate
a freshly captured endpoint and its status mapping before standing up Postgres.

All real logic lives in ``app.domain.polling``; this module only wires a source
to its adapter, runs a cycle on the interval, and records that each cycle
happened. It runs at a higher reliability tier than the web app because a web
outage is recoverable and a polling gap never is.

Each cycle captures first and interprets second (PLAN 0.1): the raw response
pages are archived and committed before the transition log is derived from
them, so a mistake in the derivation is a recompute rather than a hole.

Sources wired: every scraped CPO app in the registry (ChargeZone, Statiq,
Kazam, chargeMOD, Tata Power EZ, Ather Grid, Jio-bp). A source is polled only
when it is BOTH authorised in ``sources.py`` AND given an endpoint in settings -
config alone never grants permission.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import datetime as dt
import logging
import time

import httpx
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.domain.polling.adapters import Adapter, ScrapeAdapter, TataEzChargeAdapter
from app.domain.polling.derive import derive_transitions
from app.domain.polling.ingest import (
    finish_run,
    last_known_states,
    start_run,
    update_connector_state,
    write_raw_pages,
    write_transitions,
)
from app.domain.polling.sources import BY_NAME, SourceNotAuthorisedError, SourceSpec
from app.models.charger_status import PollOutcome

log = logging.getLogger("poller")

#: How long a single source's HTTP fetch may take before we abandon it and let
#: the next cycle try. A hung source must never eat the whole interval.
FETCH_TIMEOUT_SECONDS = 30.0


def resolve_scrape_spec(name: str, settings: Settings) -> SourceSpec:
    """Merge a scraped source's registry entry with the deployment's config.

    The registry holds the *governance* facts (terms, authorisation); config
    holds the *operational* ones (endpoint, rate limit). ``enabled`` follows
    whether an endpoint is actually configured, so a blank base URL leaves the
    source unpollable and ``require_pollable`` refuses it rather than polling
    the empty string. Authorisation still comes only from the registry - a
    configured-but-unvetted source is refused with "authorised=False".
    """
    cfg = settings.scrape_sources[name]
    return dataclasses.replace(
        BY_NAME[name],
        base_url=cfg.base_url,
        rate_limit_per_minute=cfg.rate_limit_per_minute,
        enabled=cfg.configured,
    )


def build_targets(settings: Settings) -> list[tuple[SourceSpec, Adapter]]:
    """The (source, adapter) pairs this deployment is configured to poll."""
    targets: list[tuple[SourceSpec, Adapter]] = []

    for name in settings.scrape_sources:
        spec = resolve_scrape_spec(name, settings)
        reason = spec.blocking_reason()
        if reason:
            # Only nag about sources someone has actually tried to configure -
            # a blank, unauthorised source is the resting state, not news.
            if settings.scrape_sources[name].configured or spec.authorised:
                log.warning("%s not polled: %s", name, reason)
            continue

        cfg = settings.scrape_sources[name]
        adapter: Adapter
        if name == "tata_power_ez":
            # Tata's map endpoint is a POST with a service/transid query, not the
            # generic GET; fall back to its real path when the config still holds
            # the generic default.
            tata_path = (
                cfg.stations_path
                if cfg.stations_path != "/stations"
                else "/HobsIntegration/syncRequestHandler"
            )
            adapter = TataEzChargeAdapter(
                spec, base_url=cfg.base_url, api_key=cfg.api_key, path=tata_path
            )
        else:
            adapter = ScrapeAdapter(
                spec, base_url=cfg.base_url, api_key=cfg.api_key, path=cfg.stations_path
            )
        targets.append((spec, adapter))

    return targets


def run_cycle(
    session: Session,
    spec: SourceSpec,
    adapter: Adapter,
    client: httpx.Client,
    *,
    now: dt.datetime,
) -> PollOutcome:
    """Poll one source once. Always leaves a ``poll_runs`` row behind.

    Three commits, deliberately:

      1. the run row, *before* the network call - a crash mid-fetch still
         leaves evidence the cycle was attempted, and a silent crash is
         otherwise indistinguishable from a poller that was never scheduled;
      2. the raw pages, *before* anything interprets them - the capture is
         irreplaceable and must not be rolled back by a bug in the
         derivation, which is entirely reproducible;
      3. the derived transitions and the closing of the run.

    A fetch that raises stops here with nothing derived. That is the correct
    behaviour and not merely defensive: the derivation reads absence as
    disappearance, so treating a failed fetch as "an empty feed" would append
    a fleet-wide vanishing to an append-only table.
    """
    run = start_run(session, source=spec.name, now=now)
    session.commit()

    # --- capture (irreplaceable) -------------------------------------------
    try:
        pages = adapter.fetch_raw(client)
        archived = write_raw_pages(
            session, pages, poll_run_id=run.id, source=spec.name, observed_at=now
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001 - one source failing must not stop the loop
        session.rollback()
        finish_run(
            session,
            run,
            outcome=PollOutcome.FAILED,
            error=f"fetch: {exc.__class__.__name__}: {exc}",
            now=dt.datetime.now(dt.UTC),
        )
        session.commit()
        log.error("%s fetch failed: %s", spec.name, exc)
        return PollOutcome.FAILED

    # --- derive (reproducible; a bug here costs a recompute, not data) -----
    try:
        observations = adapter.normalise(pages, observed_at=now)
        previous = last_known_states(session, source=spec.name)
        transitions = derive_transitions(previous, observations, source=spec.name, observed_at=now)

        written = write_transitions(session, transitions, poll_run_id=run.id)
        update_connector_state(session, transitions, now=now)
        finish_run(
            session,
            run,
            outcome=PollOutcome.OK,
            events_written=written,
            raw_pages_written=archived,
            connectors_seen=len(observations),
            stations_seen=len({o.source_station_id for o in observations}),
            now=dt.datetime.now(dt.UTC),
        )
        session.commit()
        log.info(
            "%s: %d pages archived, %d connectors seen, %d transitions",
            spec.name,
            archived,
            len(observations),
            written,
        )
        return PollOutcome.OK
    except Exception as exc:  # noqa: BLE001 - the archive is already safe
        session.rollback()
        # PARTIAL, not FAILED: the capture succeeded, so this cycle is not a
        # hole in the record - it is a replay away from being complete.
        finish_run(
            session,
            run,
            outcome=PollOutcome.PARTIAL,
            raw_pages_written=archived,
            error=f"derive: {exc.__class__.__name__}: {exc}",
            now=dt.datetime.now(dt.UTC),
        )
        session.commit()
        log.error("%s derivation failed (raw archived, replayable): %s", spec.name, exc)
        return PollOutcome.PARTIAL


def poll_once(settings: Settings) -> None:
    """One full sweep across every configured source, writing to the database."""
    targets = build_targets(settings)
    if not targets:
        log.warning("no pollable sources configured; nothing to do this cycle")
        return

    now = dt.datetime.now(dt.UTC)
    with httpx.Client(timeout=FETCH_TIMEOUT_SECONDS) as client:
        for spec, adapter in targets:
            with SessionLocal() as session:
                try:
                    run_cycle(session, spec, adapter, client, now=now)
                except SourceNotAuthorisedError as exc:
                    log.error("refusing to poll %s: %s", spec.name, exc)


def dry_run(settings: Settings) -> None:
    """Fetch each configured source and print a summary. No database touched.

    The fastest way to check a freshly captured endpoint + status mapping: run
    this, eyeball the per-status counts, and correct ``from_scraped_stations``
    / ``SCRAPE_STATUS_MAP`` until the numbers look like reality.
    """
    targets = build_targets(settings)
    if not targets:
        log.warning("no pollable sources configured; nothing to dry-run")
        return

    now = dt.datetime.now(dt.UTC)
    with httpx.Client(timeout=FETCH_TIMEOUT_SECONDS) as client:
        for spec, adapter in targets:
            try:
                obs = adapter.fetch(client, observed_at=now)
            except Exception as exc:  # noqa: BLE001 - report and move on
                log.error("%s failed: %s", spec.name, exc)
                continue
            stations = len({o.source_station_id for o in obs})
            by_status = collections.Counter(o.status.value for o in obs)
            counts = ", ".join(f"{k}={v}" for k, v in sorted(by_status.items()))
            log.info(
                "%s: %d connectors across %d stations [%s]",
                spec.name,
                len(obs),
                stations,
                counts or "no rows",
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="EV charger status poller (PLAN 0.1)")
    parser.add_argument("--once", action="store_true", help="one sweep, then exit")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch and print counts without a database (implies --once)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()

    if args.dry_run:
        dry_run(settings)
        return

    if args.once:
        poll_once(settings)
        return

    interval = settings.poller_interval_seconds
    log.info("poller starting; interval=%ss", interval)
    while True:
        started = time.monotonic()
        try:
            poll_once(settings)
        except Exception:  # noqa: BLE001 - the loop must outlive any single sweep
            log.exception("poll sweep raised; continuing")
        # Hold the cadence: sleep the remainder of the interval, not a flat
        # interval on top of the work already done.
        elapsed = time.monotonic() - started
        time.sleep(max(0.0, interval - elapsed))


if __name__ == "__main__":
    main()
