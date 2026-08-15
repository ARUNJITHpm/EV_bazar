"""Geocode an address through the cascade - PART 1.3.

    uv run python -m scripts.geocode_address "MG Road, Kochi 682035"
    uv run python -m scripts.geocode_address "opp Lulu Mall, Edappally" --no-cache
    uv run python -m scripts.geocode_address "Trivandrum" --normalise-only
    uv run python -m scripts.geocode_address --selftest

``--normalise-only`` shows just the L0 output and needs **no network and no
database** - the fast way to check the normaliser against a real address before
Nominatim is even imported. ``--selftest`` runs known addresses against the live
self-hosted Nominatim (so it needs L2 up), the same shape as
``resolve_point --selftest``.
"""

from __future__ import annotations

import argparse
import sys

import httpx

from app.config import get_settings
from app.db import SessionLocal
from app.domain.resolution.cascade import build_cascade
from app.domain.resolution.geocode import GeocodeOutcome, geocode
from app.domain.resolution.normalise import normalise_address

#: Real addresses a human can check. Deliberately messy: abbreviations, a
#: proximity word, an old city name, a bare PIN.
SELFTEST: tuple[tuple[str, str | None], ...] = (
    ("MG Road, Kochi 682035", "Ernakulam"),
    ("opp Lulu Mall, Edappally, Kochi", "Ernakulam"),
    ("Trivandrum", "Thiruvananthapuram"),
    ("Bangalore MG Rd", "Bengaluru"),
    ("682001", "Ernakulam"),  # PIN only
)


def _show_normalise(raw: str) -> None:
    n = normalise_address(raw)
    print(f"raw        {raw!r}")
    print(f"  query    {n.query!r}")
    print(f"  pincode  {n.pincode}")
    print(f"  cache_key {n.cache_key!r}")


def _show(raw: str, outcome: GeocodeOutcome) -> None:
    print(f"raw          {raw!r}")
    print(f"  status     {outcome.status}")
    if outcome.resolved:
        print(f"  coords     {outcome.lat}, {outcome.lng}")
        print(f"  source     {outcome.source}")
        print(f"  confidence {outcome.confidence}")
        print(f"  matched    {outcome.display_name}")
    for reason in outcome.reasons:
        print(f"  · {reason}")


def selftest() -> int:
    settings = get_settings()
    misses = 0
    with SessionLocal() as session, httpx.Client() as client:
        geocoders = build_cascade(session, settings)
        print(f"cascade: {' -> '.join(g.source for g in geocoders)}\n")
        for raw, _expected in SELFTEST:
            outcome = geocode(session, raw, geocoders=geocoders, client=client, use_cache=False)
            flag = "OK " if outcome.resolved else "XX "
            misses += not outcome.resolved
            coords = f"{outcome.lat:.4f},{outcome.lng:.4f}" if outcome.resolved else "—"
            print(f"  {flag} {raw:<34} -> {coords:<20} {outcome.status} {outcome.confidence or ''}")
    print(f"\nunresolved: {misses}")
    return 1 if misses else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Geocode an address (PLAN 1.3)")
    parser.add_argument("address", nargs="?")
    parser.add_argument("--no-cache", action="store_true", help="skip L1, force the geocoder")
    parser.add_argument(
        "--normalise-only", action="store_true", help="just L0 - no network, no database"
    )
    parser.add_argument("--selftest", action="store_true", help="known addresses, live Nominatim")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.address:
        parser.print_help()
        return 2
    if args.normalise_only:
        _show_normalise(args.address)
        return 0

    settings = get_settings()
    with SessionLocal() as session, httpx.Client() as client:
        outcome = geocode(
            session,
            args.address,
            geocoders=build_cascade(session, settings),
            client=client,
            use_cache=not args.no_cache,
        )
        session.commit()
        _show(args.address, outcome)
    return 0


if __name__ == "__main__":
    sys.exit(main())
