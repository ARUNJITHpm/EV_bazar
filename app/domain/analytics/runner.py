"""Station-level LOO, predictive simulation and immutable private validation."""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sqlalchemy import select

from app.domain.analytics.inputs import (
    VERSIONS,
    Bill,
    Station,
    check_inventory,
    connector_days,
    latest_bills,
)
from app.domain.analytics.ledger import PredictionLedger
from app.domain.analytics.publication import aggregate
from app.domain.demand.owner_mixed import OwnerMixedModel
from app.models.predictions import Prediction


def out_of_sample(
    stations: list[Station], bills: list[Bill], ledger: PredictionLedger
) -> list[dict[str, object]]:
    latest = latest_bills(stations, bills)
    first = {
        owner: min(
            bill.confirmed_at for bill in bills if bill.station_id == owner and bill.confirmed
        )
        for owner in {bill.station_id for bill in bills if bill.confirmed}
    }
    by_site = {station.site_id: station for station in stations}
    records = []
    seen = set()
    for prediction in ledger.session.scalars(
        select(Prediction)
        .where(Prediction.site_id.in_(by_site))
        .order_by(Prediction.predicted_at.desc(), Prediction.id.desc())
    ):
        context = prediction.analytics_context or {}
        if prediction.is_demo != ledger.is_demo or context.get("phase") != "forecast":
            continue
        station = by_site[prediction.site_id]
        month = dt.date.fromisoformat(str(context["month"]))
        key = (station.owner_station_id, month)
        timestamp = prediction.predicted_at
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=dt.UTC)  # SQLite fixture timestamps are UTC.
        if key in seen or key not in latest or timestamp >= first[station.owner_station_id]:
            continue
        observed = latest[key].kwh / connector_days(station, month)
        records.append(
            {
                "prediction_id": prediction.id,
                "station_id": station.owner_station_id,
                "month": month.isoformat(),
                "actual": observed,
                "p10": prediction.predicted_p10,
                "p50": prediction.predicted_p50,
                "p90": prediction.predicted_p90,
            }
        )
        seen.add(key)
    return records


def metrics(records: list[dict[str, object]]) -> dict[str, object]:
    errors = [
        abs(float(row["p50"]) - float(row["actual"])) / float(row["actual"])
        for row in records
        if float(row["actual"]) > 0
    ]
    covered = [float(row["p10"]) <= float(row["actual"]) <= float(row["p90"]) for row in records]
    return {
        "median_absolute_percentage_error": float(np.median(errors)) if errors else None,
        "interval_coverage": float(np.mean(covered)) if covered else None,
        "stations": len({row["station_id"] for row in records}),
        "zero_actual_readings": sum(float(row["actual"]) == 0 for row in records),
    }


def run_private(
    stations: list[Station],
    bills: list[Bill],
    month: dt.date,
    ledger: PredictionLedger,
    report_path: Path,
    *,
    seed: int = 0,
) -> list[dict[str, object]]:
    check_inventory(stations)
    if report_path.exists():
        raise ValueError("Private validation reports are immutable")
    approved = latest_bills(stations, bills)
    # Confirmed corrections only, no future observations in a retrospective fit.
    training = [bill for bill in approved.values() if bill.month <= month]
    by_owner = {station.owner_station_id: station for station in stations}
    usable = [bill for bill in training if by_owner[bill.station_id].opened_month is not None]
    loo = []
    oos = out_of_sample(stations, bills, ledger)
    try:
        for owner_id in sorted({bill.station_id for bill in usable}):
            held = [bill for bill in usable if bill.station_id == owner_id]
            model = OwnerMixedModel(
                stations,
                [bill for bill in usable if bill.station_id != owner_id],
                seed=seed + owner_id,
            )
            for bill in held:
                station = by_owner[owner_id]
                draws = model.predict(station, bill.month, ledger, "loo")
                p10, p50, p90 = np.quantile(draws, [0.1, 0.5, 0.9])
                loo.append(
                    {
                        "station_id": owner_id,
                        "month": bill.month.isoformat(),
                        "type": "mixed"
                        if station.connectors_ac and station.connectors_dc
                        else "DC"
                        if station.connectors_dc
                        else "AC",
                        "actual": bill.kwh / connector_days(station, bill.month),
                        "p10": float(p10),
                        "p50": float(p50),
                        "p90": float(p90),
                    }
                )
        overall = metrics(loo)
        by_type = {
            kind: metrics([row for row in loo if row["type"] == kind])
            for kind in {row["type"] for row in loo}
        }
        passed = (
            overall["stations"] >= 30
            and overall["median_absolute_percentage_error"] is not None
            and overall["median_absolute_percentage_error"] <= 0.5
            and overall["interval_coverage"] is not None
            and 0.65 <= overall["interval_coverage"] <= 0.95
        )
        passed = passed and all(
            value["stations"] >= 5
            and value["interval_coverage"] is not None
            and 0.6 <= value["interval_coverage"] <= 0.95
            for value in by_type.values()
        )
        model = OwnerMixedModel(stations, usable, seed=seed)
        groups: dict[int, list[Station]] = defaultdict(list)
        for station in stations:
            groups[station.lgd_code].append(station)
        output = []
        for group in groups.values():
            observed = {
                station.public_id: approved[(station.owner_station_id, month)]
                for station in group
                if (station.owner_station_id, month) in approved
            }
            monthly = {}
            for station in group:
                if station.public_id not in observed:
                    monthly[station.public_id] = model.predict(
                        station, month, ledger, "forecast"
                    ) * connector_days(station, month)
            output.append(
                aggregate(group, observed, monthly, month, validation_passed=bool(passed))
            )
        report = {
            **VERSIONS,
            "run_id": str(ledger.run_id),
            "is_demo": ledger.is_demo,
            "phase": "complete",
            "unit": "kwh_per_connector_day",
            "selected_features": model.features,
            "overall": overall,
            "by_type": by_type,
            "publication_validation_passed": bool(passed),
            "loo": loo,
            "out_of_sample": oos,
            "out_of_sample_summary": metrics(oos),
            "simulation_count": model.draw_count,
            "method": "Gaussian fitted-parameter predictive simulations with conditional "
            "nested effects; variance components treated as fitted. Not a refit bootstrap.",
        }
    except Exception as error:
        report = {
            **VERSIONS,
            "run_id": str(ledger.run_id),
            "is_demo": ledger.is_demo,
            "phase": "refused",
            "error_type": type(error).__name__,
            "loo": loo,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, allow_nan=False)
        raise
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, allow_nan=False)
    return output
