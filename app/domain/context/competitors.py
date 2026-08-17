"""Competitor stations from Open Charge Map - PART 2.3.

Same fetch/parse split as the geocoders and the poller: ``parse_ocm_poi`` is a
pure function over one OCM record, ``fetch_ocm`` does HTTP and nothing else,
and ``store_stations`` is the thin shell that resolves each point to a district
(PLAN 1.4) and upserts. A field OCM renames, or a coordinate we read wrong, is
then a bug in a tested pure function rather than something tangled with the
network.

Why OCM as the first source (CPO_SOURCES.md): one free-key REST API over all of
India, versus reverse-engineering seven apps. It carries a station's existence
and specs and an operational flag - NOT live occupancy, which stays the
poller's job. So this builds the competitor *denominator*; the poller fills in
*how busy* later, attaching to these rows.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field
from typing import Any

import httpx

OCM_BASE_URL = "https://api.openchargemap.io/v3"

#: OCM's UsageType.Title vocabulary -> our compact ``access`` values. A members
#: -only depot is a different competitive threat from a public forecourt, so
#: the distinction is kept rather than flattened to "exists".
_ACCESS_MAP = {
    "public": "public",
    "public - membership required": "membership",
    "public - notice required": "public",
    "public - pay at location": "public",
    "private - restricted access": "restricted",
    "private - for staff, visitors": "restricted",
    "privately owned - notice required": "restricted",
}


def map_access(usage_title: str | None) -> str | None:
    if not usage_title:
        return None
    return _ACCESS_MAP.get(
        usage_title.strip().lower(), "public" if "public" in usage_title.lower() else "private"
    )


@dataclass(frozen=True)
class Connector:
    connector_type: str | None
    power_kw: float | None
    quantity: int


@dataclass(frozen=True)
class CompetitorStationData:
    """One parsed station, source-agnostic. What ``store_stations`` writes."""

    source: str
    source_id: str
    lat: float
    lng: float

    name: str | None = None
    operator: str | None = None
    town: str | None = None
    postcode: str | None = None
    access: str | None = None
    is_operational: bool | None = None
    number_of_points: int | None = None
    max_power_kw: float | None = None
    connectors: tuple[Connector, ...] = ()
    data_provider: str | None = None
    source_last_status_update: dt.datetime | None = None

    def connectors_json(self) -> list[dict[str, Any]] | None:
        if not self.connectors:
            return None
        return [
            {"type": c.connector_type, "power_kw": c.power_kw, "quantity": c.quantity}
            for c in self.connectors
        ]


def _to_float(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _parse_dt(v: object) -> dt.datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        return dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_connections(connections: object) -> tuple[tuple[Connector, ...], float | None]:
    """Connectors and the peak power. Pure.

    Peak power is the single number the "any DC fast within 3 km" filter needs;
    the full list is kept for the detailed comparison. A connection with no
    usable power contributes to neither.
    """
    if not isinstance(connections, list):
        return (), None
    out: list[Connector] = []
    powers: list[float] = []
    for c in connections:
        if not isinstance(c, dict):
            continue
        ctype = (c.get("ConnectionType") or {}).get("Title")
        power = _to_float(c.get("PowerKW"))
        qty = c.get("Quantity")
        out.append(
            Connector(
                connector_type=ctype.strip() if isinstance(ctype, str) else None,
                power_kw=power,
                quantity=int(qty) if isinstance(qty, int) else 1,
            )
        )
        if power:
            powers.append(power)
    return tuple(out), (max(powers) if powers else None)


def parse_ocm_poi(poi: Any, *, source: str = "open_charge_map") -> CompetitorStationData | None:
    """One OCM POI -> a station, or None. Pure.

    Returns None rather than a guess when the record has no stable id or no
    coordinates - a station we cannot key or cannot place is not worth a row.
    """
    if not isinstance(poi, dict):
        return None
    source_id = poi.get("UUID") or (str(poi["ID"]) if poi.get("ID") is not None else None)
    if not source_id:
        return None

    ai = poi.get("AddressInfo") or {}
    lat = _to_float(ai.get("Latitude"))
    lng = _to_float(ai.get("Longitude"))
    if lat is None or lng is None:
        return None

    op = poi.get("OperatorInfo") or {}
    operator = op.get("Title") if isinstance(op, dict) else None
    status = poi.get("StatusType") or {}
    usage = poi.get("UsageType") or {}
    provider = poi.get("DataProvider") or {}

    connectors, max_kw = parse_connections(poi.get("Connections"))

    return CompetitorStationData(
        source=source,
        source_id=str(source_id),
        lat=lat,
        lng=lng,
        name=ai.get("Title"),
        operator=operator.strip() if isinstance(operator, str) else None,
        town=ai.get("Town"),
        postcode=str(ai.get("Postcode")) if ai.get("Postcode") else None,
        access=map_access(usage.get("Title") if isinstance(usage, dict) else None),
        is_operational=status.get("IsOperational") if isinstance(status, dict) else None,
        number_of_points=poi.get("NumberOfPoints"),
        max_power_kw=max_kw,
        connectors=connectors,
        data_provider=provider.get("Title") if isinstance(provider, dict) else None,
        source_last_status_update=_parse_dt(poi.get("DateLastStatusUpdate")),
    )


# ---------------------------------------------------------------------------
# The I/O shell.
# ---------------------------------------------------------------------------


@dataclass
class FetchResult:
    stations: list[CompetitorStationData] = field(default_factory=list)
    raw_count: int = 0
    parsed_count: int = 0


def tile_bbox(
    bbox: tuple[float, float, float, float], *, rows: int, cols: int
) -> list[tuple[float, float, float, float]]:
    """Split a bounding box into a rows x cols grid. Pure.

    OCM caps one response at ~500 POIs, so a dense state is covered by tiling
    and deduping on ``source_id`` rather than by paging (which OCM does not do
    well). Cells overlap nothing; a station on a tile edge lands in one cell.
    """
    south, west, north, east = bbox
    dlat = (north - south) / rows
    dlng = (east - west) / cols
    tiles: list[tuple[float, float, float, float]] = []
    for r in range(rows):
        for c in range(cols):
            tiles.append(
                (south + r * dlat, west + c * dlng, south + (r + 1) * dlat, west + (c + 1) * dlng)
            )
    return tiles


def dedupe(stations: list[CompetitorStationData]) -> list[CompetitorStationData]:
    """One row per (source, source_id) - the last seen wins. Pure.

    Tiles never overlap, but a station exactly on a shared edge can be returned
    by two adjacent OCM queries, so the accumulation is deduped before storage.
    """
    seen: dict[tuple[str, str], CompetitorStationData] = {}
    for s in stations:
        seen[(s.source, s.source_id)] = s
    return list(seen.values())


def fetch_ocm(
    client: httpx.Client,
    api_key: str,
    *,
    bbox: tuple[float, float, float, float] | None = None,
    lat: float | None = None,
    lng: float | None = None,
    distance_km: float = 25.0,
    country_code: str = "IN",
    max_results: int = 500,
    base_url: str = OCM_BASE_URL,
) -> FetchResult:
    """Fetch stations for a bounding box OR a point+radius. Pure HTTP.

    A bounding box (``(lat1, lng1, lat2, lng2)``) is preferred for covering a
    state; the point+radius form is for "near this candidate site". Exactly one
    of ``bbox`` or ``lat``/``lng`` should be given.
    """
    # verbose=false trims the payload but KEEPS OperatorInfo.Title and connector
    # power - compact=true drops the operator, which is the field a competitor
    # comparison turns on, so it is deliberately not used.
    params: dict[str, str | int | float] = {
        "output": "json",
        "countrycode": country_code,
        "maxresults": max_results,
        "verbose": "false",
        "key": api_key,
    }
    if bbox is not None:
        # OCM wants "(lat1,lng1),(lat2,lng2)".
        params["boundingbox"] = f"({bbox[0]},{bbox[1]}),({bbox[2]},{bbox[3]})"
    elif lat is not None and lng is not None:
        params["latitude"] = lat
        params["longitude"] = lng
        params["distance"] = distance_km
        params["distanceunit"] = "km"
    else:
        raise ValueError("give either bbox or lat+lng")

    response = client.get(
        f"{base_url}/poi/",
        params=params,
        headers={"User-Agent": "EVSiteIntelligence/0.1 (software@chargemod.com)"},
        timeout=60.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return FetchResult()

    parsed = [s for s in (parse_ocm_poi(p) for p in payload) if s is not None]
    return FetchResult(stations=parsed, raw_count=len(payload), parsed_count=len(parsed))


# ---------------------------------------------------------------------------
# Additional public inventory sources: GoEC and Zeon.
#
# Each serves a plain public JSON endpoint - no key, robots-permissive, verified
# live 2026-08-15. INVENTORY ONLY, exactly like OCM: existence + specs, never
# occupancy. They earn their place because each is dense where OCM is thin - GoEC
# dominates Kerala, Zeon is strong in Tamil Nadu - so together they thicken the
# KL+TN competitor denominator. Same fetch/parse split; kept beside OCM because
# they produce the same ``CompetitorStationData`` and store through one shell.
#
# They carry their own ``source`` ("goec"/"zeon"), so a GO EC station seen via
# both OCM and GoEC's own feed is two rows until PLAN 2.3's downstream dedupe -
# the overlap is signal, reconciled at analysis time, not dropped at fetch.
# ---------------------------------------------------------------------------

GOEC_URL = "https://www.goecworld.com/api/stations/locations"  # bare host 308-redirects to www
ZEON_URL = "https://zeoncharging.com/api/stations"

_INVENTORY_UA = {"User-Agent": "EVSiteIntelligence/0.1 (software@chargemod.com)"}


def _stable_id(prefix: str, *parts: object) -> str:
    """A deterministic, <=64-char id for a source that ships none of its own.

    Hashing (label, rounded lat/lng) is stable across fetches, so the upsert key
    stays constant and a re-fetch updates in place rather than duplicating.
    """
    digest = hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()[:24]  # noqa: S324
    return f"{prefix}-{digest}"


def parse_goec_stations(rows: object) -> list[CompetitorStationData]:
    """GoEC's flat rows -> one station per (label, point). Pure.

    The endpoint returns roughly one row PER CONNECTOR - a station with two
    chargers appears twice, identical label and coordinates, different ``power``
    - so rows are grouped by (label, lat, lng) into a single station whose
    connectors are the grouped rows. No stable id ships, so one is derived from
    the label and rounded coordinates.
    """
    if not isinstance(rows, list):
        return []
    groups: dict[tuple[str, float, float], list[dict[str, Any]]] = {}
    order: list[tuple[str, float, float]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        lat = _to_float(r.get("lat"))
        lng = _to_float(r.get("lng"))
        if lat is None or lng is None:
            continue
        key = (str(r.get("label") or "").strip(), round(lat, 6), round(lng, 6))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)

    out: list[CompetitorStationData] = []
    for label, lat, lng in order:
        members = groups[(label, lat, lng)]
        connectors: list[Connector] = []
        powers: list[float] = []
        for m in members:
            p = _to_float(m.get("power"))
            connectors.append(Connector(connector_type=None, power_kw=p, quantity=1))
            if p:
                powers.append(p)
        out.append(
            CompetitorStationData(
                source="goec",
                source_id=_stable_id("goec", label, f"{lat:.6f}", f"{lng:.6f}"),
                lat=lat,
                lng=lng,
                name=label or None,
                operator="GO EC",
                number_of_points=len(members),
                max_power_kw=max(powers) if powers else None,
                connectors=tuple(connectors),
            )
        )
    return out


def parse_zeon_station(rec: object) -> CompetitorStationData | None:
    """One Zeon ``data[]`` record -> a station, or None. Pure.

    Zeon ships a stable integer ``id`` and a ``connector_data`` list, so this is
    a straight field map - the connector count and peak power come from that
    list, the town/postcode from the nested ``address``.
    """
    if not isinstance(rec, dict):
        return None
    sid = rec.get("id")
    lat = _to_float(rec.get("latitude"))
    lng = _to_float(rec.get("longitude"))
    if sid is None or lat is None or lng is None:
        return None

    addr_raw = rec.get("address")
    addr: dict[str, Any] = addr_raw if isinstance(addr_raw, dict) else {}
    connectors: list[Connector] = []
    powers: list[float] = []
    points = 0
    conns = rec.get("connector_data")
    if isinstance(conns, list):
        for c in conns:
            if not isinstance(c, dict):
                continue
            p = _to_float(c.get("peak_power"))
            qty = c.get("connector_count")
            qty = int(qty) if isinstance(qty, int) else 1
            ctype = c.get("connector_type")
            connectors.append(
                Connector(
                    connector_type=ctype.strip() if isinstance(ctype, str) else None,
                    power_kw=p,
                    quantity=qty,
                )
            )
            points += qty
            if p:
                powers.append(p)

    zip_code = addr.get("zipCode")
    return CompetitorStationData(
        source="zeon",
        source_id=str(sid),
        lat=lat,
        lng=lng,
        name=rec.get("station_name"),
        operator="Zeon",
        town=addr.get("city"),
        postcode=str(zip_code) if zip_code else None,
        access=map_access(rec.get("accessibility_type")),
        number_of_points=points or None,
        max_power_kw=max(powers) if powers else None,
        connectors=tuple(connectors),
    )


def fetch_goec(client: httpx.Client, *, url: str = GOEC_URL) -> FetchResult:
    """Fetch the whole GoEC station list (one national GET). Pure HTTP."""
    response = client.get(url, headers=_INVENTORY_UA, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    stations = parse_goec_stations(payload)
    raw = len(payload) if isinstance(payload, list) else 0
    return FetchResult(stations=stations, raw_count=raw, parsed_count=len(stations))


def fetch_zeon(client: httpx.Client, *, url: str = ZEON_URL) -> FetchResult:
    """Fetch the whole Zeon station list (one national GET). Pure HTTP."""
    response = client.get(url, headers=_INVENTORY_UA, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return FetchResult()
    stations = [s for s in (parse_zeon_station(rec) for rec in data) if s is not None]
    return FetchResult(stations=stations, raw_count=len(data), parsed_count=len(stations))
