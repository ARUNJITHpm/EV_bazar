"""Owner forecast: the pure peer-blend module and its Forecaster seam."""

from __future__ import annotations

import math

import pytest

from app.domain.owner import (
    DEFAULT_FORECASTER,
    MODEL_VERSION,
    PeerBlendForecaster,
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


def test_forecaster_seam_matches_the_function_and_names_its_version() -> None:
    kw = [60.0]
    readings = {INSTALL + i: 900.0 for i in range(3)}
    assert isinstance(DEFAULT_FORECASTER, PeerBlendForecaster)
    assert DEFAULT_FORECASTER.model_version == MODEL_VERSION
    assert DEFAULT_FORECASTER(kw, INSTALL, readings) == forecast(kw, INSTALL, readings)


def test_more_months_of_own_history_pull_the_forecast_toward_it() -> None:
    kw = [60.0]
    one = forecast(kw, INSTALL, {INSTALL: 3 * peer_median_kwh(kw, 0)})
    six = forecast(kw, INSTALL, {INSTALL + i: 3 * peer_median_kwh(kw, i) for i in range(6)})
    assert one is not None and six is not None
    # 3x the peer line: six months of evidence trusts that more than one month does.
    assert six.band.p50 / peer_median_kwh(kw, six.age_months) > (
        one.band.p50 / peer_median_kwh(kw, one.age_months)
    )


def test_model_band_is_ordered_and_grows_with_age() -> None:
    from app.domain.owner.forecast import model_band

    young, old = model_band([60.0], 1), model_band([60.0], 24)
    assert young.p10 < young.p50 < young.p90
    assert old.p50 > young.p50
