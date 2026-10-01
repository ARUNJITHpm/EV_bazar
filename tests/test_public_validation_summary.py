"""Public summary export never copies private observations or demo metrics."""

import pytest

from scripts.prepare_analytics_validation import VERSION_KEYS, prepare


def report():
    return {
        "is_demo": False,
        "phase": "complete",
        "unit": "kwh_per_connector_day",
        "overall": {
            "median_absolute_percentage_error": 0.4,
            "interval_coverage": 0.8,
            "stations": 30,
        },
        "selected_features": ["log_age"],
        "simulation_count": 1000,
        "publication_validation_passed": True,
        "loo": [{"station_id": "private-test-id", "actual": 999}],
        "run_id": "private-test-run",
        **dict.fromkeys(VERSION_KEYS, "test-version"),
    }


def test_exports_only_summary_fields():
    output = prepare(report(), "2026-10-01")
    assert output["stations"] == 30
    assert output["median_absolute_percentage_error"] == 0.4
    assert output["interval_coverage"] == 0.8
    assert output["versions"] == dict.fromkeys(VERSION_KEYS, "test-version")
    assert "private-test" not in str(output)
    assert "loo" not in output
    assert "run_id" not in output


@pytest.mark.parametrize(
    "patch",
    [
        {"is_demo": True},
        {"is_demo": None},
        {"phase": "refused"},
        {"unit": "monthly_kwh"},
        {"overall": {"stations": 9}},
        {"model_version": ""},
        {"simulation_count": 999},
        {"selected_features": ["station_id"]},
        {"publication_validation_passed": None},
    ],
)
def test_refuses_unpublishable_reports(patch):
    with pytest.raises(ValueError):
        prepare({**report(), **patch}, "2026-10-01")


def test_refuses_invalid_calendar_date():
    with pytest.raises(ValueError):
        prepare(report(), "2026-02-30")
