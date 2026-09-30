"""Backfill the charging-network tables (migration 0015) from what we already hold.

    uv run python -m scripts.backfill_network            # dry run, rolled back
    uv run python -m scripts.backfill_network --write

Reads ``competitor_stations`` (the live inventory), ``chargers_all.json`` (the
merged scrape, which knows every app a charger is listed in) and the raw scrape
files ``pulse_raw.json`` / ``tata_power_raw.json``. Writes:

  cpos, cpo_aliases     the canonical operators and every name seen for them, from
                        ``domain/cpo/identity.py`` - the same decisions, now in rows
  stations              one per ``competitor_stations`` row (``legacy_competitor_station_id``)
  chargers, connectors  one inferred charger per physical connector (see below)
  station_listings      each app's own id for a station - INCLUDING the other apps a
                        merged charger is listed in, which ``load_chargers`` could not
                        store
  scraped_records       the raw Pulse and Tata Power records, verbatim

**Insert-only and re-runnable.** Nothing is updated or deleted, except that a
station's ``address`` is filled if it was empty. A second run inserts only what
is still missing.

**Inferred chargers.** The sources say "3 x Type 2 at 7.4 kW", never which plugs
share a box. Each physical connector becomes its own charger row with
``inferred = true`` and one connector: the choice that never claims two plugs
share power, so each is forecast on its own (the owner flow picks connectors one
by one). It over-counts chargers wherever a box really has two guns, which is
what the flag is for.

**Not backfilled:** goec / zeon raw pages (never saved, only their merged form),
so those have listings but no scraped record; OCM likewise. Live status keys are
untouched - joining them to ``connectors`` is a later step.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import uuid
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.domain.cpo.identity import (
    CANONICAL,
    OPERATOR_ALIASES,
    canonical_operator,
    normalise_operator,
)
from app.models import (
    Charger,
    CompetitorStation,
    Connector,
    Cpo,
    CpoAlias,
    DataSource,
    ScrapedRecord,
    Station,
    StationListing,
)
from scripts.load_chargers import NEAR_M, PRIORITY, _fit, _lead, _metres

T = TypeVar("T")

#: source key -> (raw file, the field holding the source's own id)
RAW_FILES = {
    "pulse": ("pulse_raw.json", "charging_station_id"),
    "tata_power": ("tata_power_raw.json", "app_id"),
}
CHUNK = 500
_DC = ("ccs", "chademo", "gbt", "gb/t", "gb-t", "dc")
_AC = ("type 2", "type2", "type 1", "type1", "15a", "16a", "ac-", "schuko", "iec", "cee", "type m")


@dataclass(frozen=True)
class ConnectorPlan:
    standard: str | None
    power_kw: float | None
    format: str | None


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:64]


def standard_of(raw: Any) -> str | None:
    """A connector type as stored, or None where the source did not say."""
    if raw is None:
        return None
    text = str(raw).strip()
    return None if text.lower() in ("", "null", "unknown", "none") else text[:48]


def current_type(standard: str | None) -> str | None:
    """AC or DC from the connector standard, None where it does not say."""
    if not standard:
        return None
    s = standard.lower()
    if any(k in s for k in _DC):
        return "DC"
    if any(k in s for k in _AC):
        return "AC"
    return None


def connector_format(standard: str | None) -> str | None:
    s = (standard or "").lower()
    if "tethered" in s:
        return "cable"
    if "socket" in s:
        return "socket"
    return None


def plan_connectors(
    connectors: list[dict[str, Any]] | None, points: int | None, max_kw: float | None
) -> list[ConnectorPlan]:
    """One plan per physical connector, from a station's stored breakdown."""
    out: list[ConnectorPlan] = []
    for c in connectors or []:
        std = standard_of(c.get("type"))
        kw = c.get("power_kw")
        power = float(kw) if isinstance(kw, int | float) and kw > 0 else None
        out.extend(
            [ConnectorPlan(std, power, connector_format(std))] * max(int(c.get("quantity") or 1), 1)
        )
    if not out and points and points > 0:
        power = max_kw if max_kw and max_kw > 0 else None
        out = [ConnectorPlan(None, power, None)] * points
    return out


