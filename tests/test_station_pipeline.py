import datetime as dt
import json

import httpx
import pytest

from app.domain.context.competitors import CompetitorStationData
from app.domain.context.station_pipeline import (
    CaptureClient,
    collect_source,
    coverage_gaps,
    export_rows,
    fetch_ncr_boundary,
    locate_stations,
    parse_osm_stations,
    persist_inventory_rows,
    read_station_csv,
)
from scripts.refresh_stations import fetch_ocm_states


def station(**kwargs):
    return CompetitorStationData(
        source="test", source_id="1", lat=9.93, lng=76.26, operator="Zeon Charging", **kwargs
    )


def test_cap_refuses_traffic_and_archives_before_use(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=[{"id": 1}])

    with CaptureClient(
        tmp_path / "raw", max_requests=1, delay_seconds=0, transport=httpx.MockTransport(handler)
    ) as client:
        response = client.get("https://example.org/stations?key=SECRET")
        assert (tmp_path / "raw/0001.body").exists()
        assert response.json() == [{"id": 1}]
        with pytest.raises(RuntimeError, match="budget"):
            client.get("https://example.org/stations")
    assert len(calls) == 1
    metadata = (tmp_path / "raw/0001.json").read_text()
    assert "SECRET" not in metadata
    assert json.loads(metadata)["sha256"]


def test_http_error_is_archived(tmp_path):
    with CaptureClient(
        tmp_path / "raw",
        delay_seconds=0,
        transport=httpx.MockTransport(lambda r: httpx.Response(503)),
    ) as client:
        response = client.get("https://example.org/stations")
        with pytest.raises(httpx.HTTPStatusError):
            response.raise_for_status()
    assert json.loads((tmp_path / "raw/0001.json").read_text())["status"] == 503


def test_transport_failure_keeps_attempt_record(tmp_path):
    def handler(request):
        raise httpx.ConnectError("unavailable", request=request)

    with (
        CaptureClient(tmp_path / "raw", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(httpx.ConnectError),
    ):
        client.get("https://example.org/")
    assert json.loads((tmp_path / "raw/0001.json").read_text())["outcome"] == "no_response"


def test_source_failure_isolated_and_secret_not_in_outcomes():
    outcomes = {}

    def fail():
        raise httpx.ConnectError("https://example.org/?key=SECRET")

    assert collect_source("broken", fail, outcomes) == []
    assert collect_source("good", lambda: [station()], outcomes) == [station()]
    assert "SECRET" not in json.dumps(outcomes)


def test_rejects_nonfinite_csv_and_requires_timestamp_timezone(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("source_id,latitude,longitude,operator\n1,nan,76,Zeon\n")
    with pytest.raises(ValueError, match="latitude"):
        read_station_csv(path, source="zeon")
    path.write_text(
        "source_id,latitude,longitude,operator,source_last_status_update\n"
        "1,9.9,76,Zeon,2026-01-01T00:00:00\n"
    )
    with pytest.raises(ValueError, match="timezone"):
        read_station_csv(path, source="zeon")


def test_spatial_ambiguity_does_not_pick_first_district():
    class Session:
        def execute(self, *args):
            return [
                (1, 555, 32, "Ernakulam", "Kerala", "2025"),
                (1, 556, 32, "Thrissur", "Kerala", "2025"),
            ]

    rows = locate_stations(Session(), [station(), station()])
    assert rows[0]["resolution"] == "ambiguous"
    assert rows[0]["district"] is None
    assert rows[1]["resolution"] == "unplaced"


def test_filters_by_resolved_state_and_keeps_unknowns_for_review():
    locations = [
        {"state": "Kerala", "resolution": "contained"},
        {"state": "Karnataka", "resolution": "contained"},
        {"state": None, "resolution": "unplaced"},
    ]
    rows, accepted = export_rows(
        [station()] * 3,
        locations,
        states=["kerala"],
        fetched_at=dt.datetime(2026, 9, 30, tzinfo=dt.UTC),
    )
    assert len(rows) == 2
    assert len(accepted) == 1
    assert rows[0]["canonical_operator"] == "Zeon"
    assert rows[0]["freshness"] == "unknown"
    assert rows[1]["in_selected_states"] is None


def test_new_fetch_does_not_make_old_source_fresh():
    rows, _ = export_rows(
        [station(source_last_status_update=dt.datetime(2025, 1, 1, tzinfo=dt.UTC))],
        [{"state": "Kerala", "resolution": "contained"}],
        states=["kerala"],
        fetched_at=dt.datetime(2026, 9, 30, tzinfo=dt.UTC),
    )
    assert rows[0]["freshness"] == "stale"
    gaps = coverage_gaps(rows, ["kerala"])
    assert next(g for g in gaps if g["operator"] == "Zeon")["source_rows"] == 1
    assert next(g for g in gaps if g["operator"] == "chargeMOD")["source_rows"] == 0


def test_ocm_cap_refuses_entire_source_without_losing_raw(tmp_path):
    with CaptureClient(
        tmp_path / "raw",
        delay_seconds=0,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[{}] * 500)),
    ) as client:
        outcomes = {}
        result = collect_source(
            "ocm",
            lambda: fetch_ocm_states(
                client,
                "secret",
                "https://example.org",
                ["kerala"],
                1,
            ),
            outcomes,
        )
    assert result == []
    assert outcomes["ocm"]["status"] == "failed"
    assert len(json.loads((tmp_path / "raw/0001.body").read_text())) == 500


