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