def content_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _chunks(items: list[T], n: int = CHUNK) -> Iterable[list[T]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


def _cpos_and_aliases(
    session: Session, sources: dict[str, int], rows: list[Any], counts: Counter[str]
) -> dict[str, int]:
    """Canonical operators and every spelling we hold. Returns canonical name -> cpo id."""
    have = {c.slug: c.id for c in session.scalars(select(Cpo))}
    fresh = [Cpo(slug=slug(n), name=n) for n in CANONICAL if slug(n) not in have]
    session.add_all(fresh)
    session.flush()
    have.update({c.slug: c.id for c in fresh})
    counts["cpos_added"] += len(fresh)
    by_name = {n: have[slug(n)] for n in CANONICAL}

    known = set(session.scalars(select(CpoAlias.alias_norm)))
    wanted: dict[str, CpoAlias] = {}
    now = dt.datetime.now(dt.UTC)

    def want(raw: str, source_key: str | None) -> None:
        match = canonical_operator(raw)
        if match.raw == "(unattributed)":
            return  # the source would not say - not a name to decide on
        norm = normalise_operator(raw)
        if not norm or norm in known or norm in wanted:
            return
        status = {"exact": "confirmed", "alias": "confirmed", "not_a_network": "not_a_network"}.get(
            match.confidence, "pending"
        )
        wanted[norm] = CpoAlias(
            alias_norm=norm[:128],
            alias_raw=raw[:128],
            cpo_id=by_name.get(match.canonical) if match.canonical else None,
            status=status,
            first_seen_source_id=sources.get(source_key) if source_key else None,
            confirmed_by=None if status == "pending" else "backfill:identity.py",
            confirmed_at=None if status == "pending" else now,
        )

    for r in rows:
        if r.operator:
            want(r.operator, r.source)
    for norm, canonical in OPERATOR_ALIASES.items():
        if norm not in known and norm not in wanted and canonical in by_name:
            wanted[norm] = CpoAlias(
                alias_norm=norm[:128],
                alias_raw=norm[:128],
                cpo_id=by_name[canonical],
                status="confirmed",
                confirmed_by="backfill:identity.py",
                confirmed_at=now,
            )
    session.add_all(wanted.values())
    session.flush()
    counts["aliases_added"] += len(wanted)
    counts["aliases_pending"] += sum(1 for a in wanted.values() if a.status == "pending")
    return by_name


def _stations(
    session: Session, rows: list[Any], cpos: dict[str, int], counts: Counter[str]
) -> dict[int, Station]:
    """A station per competitor row. Returns competitor id -> Station."""
    existing: dict[int, Station] = {
        s.legacy_competitor_station_id: s
        for s in session.scalars(
            select(Station).where(Station.legacy_competitor_station_id.is_not(None))
        )
        if s.legacy_competitor_station_id is not None
    }
    made: list[Station] = []
    for r in rows:
        if r.id in existing:
            continue
        match = canonical_operator(r.operator)
        made.append(
            Station(
                legacy_competitor_station_id=r.id,
                cpo_id=cpos.get(match.canonical) if match.canonical else None,
                operator_raw=(r.operator or None) and r.operator[:128],
                name=r.name,
                town=r.town,
                postcode=r.postcode,
                lat=r.lat,
                lng=r.lng,
                lgd_district_code=r.lgd_district_code,
                lgd_state_code=r.lgd_state_code,
                access=r.access,
                is_operational=r.is_operational,
            )
        )
    for batch in _chunks(made):
        session.add_all(batch)
        session.flush()
    counts["stations_added"] += len(made)
    counts["stations_already_there"] += len(existing)
    return {
        **existing,
        **{s.legacy_competitor_station_id: s for s in made if s.legacy_competitor_station_id},
    }


def _chargers(
    session: Session, rows: list[Any], stations: dict[int, Station], counts: Counter[str]
) -> None:
    have = {
        (sid, uid)
        for sid, uid in session.execute(
            select(Charger.station_id, Charger.evse_uid).where(Charger.evse_uid.like("inferred-%"))
        )
    }
    pending: list[tuple[Charger, ConnectorPlan]] = []
    for r in rows:
        station = stations[r.id]
        plans = plan_connectors(r.connectors, r.number_of_points, r.max_power_kw)
        if r.number_of_points and len(plans) > r.number_of_points:
            # Mostly Open Charge Map, which lists the same connector more than
            # once against NumberOfPoints = 1. Kept as listed, and made visible.
            counts["stations_with_more_connectors_than_points"] += 1
        for i, plan in enumerate(plans, 1):
            uid = f"inferred-{i}"
            if (station.id, uid) in have:
                continue
            pending.append(
                (
                    Charger(
                        station_id=station.id,
                        evse_uid=uid,
                        current_type=current_type(plan.standard),
                        rated_power_kw=plan.power_kw,
                        inferred=True,
                    ),
                    plan,
                )
            )
    for batch in _chunks(pending):
        session.add_all([c for c, _ in batch])
        session.flush()
        session.add_all(
            [
                Connector(
                    charger_id=c.id, standard=p.standard, format=p.format, max_power_kw=p.power_kw
                )
                for c, p in batch
            ]
        )
        session.flush()
    counts["chargers_added"] += len(pending)
    counts["connectors_added"] += len(pending)


def _scraped(
    session: Session, sources: dict[str, int], data_dir: Path, counts: Counter[str]
) -> dict[tuple[int, str], int]:
    """Raw records into ``scraped_records``. Returns (source id, key) -> newest record id."""
    for key, (fname, id_field) in RAW_FILES.items():
        path = data_dir / fname
        if not path.exists():
            counts[f"raw_missing_{key}"] += 1
            continue
        items = json.loads(path.read_text("utf-8"))
        scraped_at = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.UTC)
        run_id = uuid.uuid4()
        values = [
            {
                "source_id": sources[key],
                "source_key": str(item[id_field]),
                "run_id": run_id,
                "scraped_at": scraped_at,
                "payload": item,
                "content_hash": content_hash(item),
            }
            for item in items
        ]
        # Not INSERT ... ON CONFLICT: Postgres refuses it on a table with an
        # UPDATE rule, and scraped_records has one (it is insert-only). So the
        # "already stored" check is done here, against what is in the table.
        seen = {
            (sid, key, h)
            for sid, key, h in session.execute(
                select(
                    ScrapedRecord.source_id, ScrapedRecord.source_key, ScrapedRecord.content_hash
                ).where(ScrapedRecord.source_id == sources[key])
            )
        }
        fresh = []
        for v in values:
            ident = (v["source_id"], v["source_key"], v["content_hash"])
            if ident not in seen:
                seen.add(ident)
                fresh.append(v)
        for batch in _chunks(fresh, 200):
            session.execute(insert(ScrapedRecord), batch)
        added = len(fresh)
        counts["scraped_records_added"] += added
        counts["scraped_records_already_there"] += len(values) - added
    session.flush()
    latest: dict[tuple[int, str], int] = {}
    for rid, sid, skey in session.execute(
        select(ScrapedRecord.id, ScrapedRecord.source_id, ScrapedRecord.source_key).order_by(
            ScrapedRecord.id
        )
    ):
        latest[(sid, skey)] = rid
    return latest


