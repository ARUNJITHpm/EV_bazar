"""PART 2.3 - Open Charge Map parsing and fetch. The pure parts.

The store shell (district resolution + upsert) needs PostGIS and is covered by
`scripts/fetch_competitors` against a real database, the same boundary the
sites round-trip lives on.
"""

from __future__ import annotations

import datetime as dt

import httpx

from app.domain.context import (
    CompetitorStationData,
    dedupe,
    fetch_ocm,
    map_access,
    parse_connections,
    parse_ocm_poi,
    tile_bbox,
)

# A trimmed but real-shaped OCM POI (Zeon Charging, Kochi).
POI = {
    "UUID": "0437E552-3385-4095-9554-618418C71127",
    "ID": 313444,
    "AddressInfo": {
        "Title": "Casino Hotel",
        "Latitude": 9.9673,
        "Longitude": 76.2734,
        "Town": "Kochi",
        "StateOrProvince": "Kerala",
        "Postcode": "682002",
    },
    "OperatorInfo": {"Title": "Zeon Charging", "ID": 3539},
    "UsageType": {"Title": "Public - Membership Required", "ID": 4},
    "StatusType": {"IsOperational": True, "ID": 50, "Title": "Operational"},
    "NumberOfPoints": 2,
    "DataProvider": {"Title": "Open Charge Map Contributors"},
    "DateLastStatusUpdate": "2025-06-11T14:01:00Z",
    "Connections": [
        {"ConnectionType": {"Title": "Type 2 (Tethered Connector) "}, "PowerKW": 22, "Quantity": 1},
        {"ConnectionType": {"Title": "CCS (Type 2)"}, "PowerKW": 60, "Quantity": 2},
    ],
}


def test_a_full_poi_parses_every_field() -> None:
    s = parse_ocm_poi(POI)
    assert s is not None
    assert s.source == "open_charge_map"
    assert s.source_id == "0437E552-3385-4095-9554-618418C71127"
    assert (s.lat, s.lng) == (9.9673, 76.2734)
    assert s.name == "Casino Hotel"
    assert s.operator == "Zeon Charging"
    assert s.town == "Kochi"
    assert s.access == "membership"
    assert s.is_operational is True
    assert s.number_of_points == 2
    assert s.max_power_kw == 60  # the peak across connectors
    assert s.data_provider == "Open Charge Map Contributors"


def test_the_status_update_date_is_parsed_utc() -> None:
    s = parse_ocm_poi(POI)
    assert s is not None
    assert s.source_last_status_update == dt.datetime(2025, 6, 11, 14, 1, tzinfo=dt.UTC)


def test_a_poi_with_no_coordinates_is_dropped_not_guessed() -> None:
    bad = {"UUID": "x", "AddressInfo": {"Title": "nowhere"}}
    assert parse_ocm_poi(bad) is None


def test_a_poi_with_no_stable_id_is_dropped() -> None:
    bad = {"AddressInfo": {"Latitude": 1.0, "Longitude": 2.0}}
    assert parse_ocm_poi(bad) is None


def test_id_stands_in_when_there_is_no_uuid() -> None:
    s = parse_ocm_poi({"ID": 42, "AddressInfo": {"Latitude": 1.0, "Longitude": 2.0}})
    assert s is not None
    assert s.source_id == "42"


def test_missing_operator_is_none_not_empty() -> None:
    s = parse_ocm_poi({"UUID": "x", "AddressInfo": {"Latitude": 1.0, "Longitude": 2.0}})
    assert s is not None
    assert s.operator is None
    assert s.max_power_kw is None
    assert s.connectors == ()


def test_connectors_carry_type_power_and_quantity() -> None:
    conns, peak = parse_connections(POI["Connections"])
    assert peak == 60
    assert [(c.connector_type, c.power_kw, c.quantity) for c in conns] == [
        ("Type 2 (Tethered Connector)", 22.0, 1),
        ("CCS (Type 2)", 60.0, 2),
    ]


def test_connectors_json_round_trips() -> None:
    s = parse_ocm_poi(POI)
    assert s is not None
    js = s.connectors_json()
    assert js == [
        {"type": "Type 2 (Tethered Connector)", "power_kw": 22.0, "quantity": 1},
        {"type": "CCS (Type 2)", "power_kw": 60.0, "quantity": 2},
    ]


def test_a_powerless_connection_does_not_break_peak() -> None:
    conns, peak = parse_connections([{"ConnectionType": {"Title": "Unknown"}, "PowerKW": None}])
    assert peak is None
    assert conns[0].power_kw is None
    assert conns[0].quantity == 1  # defaulted


def test_access_mapping_is_compact_and_total() -> None:
    assert map_access("Public") == "public"
    assert map_access("Public - Membership Required") == "membership"
    assert map_access("Private - Restricted Access") == "restricted"
    assert map_access(None) is None
    # An unknown public-ish label still resolves to something usable.
    assert map_access("Public - Something New") == "public"


def test_fetch_uses_a_bounding_box_and_the_key() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        seen["ua"] = request.headers.get("user-agent", "")
        return httpx.Response(200, json=[POI])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = fetch_ocm(client, "test-key", bbox=(8.1, 74.8, 12.9, 77.5), base_url="http://ocm.test")

    assert result.raw_count == 1
    assert result.parsed_count == 1
    assert seen["key"] == "test-key"
    assert seen["boundingbox"] == "(8.1,74.8),(12.9,77.5)"
    assert "EVSiteIntelligence" in seen["ua"]


def test_fetch_point_radius_form() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["latitude"] == "9.9312"
        assert request.url.params["distance"] == "5.0"
        return httpx.Response(200, json=[])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = fetch_ocm(client, "k", lat=9.9312, lng=76.2673, distance_km=5.0, base_url="http://t")
    assert result.parsed_count == 0


def test_a_non_list_body_is_empty_not_an_error() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={"error": "x"}))
    )
    assert fetch_ocm(client, "k", bbox=(1, 2, 3, 4), base_url="http://t").parsed_count == 0


# --- tiling and dedupe (pure) -----------------------------------------------


def test_tiling_covers_the_box_without_gaps_or_overlap() -> None:
    tiles = tile_bbox((8.0, 76.0, 12.0, 80.0), rows=2, cols=2)
    assert len(tiles) == 4
    # unions to the original extent
    assert min(t[0] for t in tiles) == 8.0
    assert max(t[2] for t in tiles) == 12.0
    assert min(t[1] for t in tiles) == 76.0
    assert max(t[3] for t in tiles) == 80.0
    # adjacent cells share an edge exactly (no gap, no overlap)
    assert tiles[0][2] == tiles[2][0]


def test_a_one_by_one_grid_is_the_box_itself() -> None:
    box = (8.0, 76.0, 12.0, 80.0)
    assert tile_bbox(box, rows=1, cols=1) == [box]


def test_dedupe_keeps_one_row_per_source_id() -> None:
    a = CompetitorStationData(source="open_charge_map", source_id="u1", lat=1, lng=2, name="old")
    a2 = CompetitorStationData(source="open_charge_map", source_id="u1", lat=1, lng=2, name="new")
    b = CompetitorStationData(source="open_charge_map", source_id="u2", lat=3, lng=4)
    out = dedupe([a, b, a2])
    assert len(out) == 2
    names = {s.source_id: s.name for s in out}
    assert names["u1"] == "new"  # last seen wins
