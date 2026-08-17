"""GoEC and Zeon inventory parsers - PART 2.3.

Both are pure functions over one source's public JSON (shapes captured live
2026-08-15). What is worth pinning: GoEC ships roughly one row PER CONNECTOR with
no id, so rows must collapse to one station per (label, point) with a stable
derived id; Zeon ships a real id and a connector list, so its counts and peak
power must come from that list.
"""

from __future__ import annotations

from app.domain.context.competitors import parse_goec_stations, parse_zeon_station

# --- GoEC --------------------------------------------------------------------

# A two-connector station (same label + coords, appears twice) plus a second
# station elsewhere - the real endpoint's shape.
_GOEC_ROWS = [
    {"label": "GO EC KOCHI HUB", "lat": 9.9312, "lng": 76.2673, "power": "60", "state": "kerala"},
    {"label": "GO EC KOCHI HUB", "lat": 9.9312, "lng": 76.2673, "power": "30", "state": "kerala"},
    {"label": "GO EC MADURAI", "lat": 9.9252, "lng": 78.1198, "power": "3.3", "state": "tamilnadu"},
]


def test_goec_collapses_connector_rows_into_one_station() -> None:
    stations = parse_goec_stations(_GOEC_ROWS)
    assert len(stations) == 2  # not 3
    kochi = next(s for s in stations if s.name == "GO EC KOCHI HUB")
    assert kochi.operator == "GO EC"
    assert kochi.number_of_points == 2  # two connector rows
    assert kochi.max_power_kw == 60.0  # max of 60, 30
    assert len(kochi.connectors) == 2


def test_goec_id_is_stable_across_fetches() -> None:
    first = parse_goec_stations(_GOEC_ROWS)
    again = parse_goec_stations(_GOEC_ROWS)
    assert {s.source_id for s in first} == {s.source_id for s in again}
    # and short enough for the source_id column (<=64)
    assert all(len(s.source_id) <= 64 for s in first)
    assert all(s.source == "goec" for s in first)


def test_goec_skips_rows_without_coordinates() -> None:
    rows = [{"label": "NO COORDS", "power": "60"}, *_GOEC_ROWS]
    stations = parse_goec_stations(rows)
    assert all(s.name != "NO COORDS" for s in stations)
    assert len(stations) == 2


# --- Zeon --------------------------------------------------------------------

_ZEON_REC = {
    "id": 42,
    "station_name": "Zeon Krishnagiri",
    "address": {"city": "Polupalli", "state": "Tamil Nadu", "zipCode": "635115"},
    "latitude": 12.582,
    "longitude": 78.157,
    "accessibility_type": "public",
    "connector_data": [
        {"peak_power": "50", "current_type": "DC", "connector_type": "CCS2", "connector_count": 1},
        {"peak_power": "60", "current_type": "DC", "connector_type": "CCS2", "connector_count": 2},
    ],
}


def test_zeon_maps_id_town_and_access() -> None:
    s = parse_zeon_station(_ZEON_REC)
    assert s is not None
    assert s.source == "zeon"
    assert s.source_id == "42"
    assert s.operator == "Zeon"
    assert s.town == "Polupalli"
    assert s.postcode == "635115"
    assert s.access == "public"


def test_zeon_counts_connectors_and_peak_power() -> None:
    s = parse_zeon_station(_ZEON_REC)
    assert s is not None
    assert s.number_of_points == 3  # 1 + 2 connector_count
    assert s.max_power_kw == 60.0
    assert len(s.connectors) == 2


def test_zeon_rejects_a_record_missing_coordinates() -> None:
    assert parse_zeon_station({"id": 1, "station_name": "no coords"}) is None
    assert parse_zeon_station("not a dict") is None
