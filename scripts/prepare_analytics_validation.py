"""Prepare an approved public aggregate summary from a private real run report."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path

VERSION_KEYS = (
    "model_version",
    "economics_version",
    "schema_version",
    "archetype_version",
    "tariff_effective_date",
    "renderer_version",
)
FEATURES = {
    "dc_share",
    "power_class",
    "log_age",
    "highway",
    "urban",
    "rural",
    "log_distance",
    "log_ev",
}


def prepare(report: dict[str, object], completed_on: str) -> dict[str, object]:
    if not isinstance(report, dict):
        raise ValueError("Run report must be an object")
    if dt.date.fromisoformat(completed_on).isoformat() != completed_on:
        raise ValueError("A calendar completion date is required")
    if report.get("is_demo") is not False or report.get("phase") != "complete":
        raise ValueError("Only a completed non-demo run may be reviewed for publication")
    if report.get("unit") != "kwh_per_connector_day":
        raise ValueError("Validation must use kwh_per_connector_day")
    overall = report.get("overall")
    if not isinstance(overall, dict):
        raise ValueError("Missing LOO summary")
    error, coverage, stations = (
        overall.get(key)
        for key in ("median_absolute_percentage_error", "interval_coverage", "stations")
    )
    if any(
        type(value) not in (int, float) or not math.isfinite(value) for value in (error, coverage)
    ):
        raise ValueError("Finite LOO metrics are required")
    if error < 0 or not 0 <= coverage <= 1 or type(stations) is not int or stations < 10:
        raise ValueError("Invalid metrics or fewer than ten eligible held-out stations")
    features = report.get("selected_features")
    if not isinstance(features, list) or any(value not in FEATURES for value in features):
        raise ValueError("Unsupported feature selection")
    simulations = report.get("simulation_count")
    if type(simulations) is not int or simulations < 1000:
        raise ValueError("At least 1000 simulations are required")
    passed = report.get("publication_validation_passed")
    if type(passed) is not bool or any(
        not isinstance(report.get(key), str) or not report[key] for key in VERSION_KEYS
    ):
        raise ValueError("Validation outcome and six version stamps are required")
    return {
        "approved": True,
        "is_demo": False,
        "completed_on": completed_on,
        "unit": "kwh_per_connector_day",
        "median_absolute_percentage_error": error,
        "interval_coverage": coverage,
        "stations": stations,
        "selected_features": features,
        "simulation_count": simulations,
        "publication_validation_passed": passed,
        "versions": {key: report[key] for key in VERSION_KEYS},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--completed-on", required=True)
    parser.add_argument(
        "--approved", action="store_true", help="Confirm operator review of a real run"
    )
    args = parser.parse_args()
    if not args.approved:
        parser.error("Operator review is required (--approved)")
    try:
        summary = prepare(json.loads(args.report.read_text(encoding="utf-8")), args.completed_on)
    except (ValueError, TypeError, KeyError) as error:
        parser.error(str(error))
    output = (
        Path(__file__).resolve().parents[1] / "frontend/content/analytics/validation-summary.json"
    )
    output.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("Prepared reviewed aggregate summary; private report was not copied.")


if __name__ == "__main__":
    main()
