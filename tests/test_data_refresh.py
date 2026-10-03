import datetime as dt
import io
import zipfile

from app.models.data_refresh import DataRefreshEvent
from workers.data_refresh import archive_folder, due_period, next_attempt


def utc(value):
    return dt.datetime.fromisoformat(value).replace(tzinfo=dt.UTC)


def event(outcome, attempt, observed):
    return DataRefreshEvent(
        job="stations_weekly",
        period="2026-09-27",
        attempt=attempt,
        outcome=outcome,
        observed_at=utc(observed),
        payload={},
    )


def test_weekly_ist_boundary_and_missed_run_catchup():
    assert due_period("stations_weekly", utc("2026-09-26T21:29:59")) == "2026-09-20"
    assert due_period("stations_weekly", utc("2026-09-26T21:30:00")) == "2026-09-27"
    assert due_period("stations_weekly", utc("2026-09-30T15:00:00")) == "2026-09-27"


def test_monthly_rollover_before_four_am_ist():
    assert due_period("vahan_monthly", utc("2026-09-30T22:29:59")) == "2026-09"
    assert due_period("vahan_monthly", utc("2026-09-30T22:30:00")) == "2026-10"


def test_success_survives_restart_and_prevents_duplicate():
    events = [event("success", 1, "2026-09-27T01:00:00")]
    assert next_attempt(events, utc("2026-09-30T00:00:00")) is None


def test_crash_retries_after_cooldown_but_stops_at_three():
    started = event("started", 1, "2026-09-27T01:00:00")
    assert next_attempt([started], utc("2026-09-27T01:30:00")) is None
    assert next_attempt([started], utc("2026-09-27T02:00:00")) == 2
    assert (
        next_attempt([event("failed", 3, "2026-09-27T01:00:00")], utc("2026-09-30T00:00:00"))
        is None
    )


def test_zip_preserves_original_raw_bytes(tmp_path):
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw/page.body").write_bytes(b"original station response")
    (tmp_path / "manifest.json").write_bytes(b'{"status":"failed"}')
    with zipfile.ZipFile(io.BytesIO(archive_folder(tmp_path))) as archive:
        assert archive.read("raw/page.body") == b"original station response"
        assert archive.read("manifest.json") == b'{"status":"failed"}'


# --- VAHAN steps -------------------------------------------------------------

from pathlib import Path  # noqa: E402

import workers.data_refresh as refresh  # noqa: E402

YEARLY = "state_code,rto,period,fuel,vehicle_class,count\n"
MONTHLY = "state_code,rto,month,breakdown,label,fuel_scope,count\n"


def fake_runner(csvs, calls):
    """Stand-in for run_command: a scrape writes its canned CSV, ingest succeeds."""

    def run(command, *, timeout, environment, output):
        calls.append(command)
        if "scripts.scrape_vahan" in command:
            out = Path(command[command.index("--out") + 1])
            out.write_text(csvs[out.name], encoding="utf-8")
        return 0

    return run


GOOD = {
    "vahan.csv": YEARLY + "KL,ADOOR SRTO - KL26,2025,PURE EV,2WN,120\n",
    "monthly_maker.csv": MONTHLY
    + "KL,ALL,2025-01-01,maker,ATHER ENERGY LTD,ELECTRIC(BOV)+PURE EV,40\n",
    "monthly_category.csv": MONTHLY
    + "KL,ADOOR SRTO - KL26,2025-01-01,vehicle_category,MOTOR CAR,ELECTRIC(BOV)+PURE EV,3\n",
}


def test_smoke_touches_every_table_and_never_writes(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(refresh, "run_command", fake_runner(GOOD, calls))
    result = refresh.execute_vahan("vahan_smoke", tmp_path, {})
    assert result["outcome"] == "success"
    assert set(result["steps"]) == {"yearly", "monthly_maker", "monthly_category"}
    assert all(s["ingest"] == "dry_run_rolled_back" for s in result["steps"].values())
    ingests = [c for c in calls if "scripts.ingest_vahan" in c]
    assert len(ingests) == 3 and not any("--write" in c for c in ingests)


def test_monthly_job_commits_every_csv(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(refresh, "run_command", fake_runner(GOOD, calls))
    result = refresh.execute_vahan("vahan_monthly", tmp_path, {})
    assert result["outcome"] == "success"
    assert sum("--write" in c for c in calls if "scripts.ingest_vahan" in c) == 3


def test_a_step_with_only_markers_fails_before_any_ingest(tmp_path, monkeypatch):
    csvs = {
        **GOOD,
        "monthly_maker.csv": MONTHLY + "KL,ALL,2025-01-01,maker,__NONE__,ELECTRIC(BOV)+PURE EV,0\n",
    }
    calls = []
    monkeypatch.setattr(refresh, "run_command", fake_runner(csvs, calls))
    result = refresh.execute_vahan("vahan_smoke", tmp_path, {})
    assert result == {
        "outcome": "failed",
        "step": "monthly_maker",
        "reason": "no_positive_registration_rows",
        "steps": {
            "yearly": {"rows": 1, "positive_rows": 1},
            "monthly_maker": {"rows": 1, "positive_rows": 0},
        },
    }
    assert not any("scripts.ingest_vahan" in c for c in calls)
