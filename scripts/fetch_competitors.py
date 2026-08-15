"""Fetch the competitor inventory from Open Charge Map - PART 2.3.

    uv run python -m scripts.fetch_competitors --state kerala --write
    uv run python -m scripts.fetch_competitors --state tamilnadu --dry-run
    uv run python -m scripts.fetch_competitors --near 9.9312 76.2673 --radius 5

Needs OPEN_CHARGE_MAP__API_KEY in .env (free key from openchargemap.org). Each
station is resolved to its district via PLAN 1.4 on the way in, so
"competitors per district" is an integer lookup afterwards, not a spatial join.

OCM gives existence + specs + an operational flag, NOT live occupancy - that is
the poller's job (PART 0.1), and it will attach to these rows.
"""

from __future__ import annotations

import argparse
import sys

import httpx

from app.config import get_settings
from app.db import SessionLocal
from app.domain.context import (
    CompetitorStationData,
    dedupe,
    fetch_ocm,
    store_stations,
    tile_bbox,
)

#: Generous bounding boxes (south, west, north, east) for the Tier-1 states.
#: Padded to catch border sites; the district resolver assigns each precisely.
STATE_BBOX: dict[str, tuple[float, float, float, float]] = {
    "kerala": (8.1, 74.8, 12.9, 77.5),
    "tamilnadu": (8.0, 76.2, 13.6, 80.4),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch competitor inventory (PLAN 2.3)")
    parser.add_argument("--state", choices=sorted(STATE_BBOX), help="fetch a whole state's bbox")
    parser.add_argument(
        "--near", nargs=2, type=float, metavar=("LAT", "LNG"), help="fetch near a point instead"
    )
    parser.add_argument("--radius", type=float, default=25.0, help="km, with --near")
    parser.add_argument(
        "--max", type=int, default=500, help="max results per query (OCM caps ~500)"
    )
    parser.add_argument(
        "--grid", type=int, default=3, help="tile a state into GRID x GRID cells to beat the cap"
    )
    parser.add_argument("--write", action="store_true", help="commit; otherwise roll back")
    parser.add_argument("--dry-run", action="store_true", help="fetch and show, store nothing")
    args = parser.parse_args(argv)

    if not args.state and not args.near:
        parser.error("give --state or --near")

    settings = get_settings()
    ocm = settings.open_charge_map
    if not ocm.enabled:
        print("OPEN_CHARGE_MAP__API_KEY is not set in .env - get a free key at openchargemap.org")
        return 2

    stations: list[CompetitorStationData] = []
    raw_total = 0
    with httpx.Client() as client:
        assert ocm.api_key is not None  # noqa: S101 - narrowed by ocm.enabled
        if args.state:
            tiles = tile_bbox(STATE_BBOX[args.state], rows=args.grid, cols=args.grid)
            print(f"fetching Open Charge Map for {args.state} across {len(tiles)} tiles...")
            for i, tile in enumerate(tiles, 1):
                res = fetch_ocm(
                    client, ocm.api_key, bbox=tile, max_results=args.max, base_url=ocm.base_url
                )
                raw_total += res.raw_count
                stations.extend(res.stations)
                cap = " (HIT CAP - increase --grid)" if res.raw_count >= args.max else ""
                print(f"  tile {i:>2}/{len(tiles)}: {res.raw_count} POIs{cap}")
        else:
            lat, lng = args.near
            print(f"fetching Open Charge Map within {args.radius} km of {lat},{lng}...")
            res = fetch_ocm(
                client,
                ocm.api_key,
                lat=lat,
                lng=lng,
                distance_km=args.radius,
                max_results=args.max,
                base_url=ocm.base_url,
            )
            raw_total += res.raw_count
            stations.extend(res.stations)

    stations = dedupe(stations)
    print(f"\n  {raw_total} raw POIs across tiles -> {len(stations)} unique stations")
    # A quick operator tally so the fetch is legible before anything is stored.
    ops: dict[str, int] = {}
    for s in stations:
        ops[s.operator or "(unattributed)"] = ops.get(s.operator or "(unattributed)", 0) + 1
    for op, n in sorted(ops.items(), key=lambda kv: -kv[1])[:12]:
        print(f"    {n:>4}  {op}")

    if args.dry_run or not stations:
        print("\ndry run - nothing written" if args.dry_run else "\nno stations to store")
        return 0

    with SessionLocal() as session:
        store = store_stations(session, stations, resolve_districts=True)
        if args.write:
            session.commit()
            verb = "committed"
        else:
            session.rollback()
            verb = "rolled back (pass --write to keep)"
    print(
        f"\n{store.inserted} inserted, {store.updated} updated, "
        f"{store.unplaced} could not be placed in a district - {verb}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
