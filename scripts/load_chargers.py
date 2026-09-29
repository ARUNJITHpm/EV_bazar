"""Load the scraped, merged chargers into ``competitor_stations``.

Reads ``chargers_all.json`` (scripts/scrape_chargers.py). One merged charger
becomes one row, keyed ``(source, source_id)`` by the first app that lists it,
in this order: GO EC, Zeon, Pulse, Tata Power.

**Insert-only.** A charger whose GO EC / Zeon id is already in the table is
skipped, not overwritten: those rows were parsed by the dedicated fetchers and
carry connector detail this file cannot improve on. Re-running is safe - it
inserts whatever is still missing.

**Not stored:** the other apps a charger is also listed in. ``competitor_stations``
has no column for it; the JSON keeps ``listed_in`` in full.

Default is a dry run (rolled back). Pass ``--write`` to keep it.

    uv run python -m scripts.load_chargers
    uv run python -m scripts.load_chargers --write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import text

from app.db import SessionLocal
from app.domain.context.competitors import CompetitorStationData, Connector
from app.domain.context.store import store_stations

PRIORITY = ("goec", "zeon", "pulse", "tata_power")
DC = {"CCS2", "CCS", "GBT", "CHAdeMO", "DC-001"}
NEAR_M = 60


def _power_range(p: str | None) -> tuple[float | None, float | None]:
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", p or "")]
    return (min(nums), max(nums)) if nums else (None, None)


def _connectors(c: dict) -> tuple[tuple[Connector, ...], float | None]:
    lo, hi = _power_range(c.get("power"))
    out: list[Connector] = []
    for typ, n in (c.get("connectors") or {}).items():
        kind = None if typ == "total" else typ
        if hi is None:
            kw = None
        elif typ in DC:
            kw = hi
        elif lo is not None and lo <= 7.4 <= hi:
            kw = 7.4
        else:
            kw = lo
        out.append(Connector(connector_type=kind, power_kw=kw, quantity=max(int(n), 1)))
    if not out and hi is not None:
        out.append(Connector(connector_type=None, power_kw=hi, quantity=1))
    return tuple(out), hi


def _fit(source_id: str) -> str:
    """``source_id`` is String(64). A longer id keeps its head plus a hash of
    the whole, so it stays unique and stable across runs."""
    if len(source_id) <= 64:
        return source_id
    return f"{source_id[:52]}~{hashlib.sha1(source_id.encode()).hexdigest()[:11]}"


def _key(c: dict) -> tuple[str, str]:
    apps = {x["app"]: x["app_id"] for x in c["listed_in"]}
    for app in PRIORITY:
        if app in apps:
            return app, _fit(str(apps[app]))
    first = c["listed_in"][0]
    return first["app"], _fit(str(first["app_id"]))


def _row(c: dict) -> CompetitorStationData:
    conns, hi = _connectors(c)
    source, source_id = _key(c)
    points = sum(x.quantity for x in conns) if (c.get("connectors") or {}) else None
    apps = "+".join(x["app"] for x in c["listed_in"])
    return CompetitorStationData(
        source=source,
        source_id=source_id,
        lat=c["lat"],
        lng=c["lng"],
        name=c["name"],
        operator=c.get("cpo"),
        number_of_points=points,
        max_power_kw=hi,
        connectors=conns,
        data_provider=f"scrape {apps}",
    )


def _lead(operator: str | None) -> str:
    """First four letters of the operator, for a loose same-company test:
    'ChargeMod (IN)' ~ 'ChargeMOD', 'Tata Power' ~ 'Tata Power'."""
    return re.sub(r"[^a-z0-9]", "", (operator or "").lower())[:4]


def _metres(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    dy = (a_lat - b_lat) * 111_195
    dx = (a_lng - b_lng) * 111_195 * math.cos(math.radians(a_lat))
    return math.hypot(dx, dy)


def _same_charger(
    r: CompetitorStationData, existing: list[tuple[float, float, str | None]]
) -> bool:
    """True if a stored row from elsewhere is within NEAR_M and the same company
    (or either side has no operator to compare)."""
    for lat, lng, op in existing:
        if abs(lat - r.lat) > 0.001 or abs(lng - r.lng) > 0.001:
            continue
        if _metres(lat, lng, r.lat, r.lng) > NEAR_M:
            continue
        if not op or not r.operator or _lead(op) == _lead(r.operator):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--file", default="chargers_all.json")
    ap.add_argument("--write", action="store_true", help="commit (default: roll back)")
    args = ap.parse_args(argv)

    chargers = json.loads(Path(args.file).read_text("utf-8"))["chargers"]
    rows = [_row(c) for c in chargers]
    dupes = [k for k, n in Counter((r.source, r.source_id) for r in rows).items() if n > 1]
    if dupes:
        print(f"refusing: {len(dupes)} keys repeat inside the file, e.g. {dupes[:3]}")
        return 1

    with SessionLocal() as session:
        have = {
            (r[0], r[1])
            for r in session.execute(text("SELECT source, source_id FROM competitor_stations"))
        }
        # A merged charger is skipped if ANY app it is listed in is already stored.
        stored = [
            (r[0], r[1], r[2])
            for r in session.execute(text("SELECT lat, lng, operator FROM competitor_stations"))
        ]
        new: list[CompetitorStationData] = []
        same_elsewhere = 0
        for c, r in zip(chargers, rows, strict=True):
            if any((x["app"], _fit(str(x["app_id"]))) in have for x in c["listed_in"]):
                continue
            if _same_charger(r, stored):
                same_elsewhere += 1
                continue
            new.append(r)
        print(f"{same_elsewhere} skipped: already stored under another source (<= {NEAR_M} m)")
        print(
            f"{len(rows)} chargers in file, {len(rows) - len(new)} already stored, "
            f"{len(new)} to insert"
        )

        result = store_stations(session, new, resolve_districts=True)

        # Rows this load added that sit within NEAR_M of a row from another
        # source: likely the same physical charger counted twice.
        near = session.execute(
            text(
                """
                SELECT count(*) FROM competitor_stations n
                WHERE n.data_provider LIKE 'scrape %%'
                  AND n.fetched_at >= now() - interval '10 minutes'
                  AND EXISTS (
                    SELECT 1 FROM competitor_stations o
                    WHERE o.id <> n.id AND o.source <> n.source
                      AND o.data_provider NOT LIKE 'scrape %%'
                      AND ST_DWithin(o.geom::geography, n.geom::geography, :m))
                """
            ),
            {"m": NEAR_M},
        ).scalar_one()

        print(
            f"{result.inserted} inserted, {result.updated} updated, "
            f"{result.unplaced} not placed in a district"
        )
        print(f"{near} of the new rows are within {NEAR_M} m of a row from another source")
        by = Counter((r.source, r.operator) for r in new)
        for (src, op), n in by.most_common(8):
            print(f"  {n:>4}  {src:<10} {op}")
        if args.write:
            session.commit()
            print("committed")
        else:
            session.rollback()
            print("rolled back (pass --write to keep)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
