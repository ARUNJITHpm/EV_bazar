"""Auditable inventory captures. Availability remains the separate poller's job."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.context.competitors import CompetitorStationData, dedupe
from app.domain.cpo.identity import CANONICAL, canonical_operator

NCR_BOUNDARY_URL = (
    "https://bharatnetprogress.nic.in/nicclouddb/rest/services/"
    "NCR/NCR_Geo_Portal_23_01_2025/MapServer/22/query"
)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Discovery boxes only. Administrative membership comes from district polygons.
STATE_BBOX = {
    "kerala": (8.0, 74.7, 13.0, 77.6),
    "tamilnadu": (8.0, 76.1, 13.7, 80.5),
    "karnataka": (11.4, 74.0, 18.6, 78.7),
    "maharashtra": (15.5, 72.5, 22.1, 80.9),
    "gujarat": (20.0, 68.0, 24.8, 74.6),
    "delhi": (28.3, 76.8, 29.0, 77.5),
    "delhincr": (26.5, 75.7, 30.0, 78.6),
}
STATE_NAMES = {
    "kerala": "kerala",
    "tamilnadu": "tamil nadu",
    "karnataka": "karnataka",
    "maharashtra": "maharashtra",
    "gujarat": "gujarat",
    "delhi": "delhi",
    "delhincr": "delhi-ncr",
}
DEFAULT_STATES = ["kerala", "tamilnadu", "karnataka", "maharashtra", "gujarat", "delhi"]
VERSION_STAMPS = {
    "schema_version": "station-inventory-v1",
    "model_version": "not_applicable",
    "economics_version": "not_applicable",
    "archetype_version": "not_applicable",
    "tariff_effective_date": None,
    "renderer_version": "station-export-v1",
}


class CaptureClient(httpx.Client):
    """Archive responses before parsing; bound requests including redirects.

    URLs omit query strings and headers are never archived (OCM keys live there).
    Failures leave a metadata record. New run directories prevent overwrites.
    """

    def __init__(
        self,
        directory: Path,
        *,
        max_requests: int = 100,
        delay_seconds: float = 1,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if max_requests < 1 or delay_seconds < 0:
            raise ValueError("invalid request budget or delay")
        directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        self.max_requests = max_requests
        self.delay_seconds = delay_seconds
        self.requests_sent = 0
        self._last_request: float | None = None
        self.source = "unknown"
        self.records: list[dict[str, Any]] = []
        super().__init__(
            transport=transport,
            event_hooks={
                "request": [self._before],
                "response": [self._archive],
            },
        )

    def _before(self, request: httpx.Request) -> None:
        if self.requests_sent >= self.max_requests:
            raise RuntimeError("request budget exhausted; refusing external call")
        if self._last_request is not None:
            time.sleep(max(0, self.delay_seconds - (time.monotonic() - self._last_request)))
        self._last_request = time.monotonic()
        self.requests_sent += 1
        record = {
            "sequence": self.requests_sent,
            "source": self.source,
            "url": str(request.url.copy_with(query=None)),
            "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
            "status": None,
            "outcome": "no_response",
            **VERSION_STAMPS,
        }
        # Written before traffic. Transport failures retain a no_response record.
        self.records.append(record)
        self._write_record(record)
        request.extensions["capture_sequence"] = self.requests_sent

    def _write_record(self, record: dict[str, Any]) -> None:
        path = self.directory / f"{record['sequence']:04d}.json"
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    def _archive(self, response: httpx.Response) -> None:
        sequence = response.request.extensions["capture_sequence"]
        record = self.records[sequence - 1]
        record["status"] = response.status_code
        self._write_record(record)
        body = response.read()
        path = self.directory / f"{sequence:04d}.body"
        with path.open("xb") as stream:
            stream.write(body)
        record.update(
            outcome="archived", body_file=path.name, sha256=hashlib.sha256(body).hexdigest()
        )
        self._write_record(record)


def valid_coordinates(station: CompetitorStationData) -> bool:
    return (
        math.isfinite(station.lat)
        and math.isfinite(station.lng)
        and -90 <= station.lat <= 90
        and -180 <= station.lng <= 180
    )


def read_station_csv(path: Path, *, source: str) -> list[CompetitorStationData]:
    """Portable CPO exports: strict coordinates/IDs, nullable metadata.

    Keep provider state/district claims in the archived CSV; never trust them
    as administrative assignments. Unknown operational status stays NULL.
    """
    if not source or len(source) > 32:
        raise ValueError("source must be 1..32 characters")
    stations = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"source_id", "latitude", "longitude", "operator"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"CSV needs columns: {sorted(required)}")
        for line, row in enumerate(reader, 2):
            sid = row["source_id"].strip()
            if not sid or len(sid) > 64:
                raise ValueError(f"line {line}: invalid source_id")
            updated = row.get("source_last_status_update") or None
            timestamp = (
                dt.datetime.fromisoformat(updated.replace("Z", "+00:00")) if updated else None
            )
            if timestamp is not None and timestamp.tzinfo is None:
                raise ValueError(f"line {line}: source timestamp needs timezone")
            station = CompetitorStationData(
                source=source,
                source_id=sid,
                lat=float(row["latitude"]),
                lng=float(row["longitude"]),
                operator=row["operator"].strip() or None,
                name=row.get("name") or None,
                town=row.get("town") or None,
                postcode=row.get("postcode") or None,
                source_last_status_update=timestamp,
            )
            if not valid_coordinates(station):
                raise ValueError(f"line {line}: invalid latitude/longitude")
            stations.append(station)
    return dedupe(stations)


_LOCATE = text("""
    SELECT t.idx, d.lgd_district_code, d.lgd_state_code, d.name, d.state_name,
           d.boundary_vintage
    FROM unnest(CAST(:lats AS double precision[]), CAST(:lngs AS double precision[]))
         WITH ORDINALITY AS t(lat, lng, idx)
    JOIN districts d ON ST_Covers(d.geom, ST_SetSRID(ST_MakePoint(t.lng, t.lat), 4326))
    ORDER BY t.idx
