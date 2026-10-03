from __future__ import annotations

import datetime as dt
import importlib.util
import json
import uuid
from pathlib import Path

import numpy as np
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.domain.analytics.inputs import Bill, Station, latest_bills
from app.domain.analytics.ledger import PredictionLedger
from app.domain.analytics.publication import PUBLIC_FIELDS, aggregate
from app.domain.analytics.runner import out_of_sample, run_private
from app.domain.demand.owner_mixed import OwnerMixedModel
from app.models.predictions import Prediction

MONTH = dt.date(2026, 8, 1)
NOW = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)


def station(index: int, **changes) -> Station:
    return Station(
        public_id=f"test-public-{index}",
        site_id=uuid.UUID(int=index),
        owner_station_id=index,
        lgd_code=1,
        state="Test State",
        connectors_ac=1,
        connectors_dc=0,
        mean_power_kw=7,
        opened_month=dt.date(2024, 1, 1),
        road_class="urban",
        highway_distance_km=5,
        ev_registrations=2000,
        consent=True,
        meter_type="separate",
        reviewed=True,
        **changes,
    )


def bill(index: int, kwh=100) -> Bill:
    return Bill(
        station_id=index,
        month=MONTH,
        kwh=kwh,
        confirmed_at=NOW,
        confirmed=True,
        full_calendar_month_verified=True,
        correction_id=index,
    )


