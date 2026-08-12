"""Replay the raw archive and compare it to the derived log - PART 0.1.

    uv run python -m scripts.rederive --source chargezone --since 2026-08-01

This is the script that makes ``poll_raw_payloads`` worth its disk. If a
status word turns out to be mapped wrong, or the presence rule turns out to be
too eager, this re-derives what table (2) *should* contain from what we
actually received - and tells you how far the two have drifted.

**Dry-run only, on purpose.** Table (2) is append-only at the database level,
so "fixing" it in place is not a thing this script can or should do quietly.
Rebuilding it is a deliberate operation: derive into a fresh table, verify,
then swap. What belongs in a script is the part that is safe to run at 2am and
answers the question - which is this.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import sys

from sqlalchemy import func, select

from app.db import SessionLocal
from app.domain.polling.derive import replay
from app.domain.polling.normalise import (
    ChargerObservation,
    dedupe,
    from_ocpi_locations,
    from_scraped_stations,
)
from app.domain.polling.sources import BY_NAME
from app.models.charger_status import ChargerStatusEvent, PollRawPayload


def _normalise(
    kind: str, page: object, *, source: str, observed_at: dt.datetime
) -> tuple[ChargerObservation, ...]:
    """Route a page to the pure normaliser its source uses.

    Deliberately not via the adapter classes: an adapter needs an endpoint and
    a token, and replaying history should not require either. The normalisers
    are pure functions of the payload, which is the whole point of keeping
    them that way.
    """
    if kind == "ocpi" and isinstance(page, dict):
        return from_ocpi_locations(page, source=source, observed_at=observed_at)
    if kind == "scrape" and isinstance(page, dict | list):
        return from_scraped_stations(page, source=source, observed_at=observed_at)
    return ()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay the raw archive (PLAN 0.1)")
    parser.add_argument("--source", required=True, help="registry source name")
    parser.add_argument("--since", required=True, help="ISO date/datetime, inclusive")
    parser.add_argument("--until", default=None, help="ISO date/datetime, exclusive (default now)")
    args = parser.parse_args(argv)

    spec = BY_NAME.get(args.source)
    if spec is None:
        print(f"unknown source {args.source!r}; known: {', '.join(sorted(BY_NAME))}")
        return 2

    since = dt.datetime.fromisoformat(args.since)
    if since.tzinfo is None:
        since = since.replace(tzinfo=dt.UTC)
    until = dt.datetime.now(dt.UTC)
    if args.until:
        until = dt.datetime.fromisoformat(args.until)
        if until.tzinfo is None:
            until = until.replace(tzinfo=dt.UTC)

    with SessionLocal() as session:
        rows = (
            session.execute(
                select(
                    PollRawPayload.observed_at,
                    PollRawPayload.page_no,
                    PollRawPayload.raw_payload,
                )
                .where(
                    PollRawPayload.source == args.source,
                    PollRawPayload.observed_at >= since,
                    PollRawPayload.observed_at < until,
                )
                # page_no in the sort is not cosmetic: "last one wins" dedupe
                # means replaying pages out of order changes the answer.
                .order_by(PollRawPayload.observed_at, PollRawPayload.page_no)
            )
            .tuples()
            .all()
        )

        recorded = int(
            session.execute(
                select(func.count())
                .select_from(ChargerStatusEvent)
                .where(
                    ChargerStatusEvent.source == args.source,
                    ChargerStatusEvent.observed_at >= since,
                    ChargerStatusEvent.observed_at < until,
                )
            ).scalar_one()
        )

    if not rows:
        print(f"no archived pages for {args.source} in {since.isoformat()} .. {until.isoformat()}")
        return 1

    # Group pages back into the cycles they arrived in.
    cycles: dict[dt.datetime, list[object]] = collections.defaultdict(list)
    for observed_at, _page_no, payload in rows:
        at = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=dt.UTC)
        cycles[at].append(payload)

    replayed: list[tuple[dt.datetime, tuple[ChargerObservation, ...]]] = []
    for at in sorted(cycles):
        observations: list[ChargerObservation] = []
        for page in cycles[at]:
            observations.extend(_normalise(spec.adapter, page, source=args.source, observed_at=at))
        replayed.append((at, dedupe(tuple(observations))))

    transitions = replay(replayed, source=args.source)
    by_kind = collections.Counter(t.transition.value for t in transitions)

    print(f"source            {args.source} ({spec.adapter})")
    print(f"window            {since.isoformat()} .. {until.isoformat()}")
    print(f"archived pages    {len(rows)} across {len(cycles)} cycles")
    print(f"replayed          {len(transitions)} transitions")
    for kind, count in sorted(by_kind.items()):
        print(f"  {kind:<14}{count}")
    print(f"recorded in (2)   {recorded}")

    drift = len(transitions) - recorded
    if drift:
        print(
            f"\nDRIFT {drift:+d}. The archive and the derived log disagree. Either the "
            "normaliser changed since these rows were written (expected, and the reason "
            "this script exists), or the derivation has a bug. Rebuild deliberately - "
            "do not patch (2) in place."
        )
        return 1

    print("\nno drift: the derived log matches a fresh replay of the archive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
