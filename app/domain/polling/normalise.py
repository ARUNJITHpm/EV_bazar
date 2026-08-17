"""Payload -> observations. Pure functions, no DB, no network.

Kept pure for the same reason the ROI engine is: this is where the subtle
bugs live. A status vocabulary mapped wrong silently corrupts three years of
occupancy history, and the corruption is invisible until someone tries to
train on it.

Everything here is exhaustively unit-tested without a database.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from app.models.charger_status import ConnectorStatus


@dataclass(frozen=True)
class ChargerObservation:
    """One connector, one moment. The unit the poller writes."""

    source: str
    source_station_id: str
    connector_id: str
    status: ConnectorStatus
    observed_at: dt.datetime
    raw_payload: dict[str, Any] | None = None


#: OCPI 2.2 EVSE status vocabulary -> our five.
#:
#: BLOCKED and RESERVED both mean "physically there but you cannot use it",
#: which is occupancy from a site-assessment point of view - a driver
#: arriving finds it unusable either way.
OCPI_STATUS_MAP: dict[str, ConnectorStatus] = {
    "AVAILABLE": ConnectorStatus.AVAILABLE,
    "CHARGING": ConnectorStatus.CHARGING,
    "BLOCKED": ConnectorStatus.OCCUPIED,
    "RESERVED": ConnectorStatus.OCCUPIED,
    "INOPERATIVE": ConnectorStatus.OFFLINE,
    "OUTOFORDER": ConnectorStatus.OFFLINE,
    "REMOVED": ConnectorStatus.OFFLINE,
    "PLANNED": ConnectorStatus.UNKNOWN,
    "UNKNOWN": ConnectorStatus.UNKNOWN,
}


def map_ocpi_status(raw: str | None) -> ConnectorStatus:
    """Map an OCPI status, defaulting to UNKNOWN rather than guessing.

    An unrecognised status must never be coerced to AVAILABLE. Inventing
    availability is how a site looks busier - or emptier - than it was, and
    the raw payload is retained precisely so a bad mapping is fixable later.
    """
    if not raw:
        return ConnectorStatus.UNKNOWN
    return OCPI_STATUS_MAP.get(raw.strip().upper(), ConnectorStatus.UNKNOWN)


def _parse_timestamp(value: Any, fallback: dt.datetime) -> dt.datetime:
    """Parse an OCPI timestamp, falling back to our own observation time.

    A source's clock is not authoritative and is sometimes absent. A naive
    timestamp is assumed UTC, which is what OCPI mandates.
    """
    if not isinstance(value, str):
        return fallback
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return fallback
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def from_ocpi_locations(
    payload: dict[str, Any],
    *,
    source: str,
    observed_at: dt.datetime,
) -> tuple[ChargerObservation, ...]:
    """Flatten an OCPI ``GET /locations`` response into observations.

    Shape: ``{"data": [{location, evses: [{uid, status, connectors: [...]}]}]}``

    One row per *connector*, not per EVSE. An EVSE with two connectors that
    can only serve one car at a time still produces two rows - the physical
    truth is recovered later by joining on station identity, and throwing
    detail away at ingest time is not recoverable.
    """
    observations: list[ChargerObservation] = []

    for location in _as_list(payload.get("data")):
        station_id = _first_str(location, ("id", "location_id", "uid"))
        if not station_id:
            continue

        for evse in _as_list(location.get("evses")):
            status = map_ocpi_status(evse.get("status"))
            seen_at = _parse_timestamp(evse.get("last_updated"), observed_at)
            evse_uid = _first_str(evse, ("uid", "evse_id", "id")) or station_id

            connectors = _as_list(evse.get("connectors"))
            if not connectors:
                # An EVSE with no connector list still carries a status, and
                # dropping it would silently lose a charge point.
                observations.append(
                    ChargerObservation(
                        source=source,
                        source_station_id=station_id,
                        connector_id=evse_uid,
                        status=status,
                        observed_at=seen_at,
                        raw_payload={"evse": evse},
                    )
                )
                continue

            for connector in connectors:
                connector_id = _first_str(connector, ("id", "connector_id"))
                observations.append(
                    ChargerObservation(
                        source=source,
                        source_station_id=station_id,
                        connector_id=f"{evse_uid}:{connector_id}" if connector_id else evse_uid,
                        status=status,
                        observed_at=seen_at,
                        raw_payload={"evse": evse, "connector": connector},
                    )
                )

    return tuple(observations)


#: Scraped-app status vocabulary -> our five.
#:
#: Shared by every scraped CPO app (ChargeZone, Statiq, Kazam, chargeMOD, Tata
#: Power EZ, Ather Grid, Jio-bp). Their apps mostly speak the same handful of
#: words; where one differs, add its word here rather than forking the map. An
#: unmapped word becomes UNKNOWN, never a guessed AVAILABLE (see
#: ``map_scrape_status``).
#:
#: ⚠️ EXTEND THESE KEYS as each app's real vocabulary is captured (browser
#: devtools / mitmproxy). The right-hand side - our five statuses - does not
#: change; only the left-hand source words do.
SCRAPE_STATUS_MAP: dict[str, ConnectorStatus] = {
    "available": ConnectorStatus.AVAILABLE,
    "free": ConnectorStatus.AVAILABLE,
    "charging": ConnectorStatus.CHARGING,
    "in_use": ConnectorStatus.CHARGING,
    "inuse": ConnectorStatus.CHARGING,
    "busy": ConnectorStatus.CHARGING,
    "occupied": ConnectorStatus.OCCUPIED,
    "plugged": ConnectorStatus.OCCUPIED,
    "reserved": ConnectorStatus.OCCUPIED,
    "preparing": ConnectorStatus.OCCUPIED,
    "finishing": ConnectorStatus.OCCUPIED,
    "unavailable": ConnectorStatus.OFFLINE,
    "offline": ConnectorStatus.OFFLINE,
    "faulted": ConnectorStatus.OFFLINE,
    "fault": ConnectorStatus.OFFLINE,
    "outoforder": ConnectorStatus.OFFLINE,
    "out_of_order": ConnectorStatus.OFFLINE,
    "outofservice": ConnectorStatus.OFFLINE,  # Tata / Google availability vocab
    "out_of_service": ConnectorStatus.OFFLINE,
    "maintenance": ConnectorStatus.OFFLINE,
    "unknown": ConnectorStatus.UNKNOWN,
}


def map_scrape_status(raw: str | None) -> ConnectorStatus:
    """Map a scraped app's status word, defaulting to UNKNOWN not a guess.

    Same discipline as ``map_ocpi_status``: never invent AVAILABLE for a word
    we do not recognise. A site that looks busier or emptier than it was
    corrupts the occupancy history silently, and the raw payload is kept so a
    mapping fixed tomorrow re-derives today's truth.
    """
    if not raw:
        return ConnectorStatus.UNKNOWN
    return SCRAPE_STATUS_MAP.get(raw.strip().lower(), ConnectorStatus.UNKNOWN)


def from_scraped_stations(
    payload: dict[str, Any] | list[Any],
    *,
    source: str,
    observed_at: dt.datetime,
) -> tuple[ChargerObservation, ...]:
    """Flatten a scraped CPO app's stations response into observations.

    ###################################################################
    #  THE ONE PLACE TO CORRECT AFTER CAPTURING A REAL PAYLOAD.        #
    #  Everything downstream (adapter, ingest, occupancy maths) is     #
    #  already correct and shape-agnostic. Only the field names below  #
    #  and SCRAPE_STATUS_MAP above depend on the real JSON. Each app's #
    #  shape differs; the tolerant key lookups below absorb most of it. #
    ###################################################################

    Assumed shape (adjust the key candidates to what the app actually sends)::

        {
          "stations": [
            {
              "id": "KL-TVM-001",
              "connectors": [
                {"id": "1", "status": "available", "type": "CCS2", "power_kw": 60}
              ]
            }
          ]
        }

    One row per *connector*, exactly like the OCPI path: an unusable connector
    is occupancy from a driver's point of view, and detail thrown away at
    ingest is not recoverable. A station with no connector list still yields
    one row on its own status so a charge point is never silently dropped.

    Key lookups are tolerant (several candidate names each) so a minor naming
    difference in the real payload does not need a code change - only a genuinely
    different structure does.
    """
    observations: list[ChargerObservation] = []

    # The station list may sit under any of these keys, or be a bare list.
    if isinstance(payload, list):
        stations = _as_list(payload)  # payload itself is already a list of stations
    else:
        stations = (
            _as_list(payload.get("stations"))
            or _as_list(payload.get("data"))
            or _as_list(payload.get("results"))
            or _as_list(payload.get("statusList"))  # Tata EZ Charge wraps the list here
        )

    for station in stations:
        station_id = _first_str(
            station, ("id", "station_id", "stationId", "chargingStationId", "cpId", "uuid", "code")
        )
        if not station_id:
            continue

        connectors = (
            _as_list(station.get("connectors"))
            or _as_list(station.get("chargers"))
            or _as_list(station.get("ports"))
            or _as_list(station.get("evses"))
        )

        if not connectors:
            # Station-level status only. Still a charge point; keep it.
            observations.append(
                ChargerObservation(
                    source=source,
                    source_station_id=station_id,
                    connector_id=station_id,
                    status=map_scrape_status(
                        _first_str(station, ("status", "state", "availability", "stationStatus"))
                    ),
                    observed_at=observed_at,
                    raw_payload={"station": station},
                )
            )
            continue

        for index, connector in enumerate(connectors):
            connector_id = _first_str(
                connector, ("id", "connector_id", "portId", "evse_id")
            ) or str(index)
            observations.append(
                ChargerObservation(
                    source=source,
                    source_station_id=station_id,
                    connector_id=connector_id,
                    status=map_scrape_status(
                        _first_str(connector, ("status", "state", "availability"))
                    ),
                    observed_at=observed_at,
                    raw_payload={"connector": connector},
                )
            )

    return dedupe(tuple(observations))


def dedupe(observations: tuple[ChargerObservation, ...]) -> tuple[ChargerObservation, ...]:
    """Collapse repeats of the same connector within one poll cycle.

    A paginated feed can return the same location twice. Writing both would
    double-count that connector in every occupancy average computed later.
    Last observation wins - it is the more recent truth.
    """
    seen: dict[tuple[str, str, str], ChargerObservation] = {}
    for obs in observations:
        seen[(obs.source, obs.source_station_id, obs.connector_id)] = obs
    return tuple(seen.values())


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    return []


def _first_str(obj: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int):
            return str(value)
    return None
