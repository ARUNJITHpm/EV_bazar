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


class StubSession:
    def __init__(self, station: Any) -> None:
        self.station = station
        self.added: list[Any] = []

    def get(self, _model: Any, key: int) -> Any:
        return self.station if self.station is not None and self.station.id == key else None

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def add_all(self, objs: Any) -> None:
        self.added.extend(objs)

    def flush(self) -> None:
        return None


def _station() -> Any:
    return SimpleNamespace(
        id=7, connectors=[{"type": "CCS", "power_kw": 60, "quantity": 2}, {"power_kw": 7.4}]
    )


@pytest.fixture
def stub() -> StubSession:
    return StubSession(_station())


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
        "connector_indices": [0, 1],
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


def test_submit_counts_ignored_readings(client: TestClient) -> None:
    body = _body(readings=[{"month": "2024-11", "kwh": 500}, {"month": "2025-06", "kwh": 3000}])
    out = client.post("/api/internal/owner/submissions", json=body).json()
    assert out["readings_used"] == 1 and out["readings_ignored"] == 1


@pytest.mark.parametrize(
    ("over", "code"),
    [
        ({"consent_aggregate": False}, 422),
        ({"station_id": 999}, 404),
        ({"connector_indices": [5]}, 422),
        ({"connector_indices": [-1]}, 422),
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
    stub.station.connectors = [{"type": "?", "power_kw": None}]
    assert client.post("/api/internal/owner/submissions", json=_body()).status_code == 422