""")


def locate_stations(
    session: Session, stations: list[CompetitorStationData]
) -> list[dict[str, Any]]:
    """Single spatial query. Multiple matches are ambiguous, never LIMIT 1."""
    matches: dict[int, list[Any]] = {}
    if stations:
        for row in session.execute(
            _LOCATE,
            {
                "lats": [s.lat for s in stations],
                "lngs": [s.lng for s in stations],
            },
        ):
            matches.setdefault(int(row[0]) - 1, []).append(row)
    result = []
    for index in range(len(stations)):
        rows = matches.get(index, [])
        single = rows[0] if len(rows) == 1 else None
        result.append(
            {
                "lgd_district_code": single[1] if single else None,
                "lgd_state_code": single[2] if single else None,
                "district": single[3] if single else None,
                "state": single[4] if single else None,
                "boundary_vintage": single[5] if single else None,
                "resolution": "contained" if single else "ambiguous" if rows else "unplaced",
            }
        )
    return result


def export_rows(
    stations: list[CompetitorStationData],
    locations: list[dict[str, Any]],
    *,
    states: list[str],
    fetched_at: dt.datetime,
    stale_days: int = 30,
    ncr_boundary: Any = None,
) -> tuple[list[dict[str, Any]], list[CompetitorStationData]]:
    """Resolved neighbours outside the selected states are excluded, not relabelled."""
    names = {STATE_NAMES[s] for s in states if s != "delhincr"}
    if "delhincr" in states and ncr_boundary is None:
        raise ValueError("Delhi-NCR requires the archived official region boundary")
    output, selected = [], []
    for station, location in zip(stations, locations, strict=True):
        in_ncr = False
        if "delhincr" in states:
            from shapely.geometry import Point

            in_ncr = bool(ncr_boundary.covers(Point(station.lng, station.lat)))
        if location["state"] and location["state"].casefold() not in names and not in_ncr:
            continue
        match = canonical_operator(station.operator)
        updated = station.source_last_status_update
        # Some legacy parser timestamps lack a timezone. Do not invent UTC.
        age = (fetched_at - updated).total_seconds() / 86400 if updated and updated.tzinfo else None
        freshness = (
            "unknown"
            if age is None
            else "future_timestamp"
            if age < 0
            else "stale"
            if age > stale_days
            else "recent_source_update"
        )
        output.append(
            {
                **asdict(station),
                **location,
                **VERSION_STAMPS,
                "latitude": station.lat,
                "longitude": station.lng,
                "canonical_operator": match.canonical,
                "operator_match": match.confidence,
                "fetched_at": fetched_at.isoformat(),
                "freshness": freshness,
                "source_age_days": round(age, 1) if age is not None else None,
                "in_selected_states": True if location["state"] else None,
                "target_region": "delhi-ncr" if in_ncr else location["state"],
            }
        )
        if location["resolution"] == "contained":
            selected.append(station)
    return output, selected


def coverage_gaps(rows: list[dict[str, Any]], states: list[str]) -> list[dict[str, Any]]:
    """Missing listings mean missing evidence, never zero actual stations."""
    return [
        {
            "state": STATE_NAMES[state],
            "operator": operator,
            "source_rows": sum(
                r["canonical_operator"] == operator
                and (r.get("target_region", r["state"]) or "").casefold() == STATE_NAMES[state]
                for r in rows
            ),
            "coverage": "observed_listings_only",
        }
        for state in states
        for operator in CANONICAL
    ]


def fetch_ncr_boundary(client: httpx.Client) -> Any:
    """Official RP-2021 subregion boundary; WGS84, archived by CaptureClient."""
    from shapely.geometry import shape
    from shapely.ops import unary_union

    response = client.get(
        NCR_BOUNDARY_URL,
        params={
            "where": "1=1",
            "outFields": "*",
            "outSR": 4326,
            "f": "geojson",
        },
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list) or len(features) != 4:
        raise ValueError("NCR boundary must return all four official subregions")
    boundary = unary_union([shape(f["geometry"]) for f in features])
    if boundary.is_empty or not boundary.is_valid:
        raise ValueError("NCR boundary is invalid")
    return boundary


def parse_osm_stations(payload: object) -> list[CompetitorStationData]:
    """OSM elements, preserving IDs and unattributed operators; no status inference."""
    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise ValueError("invalid Overpass payload")
    if payload.get("remark"):
        raise ValueError("Overpass partial/error response")
    stations = []
    for element in payload["elements"]:
        tags = element.get("tags", {})
        if tags.get("amenity") != "charging_station":
            continue
        coordinates = element if element.get("type") == "node" else element.get("center", {})
        lat, lng = coordinates.get("lat"), coordinates.get("lon")
        if lat is None or lng is None or element.get("id") is None:
            continue
        station = CompetitorStationData(
            source="openstreetmap",
            source_id=f"{element['type']}/{element['id']}",
            lat=float(lat),
            lng=float(lng),
            name=tags.get("name"),
            operator=tags.get("operator") or tags.get("network"),
            town=tags.get("addr:city"),
            postcode=tags.get("addr:postcode"),
            access={"yes": "public", "private": "private", "customers": "restricted"}.get(
                tags.get("access")
            ),
            data_provider="OpenStreetMap contributors; ODbL 1.0",
        )
        if not valid_coordinates(station):
            raise ValueError("invalid OSM coordinates")
        stations.append(station)
    return dedupe(stations)


def fetch_osm_states(
    client: httpx.Client,
    states: list[str],
    *,
    url: str = OVERPASS_URL,
) -> list[CompetitorStationData]:
    stations = []
    for state in dict.fromkeys(states):
        box = ",".join(str(v) for v in STATE_BBOX[state])
        query = f'[out:json][timeout:90];nwr["amenity"="charging_station"]({box});out center meta;'
        response = client.post(url, data={"data": query}, timeout=120)
        response.raise_for_status()
        stations.extend(parse_osm_stations(response.json()))
    return dedupe(stations)


def persist_inventory_rows(session: Session, rows: list[dict[str, Any]]) -> int:
    """Bulk cache upsert in one transaction. Unresolved points never enter the cache."""
    from sqlalchemy.dialects.postgresql import insert

    from app.models.competitors import CompetitorStation

    columns = (
        "source",
        "source_id",
        "name",
        "operator",
        "lat",
        "lng",
        "town",
        "postcode",
        "access",
        "is_operational",
        "number_of_points",
        "max_power_kw",
        "data_provider",
        "lgd_state_code",
        "lgd_district_code",
        "fetched_at",
        "source_last_status_update",
    )
    values = []
    for row in rows:
        if row["resolution"] != "contained":
            continue
        value = {key: row.get(key) for key in columns}
        value["fetched_at"] = dt.datetime.fromisoformat(row["fetched_at"])
        value["connectors"] = [
            {
                "type": c["connector_type"],
                "power_kw": c["power_kw"],
                "quantity": c["quantity"],
            }
            for c in row["connectors"]
        ] or None
        values.append(value)
    for offset in range(0, len(values), 300):
        statement = insert(CompetitorStation).values(values[offset : offset + 300])
        session.execute(
            statement.on_conflict_do_update(
                constraint="uq_competitor_source",
                set_={
                    key: getattr(statement.excluded, key)
                    for key in values[0]
                    if key not in {"source", "source_id"}
                },
            )
        )
    return len(values)


def collect_source(
    name: str,
    fetch: Callable[[], list[CompetitorStationData]],
    outcomes: dict[str, dict[str, Any]],
) -> list[CompetitorStationData]:
    """Isolate failed sources; never publish a partial source as a complete refresh."""
    try:
        stations = fetch()
        if any(not valid_coordinates(s) for s in stations):
            raise ValueError("source returned invalid coordinates")
        if not stations:
            raise ValueError("empty source response; needs review")
        outcomes[name] = {"status": "ok", "parsed_stations": len(stations)}
        return dedupe(stations)
    except (httpx.HTTPError, ValueError, TypeError, KeyError, RuntimeError) as error:
        # HTTP exception messages can contain the OCM key-bearing request URL.
        outcomes[name] = {"status": "failed", "error_type": type(error).__name__}
        return []