@pytest.fixture
def ledger():
    engine = create_engine("sqlite://")
    spec = importlib.util.spec_from_file_location(
        "analytics_fixture", Path(__file__).parent / "migrations/analytics_fixture.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        module.upgrade()
    with Session(engine) as session:
        yield PredictionLedger(session, uuid.uuid4(), is_demo=True)


def test_nine_stations_disclose_no_counts_or_values():
    stations = [station(index) for index in range(1, 10)]
    result = aggregate(
        stations,
        {row.public_id: bill(row.owner_station_id) for row in stations},
        {},
        MONTH,
        validation_passed=True,
    )
    assert set(result) == set(PUBLIC_FIELDS)
    assert result["note"] == "Not enough data yet"
    assert all(result[key] is None for key in PUBLIC_FIELDS[2:-1])


@pytest.mark.parametrize("failure", ["dominance", "consent", "meter", "validation", "exposure"])
def test_publication_refuses_privacy_and_validation_failures(failure):
    stations = [station(index) for index in range(1, 11)]
    observed = {
        row.public_id: bill(
            row.owner_station_id,
            10000 if failure == "dominance" and row.owner_station_id == 1 else 100,
        )
        for row in stations
    }
    if failure in {"consent", "meter"}:
        stations[0] = stations[0].model_copy(
            update={"consent": False} if failure == "consent" else {"meter_type": "shared"}
        )
    if failure == "exposure":
        observed[stations[0].public_id] = observed[stations[0].public_id].model_copy(
            update={"full_calendar_month_verified": False}
        )
    result = aggregate(stations, observed, {}, MONTH, validation_passed=failure != "validation")
    assert result["district_total_p50"] is None


def test_publication_allowlist_and_type_coverage():
    stations = [station(index) for index in range(1, 12)]
    observed = {row.public_id: bill(row.owner_station_id) for row in stations[:10]}
    draws = {stations[-1].public_id: np.full(1000, 100)}
    result = aggregate(stations, observed, draws, MONTH, validation_passed=True)
    assert result["district_total_p50"] == 1100
    assert result["kwh_per_charger_p50"] == 100
    assert not any(
        key in json.dumps(result)
        for key in ["test-public-", "owner_station_id", "site_id", "phone", "individual_kwh"]
    )
    stations[-1] = stations[-1].model_copy(update={"connectors_ac": 0, "connectors_dc": 50})
    assert (
        aggregate(stations, observed, draws, MONTH, validation_passed=True)["district_total_p50"]
        is None
    )


def test_latest_invalid_correction_does_not_resurrect_old_exposure():
    old = bill(1)
    corrected = old.model_copy(update={"correction_id": 2, "full_calendar_month_verified": False})
    assert latest_bills([station(1)], [old, corrected]) == {}


def test_ledger_persists_test_band_before_use(ledger):
    prediction_id = ledger.record(station(1), MONTH, np.arange(1000, dtype=float), "forecast")
    row = ledger.session.get(Prediction, prediction_id)
    assert row.actual_kwh is None and row.is_demo
    assert row.analytics_context["unit"] == "kwh_per_connector_day"
    assert row.analytics_context["schema_version"] == "usage_aggregate_v1"


def test_fit_refusal_produces_private_report_without_fake_output(ledger, tmp_path):
    report = tmp_path / "private_validation.json"
    with pytest.raises(ValueError, match="30 distinct"):
        run_private(
            [station(index) for index in range(1, 10)],
            [bill(index) for index in range(1, 10)],
            MONTH,
            ledger,
            report,
        )
    assert json.loads(report.read_text())["phase"] == "refused"
    assert list(ledger.session.scalars(select(Prediction))) == []


def synthetic_sample():
    rng = np.random.default_rng(7)
    stations = []
    bills = []
    for index in range(1, 61):
        row = station(index).model_copy(
            update={
                "state": f"Test State {index % 3}",
                "lgd_code": index % 6 + 1,
                "connectors_ac": 1,
                "connectors_dc": int(rng.integers(0, 3)),
                "mean_power_kw": float(rng.choice([7, 22, 120])),
                "opened_month": dt.date(2023 + index % 3, index % 12 + 1, 1),
                "road_class": str(
                    rng.choice(["national_highway", "urban", "rural", "state_highway"])
                ),
                "highway_distance_km": float(rng.uniform(0, 20)),
                "ev_registrations": int(rng.integers(100, 20000)),
            }
        )
        stations.append(row)
        bills.append(
            bill(
                index,
                float(np.exp(rng.normal(3 + index % 3 * 0.3 + index % 6 * 0.1, 0.7)))
                * 31
                * row.connectors,
            )
        )
    return stations, bills


def test_hierarchical_model_outputs_only_persisted_connector_day_ranges(ledger):
    stations, bills = synthetic_sample()
    model = OwnerMixedModel(stations, bills, seed=5)
    draws = model.predict(stations[0], MONTH, ledger, "forecast")
    row = ledger.session.scalar(select(Prediction))
    assert len(draws) == 1000 and row is not None
    assert 0 <= row.predicted_p10 <= row.predicted_p50 <= row.predicted_p90
    assert row.actual_kwh is None and row.is_demo
    unknown = stations[0].model_copy(update={"opened_month": None})
    draws_unknown = model.predict(unknown, MONTH, ledger, "forecast")
    assert len(draws_unknown) == 1000
    assert len(list(ledger.session.scalars(select(Prediction)))) == 2


def test_out_of_sample_uses_only_predictions_before_first_upload(ledger):
    source = station(1)
    for date in [dt.datetime(2026, 7, 1, tzinfo=dt.UTC), dt.datetime(2026, 9, 15, tzinfo=dt.UTC)]:
        ledger.session.add(
            Prediction(
                site_id=source.site_id,
                model_version="owner_mixed_v1",
                economics_version="not_applicable",
                predicted_p10=1,
                predicted_p50=2,
                predicted_p90=4,
                is_demo=True,
                actual_kwh=None,
                predicted_at=date,
                analytics_context={"phase": "forecast", "month": MONTH.isoformat()},
            )
        )
    ledger.session.commit()
    rows = out_of_sample([source], [bill(1)], ledger)
    assert len(rows) == 1 and rows[0]["prediction_id"] == 1
    assert ledger.session.get(Prediction, 1).actual_kwh is None


def test_full_leave_one_station_out_report_is_private_and_logged(ledger, tmp_path):
    stations, bills = synthetic_sample()
    report = tmp_path / "private_loo.json"
    output = run_private(stations, bills, MONTH, ledger, report, seed=2)
    data = json.loads(report.read_text())
    assert data["phase"] == "complete" and len(data["loo"]) == 60
    predictions = list(ledger.session.scalars(select(Prediction)))
    assert len(predictions) == 60 and all(
        row.actual_kwh is None and row.is_demo for row in predictions
    )
    assert all(set(row) == set(PUBLIC_FIELDS) for row in output)
