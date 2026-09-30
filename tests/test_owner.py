"""Station-owner upload: the pure forecast, and the submission endpoint.

The endpoint runs against a stub session: ``competitor_stations`` carries a
PostGIS column that SQLite cannot create, and the handler only needs ``get``,
``add``, ``add_all`` and ``flush``.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.internal import owner
from app.db import get_session
from app.domain.owner import (
    MODEL_VERSION,
    expand_connectors,
    forecast,
    peer_median_kwh,
    valid_readings,
)
from app.models.charging import Station

INSTALL = 2025 * 12  # Jan 2025


def _m(year: int, month: int) -> int:
    return year * 12 + month - 1


def test_expand_connectors_flattens_quantity_and_drops_unpowered() -> None:
    rows = [
        {"type": "CCS", "power_kw": 60, "quantity": 2},
        {"type": "?", "power_kw": None, "quantity": 1},
        {"type": "Type2", "power_kw": 7.4},
    ]
    assert expand_connectors(rows) == [60.0, 60.0, 7.4]
    assert expand_connectors(None) == []


def test_peer_median_grows_with_age_and_power() -> None:
    assert peer_median_kwh([60], 1) < peer_median_kwh([60], 12) < peer_median_kwh([60], 60)
    assert peer_median_kwh([60], 6) > peer_median_kwh([7.4], 6)
    assert peer_median_kwh([7.4, 7.4], 6) == pytest.approx(2 * peer_median_kwh([7.4], 6))


def test_valid_readings_drops_impossible_and_pre_install() -> None:
    kw = [7.4]  # ceiling 7.4 * 744 = 5505.6
    got = valid_readings(
        {INSTALL - 1: 100, INSTALL: 100, INSTALL + 1: 0, INSTALL + 2: -5, INSTALL + 3: 6000},
        INSTALL,
        kw,
    )
    assert got == [(INSTALL, 100.0)]


def test_forecast_none_without_usable_readings() -> None:
    assert forecast([7.4], INSTALL, {}) is None
    assert forecast([7.4], INSTALL, {INSTALL: 0}) is None
    assert forecast([], INSTALL, {INSTALL: 100}) is None


def test_forecast_on_the_peer_line_gives_percentile_50() -> None:
    kw = [60.0]
    readings = {INSTALL + i: peer_median_kwh(kw, i) for i in range(6)}
    f = forecast(kw, INSTALL, readings)
    assert f is not None
    assert f.model_version == MODEL_VERSION
    assert f.relative_to_peers == pytest.approx(1.0)
    assert f.peer_percentile == pytest.approx(50.0, abs=0.1)
    assert f.next_month == INSTALL + 6
    assert f.band.p50 == pytest.approx(peer_median_kwh(kw, 6))


def test_forecast_band_is_ordered_and_narrows_with_evidence() -> None:
    kw = [60.0]
    one = forecast(kw, INSTALL, {INSTALL: 800.0})
    six = forecast(kw, INSTALL, {INSTALL + i: 800.0 for i in range(6)})
    assert one is not None and six is not None
    for f in (one, six):
        assert f.band.p10 < f.band.p50 < f.band.p90
        assert f.peer_band.p10 < f.peer_band.p50 < f.peer_band.p90
    width = lambda f: math.log(f.band.p90 / f.band.p10)  # noqa: E731
    assert width(six) < width(one)


def test_forecast_busy_station_ranks_above_peers() -> None:
    kw = [60.0]
    f = forecast(kw, INSTALL, {INSTALL + i: 2 * peer_median_kwh(kw, i) for i in range(4)})
    assert f is not None
    assert f.relative_to_peers == pytest.approx(2.0)
    assert f.peer_percentile > 90


# --- endpoint ---------------------------------------------------------------


class _Rows:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class StubSession:
    """Answers the two queries the handlers make, by what the statement selects."""

    def __init__(self, station: Any, connectors: list[Any]) -> None:
        self.station = station
        self.connectors = connectors  # (station id, connector id, standard, kW)
        self.added: list[Any] = []

    def get(self, _model: Any, key: int) -> Any:
        return self.station if self.station is not None and self.station.id == key else None

    def execute(self, stmt: Any) -> _Rows:
        if stmt.column_descriptions[0]["entity"] is Station:
            return _Rows([(self.station, "Zeon")] if self.station is not None else [])
        return _Rows(self.connectors)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def add_all(self, objs: Any) -> None:
        self.added.extend(objs)

    def flush(self) -> None:
        return None


def _station() -> Any:
    return SimpleNamespace(
        id=7,
        name="Casino Hotel",
        operator_raw="Zeon Charging",
        town="Kochi",
        lat=9.96,
        lng=76.27,
        merged_into_id=None,
    )


CONNECTORS = [(7, 11, "CCS2", 60.0), (7, 12, "CCS2", 60.0), (7, 13, "Type2", 7.4)]


@pytest.fixture
def stub() -> StubSession:
    return StubSession(_station(), list(CONNECTORS))


@pytest.fixture
def client(stub: StubSession) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(owner.router, prefix="/api/internal")
    app.dependency_overrides[get_session] = lambda: stub
    with TestClient(app) as c:
        yield c


def _body(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "station_id": 7,
        "connector_ids": [11, 12],
        "install_month": "2025-01",
        "meter_type": "separate",
        "readings": [{"month": "2025-06", "kwh": 3000}, {"month": "2025-07", "kwh": 3400}],
        "consent_aggregate": True,
    }
    body.update(over)
    return body


def test_submit_stores_and_returns_band(client: TestClient, stub: StubSession) -> None:
    r = client.post("/api/internal/owner/submissions", json=_body())
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["model_version"] == MODEL_VERSION
    assert out["next_month"] == "2025-08"
    assert out["readings_used"] == 2 and out["readings_ignored"] == 0
    f = out["forecast"]
    assert f["p10_kwh"] < f["p50_kwh"] < f["p90_kwh"]
    kinds = [type(o).__name__ for o in stub.added]
    assert kinds == ["OwnerSubmission", "OwnerReading", "OwnerReading"]
    assert stub.added[0].forecast["model_version"] == MODEL_VERSION
    assert stub.added[0].install_month.isoformat() == "2025-01-01"
    # Real ids, not positions; the legacy pair stays empty.
    assert stub.added[0].station_id == 7 and stub.added[0].connector_ids == [11, 12]
    assert stub.added[0].competitor_station_id is None


def test_submit_counts_ignored_readings(client: TestClient) -> None:
    body = _body(readings=[{"month": "2024-11", "kwh": 500}, {"month": "2025-06", "kwh": 3000}])
    out = client.post("/api/internal/owner/submissions", json=body).json()
    assert out["readings_used"] == 1 and out["readings_ignored"] == 1


@pytest.mark.parametrize(
    ("over", "code"),
    [
        ({"consent_aggregate": False}, 422),
        ({"station_id": 999}, 404),
        ({"connector_ids": [999]}, 422),  # not a connector of this station
        ({"connector_ids": [11, 999]}, 422),
        ({"connector_ids": [0]}, 422),
        ({"connector_ids": [-1]}, 422),
        ({"install_month": "2025-13"}, 422),
        ({"meter_type": "maybe"}, 422),
        ({"readings": []}, 422),
        ({"readings": [{"month": "2025-06", "kwh": -1}]}, 422),
        ({"readings": [{"month": "2024-01", "kwh": 100}]}, 422),  # all before install
        ({"readings": [{"month": "2025-06", "kwh": 900000}]}, 422),  # above ceiling
    ],
)
def test_submit_rejects_bad_input(
    client: TestClient, stub: StubSession, over: Any, code: int
) -> None:
    r = client.post("/api/internal/owner/submissions", json=_body(**over))
    assert r.status_code == code
    assert stub.added == []


def test_submit_station_without_powered_connectors(client: TestClient, stub: StubSession) -> None:
    stub.connectors = []
    assert client.post("/api/internal/owner/submissions", json=_body()).status_code == 422


def test_submit_merged_station_is_unknown(client: TestClient, stub: StubSession) -> None:
    stub.station.merged_into_id = 3
    assert client.post("/api/internal/owner/submissions", json=_body()).status_code == 404


def test_the_old_position_field_is_no_longer_accepted(client: TestClient) -> None:
    body = _body()
    body.pop("connector_ids")
    body["connector_indices"] = [0, 1]
    assert client.post("/api/internal/owner/submissions", json=body).status_code == 422


def test_search_returns_powered_connectors_with_ids(client: TestClient) -> None:
    r = client.get("/api/internal/owner/stations", params={"q": "casino"})
    assert r.status_code == 200, r.text
    (st,) = r.json()["stations"]
    assert st["id"] == 7 and st["operator"] == "Zeon" and st["town"] == "Kochi"
    assert [(c["id"], c["standard"], c["power_kw"]) for c in st["connectors"]] == [
        (11, "CCS2", 60.0),
        (12, "CCS2", 60.0),
        (13, "Type2", 7.4),
    ]