def _find_station(
    c: dict[str, Any], by_key: dict[tuple[str, str], Any], near: list[Any]
) -> Any | None:
    """The competitor row a merged charger belongs to: by any app id, else by place."""
    apps = {x["app"]: str(x["app_id"]) for x in c["listed_in"]}
    for app in (*PRIORITY, *apps):
        if app in apps and (app, _fit(apps[app])) in by_key:
            return by_key[(app, _fit(apps[app]))]
    best, best_m = None, NEAR_M + 1.0
    for r in near:
        if abs(r.lat - c["lat"]) > 0.001 or abs(r.lng - c["lng"]) > 0.001:
            continue
        m = _metres(r.lat, r.lng, c["lat"], c["lng"])
        if m > NEAR_M or m >= best_m:
            continue
        if not r.operator or not c.get("cpo") or _lead(r.operator) == _lead(c["cpo"]):
            best, best_m = r, m
    return best


def _listings(
    session: Session,
    sources: dict[str, int],
    rows: list[Any],
    stations: dict[int, Station],
    chargers_json: list[dict[str, Any]],
    scraped: dict[tuple[int, str], int],
    counts: Counter[str],
) -> None:
    taken: dict[tuple[int, str], int] = {
        (sid, key): st
        for sid, key, st in session.execute(
            select(StationListing.source_id, StationListing.source_key, StationListing.station_id)
        )
    }
    by_key = {(r.source, r.source_id): r for r in rows}
    fitted_to_full: dict[tuple[str, str], str] = {}
    made: list[StationListing] = []

    def add(
        station: Station,
        source: str,
        key: str,
        name: str | None,
        operator: str | None,
        seen: dt.datetime,
    ) -> None:
        ident = (sources[source], key)
        if ident in taken:
            counts[
                "listings_conflict" if taken[ident] != station.id else "listings_already_there"
            ] += 1
            return
        taken[ident] = station.id
        made.append(
            StationListing(
                station_id=station.id,
                source_id=sources[source],
                source_key=key[:255],
                source_name=name,
                source_operator=(operator or None) and operator[:128],
                first_seen_at=seen,
                last_seen_at=seen,
                last_scrape_id=scraped.get(ident),
            )
        )

    now = dt.datetime.now(dt.UTC)
    for c in chargers_json:
        for x in c["listed_in"]:
            fitted_to_full[(x["app"], _fit(str(x["app_id"])))] = str(x["app_id"])
        row = _find_station(c, by_key, rows)
        if row is None:
            counts["scraped_charger_without_a_station"] += 1
            continue
        station = stations[row.id]
        if not station.address and c.get("address"):
            station.address = str(c["address"]).strip() or None
            counts["addresses_filled"] += 1
        for x in c["listed_in"]:
            if x["app"] not in sources:
                counts["listings_unknown_source"] += 1
                continue
            add(
                station,
                x["app"],
                str(x["app_id"]),
                x.get("name_in_app"),
                x.get("operator_in_app"),
                row.fetched_at or now,
            )
    for r in rows:
        key = fitted_to_full.get((r.source, r.source_id), r.source_id)
        add(stations[r.id], r.source, key, r.name, r.operator, r.fetched_at or now)
    for batch in _chunks(made):
        session.add_all(batch)
        session.flush()
    counts["listings_added"] += len(made)


