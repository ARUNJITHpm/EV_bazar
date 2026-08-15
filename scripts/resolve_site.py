"""Address -> a ``sites`` row. All of PART 1, end to end.

    uv run python -m scripts.resolve_site "MG Road, Kochi 682035"
    uv run python -m scripts.resolve_site "MG Road, Kochi 682035" --write
    uv run python -m scripts.resolve_site --selftest

Without ``--write`` the transaction is rolled back, so this is safe to point at
production to see what *would* be recorded.

``--selftest`` is the round-trip 1.5's unit tests deliberately do not cover:
``sites`` carries a PostGIS geometry, so the table cannot exist on SQLite. It
checks the two things only a real database can answer - that the generated
``geom`` column matches the ``lat``/``lng`` beside it, and that asking twice
produces one row with two requests rather than two rows.

It needs the reference layers loaded (1.2). It does **not** need a live
Nominatim: with L2 down every address becomes an unlocated lead, which is
itself the behaviour PLAN 1.6 asks for and is worth seeing.
"""

from __future__ import annotations

import argparse
import sys

import httpx
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal
from app.domain.resolution.cascade import build_cascade
from app.domain.resolution.geocode import GeocodeOutcome, GeocodeStatus
from app.domain.resolution.geography import Confidence, resolve
from app.domain.resolution.normalise import normalise_address
from app.domain.resolution.sites import SiteFacts, combine, resolve_site, upsert_site
from app.models.site import Site

SELFTEST = (
    "MG Road, Kochi 682035",
    "Walayar, Palakkad",
    "opp Lulu Mall, Edappally, Kochi",
)


def show(site: Site, facts: SiteFacts) -> None:
    print(f"site_id      {site.site_id}")
    print(f"raw          {site.raw_input!r}")
    print(f"normalised   {site.normalised_input!r}")
    print(f"located      {site.located}     resolved {site.resolved}")
    if site.located:
        print(f"coords       {site.lat}, {site.lng}")
    print(f"district     {site.lgd_district_code or '—'}   state {site.lgd_state_code or '—'}")
    print(f"pincode      {site.pincode or '—'}")
    print(
        f"source       {site.geocode_source or '—'}   confidence {site.geocode_confidence or '—'}"
    )
    print(f"method       {site.district_method or '—'}   ambiguous {site.boundary_ambiguous}")
    print(f"urban_rural  {site.urban_rural or '— (1.2 built-up layer not loaded)'}")
    print(f"data_tier    {site.data_tier if site.data_tier is not None else '— (1.6 not built)'}")
    print(f"requests     {site.requests}")
    for reason in facts.reasons:
        print(f"  · {reason}")


def selftest() -> int:
    settings = get_settings()
    failures = 0

    with SessionLocal() as session, httpx.Client() as client:
        geocoders = build_cascade(session, settings)
        print(f"cascade: {' -> '.join(g.source for g in geocoders)}\n")

        for raw in SELFTEST:
            site, _ = resolve_site(session, raw, geocoders=geocoders, client=client)
            state = "resolved" if site.resolved else "located" if site.located else "lead only"
            print(f"  {raw:<38} {state:<10} district={site.lgd_district_code or '-'}")

        # A known coordinate, entered the way the manual queue enters one. This
        # exercises 1.4 -> 1.5 with the cascade bypassed, which matters because
        # with Nominatim down every address above is an unlocated lead and the
        # geom check below would otherwise pass by having nothing to check.
        known = combine(
            GeocodeOutcome(
                status=GeocodeStatus.HIT,
                normalised=normalise_address("MG Road, Kochi 682035"),
                lat=9.9312,
                lng=76.2673,
                source="manual",
                confidence=Confidence.HIGH,
            ),
            resolve(session, 9.9312, 76.2673, expected_pincode="682035"),
        )
        placed = upsert_site(
            session,
            raw_input="MG Road, Kochi 682035 (known point)",
            normalised_input="selftest|known-point",
            facts=known,
        )
        ok = placed.resolved
        failures += not ok
        print(
            f"\n  {'OK ' if ok else 'XX '} known point -> {placed.lgd_district_code} "
            f"({known.district_method}, {placed.geocode_confidence})"
        )

        # (1) the generated column cannot disagree with the coordinates
        bad = session.execute(
            text("""
                SELECT count(*) FROM sites
                WHERE lat IS NOT NULL
                  AND (geom IS NULL
                       OR abs(ST_X(geom) - lng) > 1e-9
                       OR abs(ST_Y(geom) - lat) > 1e-9)
            """)
        ).scalar_one()
        located = session.execute(
            text("SELECT count(*) FROM sites WHERE lat IS NOT NULL")
        ).scalar_one()
        # A check with nothing to check is not a passing check.
        ok = bad == 0 and located > 0
        failures += not ok
        print(
            f"  {'OK ' if ok else 'XX '} geom matches lat/lng on all {located} located site(s)"
            + ("" if located else "  <- NOTHING TO CHECK")
        )

        # (2) asking twice is one site asked about twice
        first, _ = resolve_site(session, SELFTEST[0], geocoders=geocoders, client=client)
        rows = session.execute(
            text("SELECT count(*) FROM sites WHERE normalised_input = :k"),
            {"k": first.normalised_input},
        ).scalar_one()
        ok = rows == 1 and first.requests >= 2
        failures += not ok
        print(f"  {'OK ' if ok else 'XX '} repeat request -> 1 row, requests={first.requests}")

        # (3) the geometry column really is read-only
        try:
            session.execute(text("UPDATE sites SET geom = ST_SetSRID(ST_MakePoint(0, 0), 4326)"))
            session.flush()
            print("  XX  geom is writable - it can drift from lat/lng")
            failures += 1
        except Exception as exc:  # noqa: BLE001 - the message is the evidence
            session.rollback()
            print(f"  OK  geom refuses direct writes: {type(exc).__name__}")

        session.rollback()
        print("\nrolled back - nothing written")

    print(f"failures: {failures}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Address -> sites row (PLAN 1.5)")
    parser.add_argument("address", nargs="?")
    parser.add_argument("--write", action="store_true", help="commit; otherwise roll back")
    parser.add_argument("--no-cache", action="store_true", help="skip L1, force the geocoders")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.address:
        parser.print_help()
        return 2

    settings = get_settings()
    with SessionLocal() as session, httpx.Client() as client:
        site, facts = resolve_site(
            session,
            args.address,
            geocoders=build_cascade(session, settings),
            client=client,
            use_cache=not args.no_cache,
        )
        show(site, facts)
        if args.write:
            session.commit()
        else:
            session.rollback()
            print("\n(dry run - rolled back; pass --write to keep it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
