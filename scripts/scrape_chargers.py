"""Scrape public chargers for Kerala, Tamil Nadu, Karnataka and Telangana, with CPO + listing apps.

    uv run python -m scripts.scrape_chargers                 # crawl pulse + goec + zeon
    uv run python -m scripts.scrape_chargers --skip-pulse    # reuse pulse_raw.json
    uv run python -m scripts.scrape_chargers --extra tata_power_raw.json statiq_raw.json

Writes to the repo root (working files, not the database):

    pulse_raw.json                     Pulse's rows exactly as served
    chargers_<region>.json             one record per physical charger, per region
    chargers_all.json                  the same, all regions together

Sources (robots-permissive, anonymous, no login):
    pulse   POST pulseenergy.io/api/charging-stations/nearby {lat,lng,radius}
            An aggregator: ``brand`` is the CPO and Pulse is one app listing it. It answers
            with the ~9-12 stations nearest the point whatever ``radius`` says, so the crawl
            is a coarse grid followed by a breadth-first walk from every station found.
    goec    GO EC's own map feed (existing fetcher)
    zeon    Zeon's own map feed (existing fetcher)
    --extra rows captured elsewhere (Tata Power / Statiq, via the browser) in the shape
            {"app","app_id","lat","lng","name","address","cpo","power","price"}

One physical charger is often listed in several apps (OCPI roaming), so a merged record
carries ``cpo`` (who runs it) and ``listed_in`` (every app + that app's own id). Two rows
merge only when they are within MERGE_M metres, come from different apps, AND agree on
operator or share a name token. Close-but-unconvinced pairs stay separate and are
cross-referenced in ``possible_duplicates`` for a human to settle - a wrong merge hides a
competitor.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
PULSE_URL = "https://pulseenergy.io/api/charging-stations/nearby"
UA = "EVBazar-research/1.0"

#: Generous boxes (south, west, north, east). Rectangles overlap at borders; a row
#: inside two boxes is assigned by ``state_hint`` first, then the tighter box.
REGIONS: dict[str, tuple[float, float, float, float]] = {
    "kerala": (8.1, 74.8, 12.95, 77.5),
    "tamilnadu": (8.0, 76.2, 13.6, 80.4),
    "karnataka": (11.5, 74.0, 18.5, 78.6),
    "telangana": (15.8, 77.2, 19.95, 81.8),
}
STATE_NAME = {
    "kerala": "Kerala",
    "tamilnadu": "Tamil Nadu",
    "karnataka": "Karnataka",
    "telangana": "Telangana",
}
SEED_STEP = 0.3
DEDUPE_CELL = 0.01  # ~1 km: a query this close to a done one returns nearly the same set
WORKERS = 6
MERGE_M = 60.0
NEAR_M = 150.0


def boxes_for(lat: float, lng: float) -> list[str]:
    return [k for k, b in REGIONS.items() if b[0] <= lat <= b[2] and b[1] <= lng <= b[3]]


def in_any_box(lat: float, lng: float) -> bool:
    return bool(boxes_for(lat, lng))


def metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    dlat = (a[0] - b[0]) * 111_320.0
    dlng = (a[1] - b[1]) * 111_320.0 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(dlat, dlng)


_HINTS = (
    ("kerala", r"kerala|\b(kl|kr)\s*\|"),
    ("tamilnadu", r"tamil\s*nadu|\btn\s*\|"),
    ("karnataka", r"karnataka|\bka\s*\|"),
    ("telangana", r"telangana|telengana|hyderabad|\b(ts|tg)\s*\|"),
)


def state_hint(name: str, address: str) -> str | None:
    """Best-effort from the text the app itself shows. NOT a boundary test."""
    text = f"{name} {address}".lower()
    for region, pat in _HINTS:
        if re.search(pat, text):
            return region
    return None


def assign_region(lat: float, lng: float, name: str, address: str) -> str | None:
    inside = boxes_for(lat, lng)
    if not inside:
        return None
    hint = state_hint(name, address)
    if hint in inside:
        return hint
    if len(inside) == 1:
        return inside[0]
    # overlap zone with no usable hint: the box whose centre is nearest
    return min(
        inside,
        key=lambda k: metres(
            (lat, lng), ((REGIONS[k][0] + REGIONS[k][2]) / 2, (REGIONS[k][1] + REGIONS[k][3]) / 2)
        ),
    )


# --- pulse -------------------------------------------------------------------


def _pulse_call(client: httpx.Client, lat: float, lng: float) -> list[dict[str, Any]]:
    for attempt in range(3):
        try:
            r = client.post(PULSE_URL, json={"lat": lat, "lng": lng, "radius": 0.15})
            r.raise_for_status()
            return r.json().get("data") or []
        except (httpx.HTTPError, ValueError):
            time.sleep(2 * (attempt + 1))
    return []


def crawl_pulse(client: httpx.Client) -> dict[int, dict[str, Any]]:
    stations: dict[int, dict[str, Any]] = {}
    south = min(b[0] for b in REGIONS.values())
    west = min(b[1] for b in REGIONS.values())
    north = max(b[2] for b in REGIONS.values())
    east = max(b[3] for b in REGIONS.values())
    wave: list[tuple[float, float]] = []
    lat = south
    while lat <= north:
        lng = west
        while lng <= east:
            if in_any_box(lat, lng):
                wave.append((round(lat, 4), round(lng, 4)))
            lng += SEED_STEP
        lat += SEED_STEP

    done_cells: set[tuple[int, int]] = set()
    calls = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        while wave:
            todo = []
            for lat, lng in wave:
                cell = (round(lat / DEDUPE_CELL), round(lng / DEDUPE_CELL))
                if cell in done_cells:
                    continue
                done_cells.add(cell)
                todo.append((lat, lng))
            wave = []
            for rows in pool.map(lambda p: _pulse_call(client, *p), todo):
                calls += 1
                for s in rows:
                    sid = s.get("charging_station_id")
                    if sid is None or int(sid) in stations:
                        continue
                    stations[int(sid)] = s
                    la, ln = float(s["lat"]), float(s["lng"])
                    if in_any_box(la, ln):
                        wave.append((la, ln))
            print(
                f"  pulse: {calls} calls, {len(stations)} stations, next wave {len(wave)}",
                flush=True,
            )
    return stations


# --- normalised rows ---------------------------------------------------------


def norm_operator(op: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (op or "").lower())


_STOP = {"ev", "evcs", "charging", "charger", "station", "charge", "the", "and", "kl", "tn", "ka"}


def name_tokens(name: str | None) -> set[str]:
    words = re.findall(r"[a-z0-9]{3,}", (name or "").lower())
    return {w for w in words if w not in _STOP}


def pulse_row(s: dict[str, Any]) -> dict[str, Any]:
    conns = {
        k: sum(int(v.get(x) or 0) for x in ("available", "in_use", "unavailable"))
        for k, v in (s.get("connectors_stat") or {}).items()
    }
    return {
        "app": "pulse",
        "app_id": str(s["charging_station_id"]),
        "lat": float(s["lat"]),
        "lng": float(s["lng"]),
        "name": (s.get("name") or "").strip(),
        "address": re.sub(r"\s+", " ", s.get("address") or "").strip(),
        "cpo": (s.get("brand") or "").strip() or None,
        "power": s.get("power"),
        "price": s.get("price"),
        "connectors": {k: n for k, n in conns.items() if n},
        "reports_live_status": True,
    }


def feed_row(app: str, d: Any) -> dict[str, Any]:
    return {
        "app": app,
        "app_id": d.source_id,
        "lat": d.lat,
        "lng": d.lng,
        "name": d.name or "",
        "address": ", ".join(x for x in (d.town, d.postcode) if x),
        "cpo": d.operator,
        "power": f"{d.max_power_kw:g} kW" if d.max_power_kw else None,
        "price": None,
        "connectors": {},
        "reports_live_status": False,
    }


def extra_row(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "app": r["app"],
        "app_id": str(r["app_id"]),
        "lat": float(r["lat"]),
        "lng": float(r["lng"]),
        "name": (r.get("name") or "").strip(),
        "address": (r.get("address") or "").strip(),
        "cpo": r.get("cpo"),
        "power": r.get("power"),
        "price": r.get("price"),
        "connectors": r.get("connectors") or {},
        "reports_live_status": bool(r.get("reports_live_status", False)),
    }


# --- merge -------------------------------------------------------------------


def _listing(row: dict[str, Any], charger: dict[str, Any]) -> dict[str, Any]:
    return {
        "app": row["app"],
        "app_id": row["app_id"],
        "name_in_app": row["name"],
        "operator_in_app": row["cpo"],
        "price": row["price"],
        "reports_live_status": row["reports_live_status"],
        "distance_m": round(metres((row["lat"], row["lng"]), (charger["lat"], charger["lng"])), 1),
    }


def merge(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chargers: list[dict[str, Any]] = []
    grid: dict[tuple[int, int], list[dict[str, Any]]] = {}

    def cell(lat: float, lng: float) -> tuple[int, int]:
        return (int(lat / 0.005), int(lng / 0.005))  # ~550 m

    for row in rows:
        target = None
        near: list[dict[str, Any]] = []
        ci, cj = cell(row["lat"], row["lng"])
        candidates = [
            c for di in (-1, 0, 1) for dj in (-1, 0, 1) for c in grid.get((ci + di, cj + dj), [])
        ]
        for c in candidates:
            d = metres((row["lat"], row["lng"]), (c["lat"], c["lng"]))
            if d > NEAR_M:
                continue
            same_app = any(x["app"] == row["app"] for x in c["listed_in"])
            same_cpo = bool(row["cpo"]) and norm_operator(row["cpo"]) == norm_operator(c["cpo"])
            share_name = bool(name_tokens(row["name"]) & name_tokens(c["name"]))
            # an app lists a physical charger once; two rows from one app are two chargers
            if d <= MERGE_M and not same_app and (same_cpo or share_name):
                target = c
                break
            near.append(c)
        if target is not None:
            target["listed_in"].append(_listing(row, target))
            if not target["cpo"] and row["cpo"]:
                target["cpo"] = row["cpo"]
            continue
        c = {
            "charger_id": f"C-{len(chargers) + 1:06d}",
            "region": assign_region(row["lat"], row["lng"], row["name"], row["address"]),
            "state_hint": state_hint(row["name"], row["address"]),
            "name": row["name"],
            "address": row["address"],
            "lat": row["lat"],
            "lng": row["lng"],
            "cpo": row["cpo"],
            "power": row["power"],
            "connectors": row["connectors"],
            "listed_in": [],
            "possible_duplicates": [],
        }
        c["listed_in"].append(_listing(row, c))
        for n in near:
            if row["app"] not in {x["app"] for x in n["listed_in"]}:
                c["possible_duplicates"].append(n["charger_id"])
                n["possible_duplicates"].append(c["charger_id"])
        chargers.append(c)
        grid.setdefault((ci, cj), []).append(c)
    return chargers


_STATE_TO_REGION = {v: k for k, v in STATE_NAME.items()}


def label_with_db(chargers: list[dict[str, Any]]) -> int:
    """Put each charger in its real state + district (read-only SELECTs on the reference layer).

    The rectangles in REGIONS overlap at borders (Coimbatore and Mysuru both fall inside
    Kerala's), so they only pre-filter. Point-in-polygon against ``districts`` decides; a
    point in no polygon (a sliver at the coast) takes the nearest district within ~5 km.
    Returns how many chargers could not be placed.
    """
    from sqlalchemy import text

    from app.db import SessionLocal

    sql = text(
        """
        SELECT p.i, d.state_name, d.name
        FROM unnest(CAST(:idx AS int[]), CAST(:lats AS float8[]), CAST(:lngs AS float8[]))
             AS p(i, lat, lng)
        LEFT JOIN LATERAL (
            SELECT state_name, name FROM districts
            WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(p.lng, p.lat), 4326), 0.05)
            ORDER BY ST_Contains(geom, ST_SetSRID(ST_MakePoint(p.lng, p.lat), 4326)) DESC,
                     geom <-> ST_SetSRID(ST_MakePoint(p.lng, p.lat), 4326)
            LIMIT 1
        ) d ON TRUE
        """
    )
    unplaced = 0
    with SessionLocal() as session:
        for start in range(0, len(chargers), 400):
            chunk = chargers[start : start + 400]
            rows = session.execute(
                sql,
                {
                    "idx": list(range(len(chunk))),
                    "lats": [c["lat"] for c in chunk],
                    "lngs": [c["lng"] for c in chunk],
                },
            ).all()
            for i, state, district in rows:
                c = chunk[i]
                c["state"] = state
                c["district"] = district
                if state is None:
                    unplaced += 1
                    continue
                c["region"] = _STATE_TO_REGION.get(state.title())
    return unplaced


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--skip-pulse", action="store_true", help="reuse pulse_raw.json")
    ap.add_argument(
        "--no-db", action="store_true", help="skip the read-only state/district labelling"
    )
    ap.add_argument("--extra", nargs="*", default=[], help="extra row files (tata, statiq)")
    args = ap.parse_args(argv)

    raw_path = ROOT / "pulse_raw.json"
    with httpx.Client(timeout=45, follow_redirects=True, headers={"User-Agent": UA}) as client:
        if args.skip_pulse and raw_path.exists():
            pulse = {
                int(s["charging_station_id"]): s for s in json.loads(raw_path.read_text("utf-8"))
            }
        else:
            print("crawling pulse ...")
            pulse = crawl_pulse(client)
            raw_path.write_text(
                json.dumps(list(pulse.values()), indent=1, ensure_ascii=False), encoding="utf-8"
            )

        from app.domain.context import fetch_goec, fetch_zeon

        feeds = {"goec": fetch_goec(client).stations, "zeon": fetch_zeon(client).stations}

    rows = [pulse_row(s) for s in pulse.values()]
    for app, stations in feeds.items():
        rows += [feed_row(app, d) for d in stations]
    for path in args.extra:
        rows += [extra_row(r) for r in json.loads(Path(path).read_text("utf-8"))]
    rows = [r for r in rows if in_any_box(r["lat"], r["lng"])]
    rows.sort(key=lambda r: (r["app"] != "pulse", r["lat"], r["lng"]))
    chargers = merge(rows)
    if not args.no_db:
        unplaced = label_with_db(chargers)
        print(f"labelled with state/district; {unplaced} outside every district")

    captured = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    sources = {
        "pulse": "POST pulseenergy.io/api/charging-stations/nearby (aggregator; brand = CPO)",
        "goec": "goecworld.com/api/stations/locations",
        "zeon": "zeoncharging.com/api/stations",
    }
    notes = [
        "state and district come from point-in-polygon on the repo's districts layer (read-only); "
        "region is that state. Rows in another state (Goa, Puducherry, Andhra...) are dropped.",
        "listed_in = every app that shows this physical charger; "
        "charger_id is ours, app_id is the app's.",
        "possible_duplicates = unmerged rows within 150 m from another app; "
        "review before treating as separate.",
        "Pulse connector counts are per-type totals; live availability is not stored here.",
    ]

    def bundle(subset: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "captured_at": captured,
            "sources": sources,
            "notes": notes,
            "counts": {
                "chargers": len(subset),
                "listed_in_more_than_one_app": sum(1 for c in subset if len(c["listed_in"]) > 1),
                "with_possible_duplicates": sum(1 for c in subset if c["possible_duplicates"]),
            },
            "chargers": subset,
        }

    def write(name: str, subset: list[dict[str, Any]]) -> None:
        (ROOT / name).write_text(
            json.dumps(bundle(subset), indent=1, ensure_ascii=False), encoding="utf-8"
        )

    chargers = [c for c in chargers if c["region"] in REGIONS]
    write("chargers_all.json", chargers)
    for region in REGIONS:
        subset = [c for c in chargers if c["region"] == region]
        write(f"chargers_{region}.json", subset)
        by_cpo: dict[str, int] = {}
        for c in subset:
            by_cpo[c["cpo"] or "(unknown)"] = by_cpo.get(c["cpo"] or "(unknown)", 0) + 1
        top = ", ".join(f"{k} {n}" for k, n in sorted(by_cpo.items(), key=lambda kv: -kv[1])[:6])
        print(f"{STATE_NAME[region]:<11} {len(subset):5d} chargers | {top}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