def backfill(session: Session, data_dir: Path, chargers_path: Path) -> Counter[str]:
    """Run every step on ``session``. Flushes, never commits."""
    counts: Counter[str] = Counter()
    sources = {s.key: s.id for s in session.scalars(select(DataSource))}
    needed = {"open_charge_map", "goec", "zeon", "pulse", "tata_power"}
    if not needed <= sources.keys():
        raise SystemExit(
            f"data_sources is missing {sorted(needed - sources.keys())}: run migration 0015"
        )
    rows = list(
        session.execute(
            select(
                CompetitorStation.id,
                CompetitorStation.source,
                CompetitorStation.source_id,
                CompetitorStation.name,
                CompetitorStation.operator,
                CompetitorStation.lat,
                CompetitorStation.lng,
                CompetitorStation.lgd_district_code,
                CompetitorStation.lgd_state_code,
                CompetitorStation.town,
                CompetitorStation.postcode,
                CompetitorStation.access,
                CompetitorStation.is_operational,
                CompetitorStation.number_of_points,
                CompetitorStation.max_power_kw,
                CompetitorStation.connectors,
                CompetitorStation.fetched_at,
            ).order_by(CompetitorStation.id)
        )
    )
    counts["competitor_rows"] = len(rows)
    cpos = _cpos_and_aliases(session, sources, rows, counts)
    stations = _stations(session, rows, cpos, counts)
    _chargers(session, rows, stations, counts)
    scraped = _scraped(session, sources, data_dir, counts)
    chargers_json = json.loads(chargers_path.read_text("utf-8"))["chargers"]
    _listings(session, sources, rows, stations, chargers_json, scraped, counts)
    session.flush()
    return counts


def totals(session: Session) -> dict[str, int]:
    return {
        model.__tablename__: session.scalar(select(func.count()).select_from(model)) or 0
        for model in (Cpo, CpoAlias, Station, Charger, Connector, StationListing, ScrapedRecord)
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default=".", help="where chargers_all.json and the raw files are")
    ap.add_argument("--write", action="store_true", help="commit (default: roll back)")
    args = ap.parse_args(argv)
    data_dir = Path(args.dir)

    with SessionLocal() as session:
        counts = backfill(session, data_dir, data_dir / "chargers_all.json")
        for k in sorted(counts):
            print(f"{counts[k]:>7}  {k}")
        print("table totals after this run:", totals(session))
        if args.write:
            session.commit()
            print("committed")
        else:
            session.rollback()
            print("rolled back (pass --write to keep)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