def test_osm_missing_metadata_is_unknown_and_edit_date_not_verification():
    stations = parse_osm_stations(
        {
            "elements": [
                {
                    "type": "way",
                    "id": 123,
                    "center": {"lat": 9.9, "lon": 76.2},
                    "timestamp": "2026-09-30T00:00:00Z",
                    "tags": {"amenity": "charging_station"},
                }
            ]
        }
    )
    assert len(stations) == 1
    assert stations[0].source_id == "way/123"
    assert stations[0].operator is None
    assert stations[0].access is None
    assert stations[0].is_operational is None
    assert stations[0].source_last_status_update is None
    with pytest.raises(ValueError, match="partial"):
        parse_osm_stations({"elements": [], "remark": "runtime error: timeout"})


def test_ncr_boundary_required_and_filters_by_polygon_not_whole_state():
    from shapely.geometry import box

    ncr = box(76, 28, 78, 30)
    points = [
        CompetitorStationData(source="test", source_id="1", lat=28.5, lng=77),
        CompetitorStationData(source="test", source_id="2", lat=27, lng=77),
    ]
    locations = [{"state": "Haryana", "resolution": "contained"}] * 2
    now = dt.datetime(2026, 9, 30, tzinfo=dt.UTC)
    with pytest.raises(ValueError, match="boundary"):
        export_rows(points, locations, states=["delhincr"], fetched_at=now)
    rows, accepted = export_rows(
        points, locations, states=["delhincr"], fetched_at=now, ncr_boundary=ncr
    )
    assert len(accepted) == 1
    assert rows[0]["state"] == "Haryana"
    assert rows[0]["target_region"] == "delhi-ncr"


def test_incomplete_official_ncr_boundary_is_refused():
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"features": []}))
        ) as client,
        pytest.raises(ValueError, match="four"),
    ):
        fetch_ncr_boundary(client)


def test_bulk_cache_write_excludes_unplaced_and_uses_no_geom_assignment():
    class Session:
        def __init__(self):
            self.statements = []

        def execute(self, statement):
            self.statements.append(statement)

    rows, _ = export_rows(
        [station(), station()],
        [
            {
                "state": "Kerala",
                "resolution": "contained",
                "lgd_state_code": 32,
                "lgd_district_code": 555,
            },
            {"state": None, "resolution": "unplaced"},
        ],
        states=["kerala"],
        fetched_at=dt.datetime(2026, 9, 30, tzinfo=dt.UTC),
    )
    session = Session()
    assert persist_inventory_rows(session, rows) == 1
    statement = session.statements[0]
    assert "ON CONFLICT" in str(statement)
    assert "geom" not in statement.compile().params
