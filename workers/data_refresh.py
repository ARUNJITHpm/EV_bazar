"""Weekly inventory on HF; persistent catch-up, one job at a time, durable ZIPs.

Weekly: Sunday 03:00 IST - station inventory, and CEA's EV charging
electricity report (published irregularly, 2-5 months late, so checked weekly;
off with CEA_EV_ENABLED=false). Optional VAHAN monthly: day 1, 04:00 IST.
Free Spaces sleep; GitHub's weekly wake-up workflow wakes the web container.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import io
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from app.domain.context.station_pipeline import VERSION_STAMPS
from app.models.data_refresh import DataRefreshEvent

log = logging.getLogger("data_refresh")
IST = ZoneInfo("Asia/Kolkata")
MAX_ATTEMPTS = 3


def run_command(
    command: list[str],
    *,
    timeout: int,
    environment: dict[str, str],
    output: Any,
) -> int:
    """Bound a subprocess and kill its whole Linux browser process group on timeout."""
    process = subprocess.Popen(
        command,
        stdout=output,
        stderr=subprocess.STDOUT,
        env=environment,
        start_new_session=sys.platform != "win32",
    )
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if sys.platform != "win32":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()
        raise


def due_period(job: str, now: dt.datetime) -> str:
    local = now.astimezone(IST)
    if job in {"vahan_monthly", "vahan_smoke"}:
        first = local.replace(day=1, hour=4, minute=0, second=0, microsecond=0)
        if local < first:
            first = (first - dt.timedelta(days=1)).replace(day=1)
        return first.strftime("%Y-%m")
    sunday = (local - dt.timedelta(days=(local.weekday() + 1) % 7)).replace(
        hour=3, minute=0, second=0, microsecond=0
    )
    if local < sunday:
        sunday -= dt.timedelta(days=7)
    return sunday.date().isoformat()


def next_attempt(events: list[DataRefreshEvent], now: dt.datetime) -> int | None:
    if any(e.outcome == "success" for e in events):
        return None
    latest = max(events, key=lambda e: e.observed_at) if events else None
    if latest:
        observed = latest.observed_at
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=dt.UTC)
        if now - observed < dt.timedelta(hours=1):
            return None
    attempt = max((e.attempt for e in events), default=0) + 1
    return attempt if attempt <= MAX_ATTEMPTS else None


def archive_folder(directory: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(directory).as_posix())
    return buffer.getvalue()


#: One VAHAN step: a name, its scrape arguments, the CSV it writes, a timeout.
VahanStep = tuple[str, list[str], str, int]


def vahan_steps(job: str) -> list[VahanStep]:
    """The scrapes a VAHAN job runs, smallest first.

    The smoke test touches every table's path once: one RTO for the yearly
    table, one state's makers and one RTO's categories for the monthly table.
    The monthly job reads everything: yearly per RTO (last four years), then
    month-wise for last year and this year, which re-reads the months late RTO
    uploads keep revising.
    """
    if job == "vahan_smoke":
        return [
            ("yearly", ["--limit", "1", "--years", "2025"], "vahan.csv", 900),
            (
                "monthly_maker",
                ["--monthly", "maker", "--state", "kerala", "--years", "2025"],
                "monthly_maker.csv",
                900,
            ),
            (
                "monthly_category",
                ["--monthly", "vehicle_category", "--limit", "1", "--years", "2025"],
                "monthly_category.csv",
                900,
            ),
        ]
    return [
        ("yearly", [], "vahan.csv", 14400),
        ("monthly_maker", ["--monthly", "maker"], "monthly_maker.csv", 3600),
        ("monthly_category", ["--monthly", "vehicle_category"], "monthly_category.csv", 14400),
    ]


def positive_rows(csv_path: Path) -> tuple[int, int]:
    """(rows, rows with a real positive count) in a yearly or monthly scrape CSV.

    Resume markers (yearly fuel NONE, monthly label __NONE__) never count.
    """
    import csv

    from app.domain.vahan.monthly import NO_ROWS

    with csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    positive = sum(
        1
        for row in rows
        if row.get("fuel") != "NONE"
        and row.get("label") != NO_ROWS
        and int(row.get("count") or "0") > 0
    )
    return len(rows), positive


def execute_vahan(job: str, directory: Path, environment: dict[str, str]) -> dict[str, Any]:
    """Scrape every step, refuse an empty one, then ingest.

    The monthly job commits each CSV. The smoke test runs the same ingest
    WITHOUT ``--write`` - resolved, aggregated and rolled back - so it proves
    the database path for every table while leaving no partial snapshot in
    tables the site reads.
    """
    steps: dict[str, Any] = {}
    with (directory / "run.log").open("ab") as output:
        for name, arguments, filename, timeout in vahan_steps(job):
            csv_path = directory / filename
            command = [sys.executable, "-m", "scripts.scrape_vahan", "--out", str(csv_path)]
            output.write(f"\n===== {name}: scrape {' '.join(arguments)}\n".encode())
            output.flush()
            try:
                returncode = run_command(
                    [*command, *arguments],
                    timeout=timeout,
                    environment=environment,
                    output=output,
                )
            except subprocess.TimeoutExpired:
                return {"outcome": "failed", "step": name, "reason": "timeout", "steps": steps}
            if returncode != 0 or not csv_path.exists():
                return {"outcome": "failed", "step": name, "returncode": returncode, "steps": steps}
            rows, positive = positive_rows(csv_path)
            steps[name] = {"rows": rows, "positive_rows": positive}
            if not positive:
                return {
                    "outcome": "failed",
                    "step": name,
                    "reason": "no_positive_registration_rows",
                    "steps": steps,
                }
        write = job == "vahan_monthly"
        for name, _arguments, filename, _timeout in vahan_steps(job):
            csv_path = directory / filename
            ingest = [sys.executable, "-m", "scripts.ingest_vahan", "--csv", str(csv_path)]
            if write:
                ingest.append("--write")
            mode = "write" if write else "dry run, rolled back"
            output.write(f"\n===== {name}: ingest ({mode})\n".encode())
            output.flush()
            failed = {"outcome": "failed", "step": name, "steps": steps}
            try:
                returncode = run_command(
                    ingest, timeout=1800, environment=environment, output=output
                )
            except subprocess.TimeoutExpired:
                return {**failed, "reason": "ingest_timeout"}
            if returncode != 0:
                return {**failed, "reason": "ingest_failed"}
            steps[name]["ingest"] = "committed" if write else "dry_run_rolled_back"
    return {"outcome": "success", "steps": steps}


def execute_cea(directory: Path, environment: dict[str, str]) -> dict[str, Any]:
    """Store any CEA report not already stored; the PDFs go into the archive.

    "Nothing new" is a success: the listing usually still shows last month's
    report, which the store recognises by its sha256 and skips.
    """
    command = [
        sys.executable,
        "-m",
        "scripts.fetch_cea_ev",
        "--write",
        "--out",
        str(directory / "cea"),
    ]
    with (directory / "run.log").open("wb") as output:
        try:
            returncode = run_command(command, timeout=900, environment=environment, output=output)
        except subprocess.TimeoutExpired:
            return {"outcome": "failed", "reason": "timeout"}
    log_text = (directory / "run.log").read_text(encoding="utf-8", errors="replace")
    if returncode != 0:
        return {"outcome": "failed", "returncode": returncode}
    return {
        "outcome": "success",
        "stored_reports": log_text.count("  stored "),
        "already_stored": log_text.count("already stored"),
    }


def execute_job(job: str, directory: Path) -> dict[str, Any]:
    environment = {**os.environ, "VAHAN_HEADLESS": "true"}
    if job.startswith("vahan"):
        return execute_vahan(job, directory, environment)
    if job == "cea_ev_weekly":
        return execute_cea(directory, environment)
    command = [
        sys.executable,
        "-m",
        "scripts.refresh_stations",
        "--write",
        "--out",
        str(directory / "stations"),
        "--sources",
        "ocm",
        "goec",
        "zeon",
    ]
    with (directory / "run.log").open("wb") as output:
        try:
            returncode = run_command(command, timeout=1800, environment=environment, output=output)
        except subprocess.TimeoutExpired:
            return {"outcome": "failed", "reason": "timeout"}
    if returncode != 0:
        return {"outcome": "failed", "returncode": returncode}
    manifests = list((directory / "stations").glob("*/manifest.json"))
    if len(manifests) != 1:
        return {"outcome": "failed", "reason": "missing_manifest"}
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    if manifest.get("database_write") != "committed":
        return {"outcome": "failed", "reason": "inventory_not_committed"}
    return {"outcome": "success", "manifest": manifest}


def run_due(job: str, now: dt.datetime) -> None:
    from app.db import SessionLocal, engine

    period = due_period(job, now)
    if job == "vahan_smoke":
        # A revised browser adapter may be explicitly retested in the same month.
        period += "-" + os.getenv("VAHAN_SERVER_SMOKE_REVISION", "v1")[:8]
    # Dedicated connection holds the SESSION lock throughout the subprocess.
    # A crash drops the connection/lock; persistent events bound later retries.
    with engine.connect() as connection:
        locked = connection.execute(
            text("SELECT pg_try_advisory_lock(hashtext(:job))"), {"job": "evsite:data_refresh"}
        ).scalar_one()
        connection.commit()
        if not locked:
            return
        try:
            with SessionLocal() as session:
                if job == "vahan_monthly":
                    smoke = session.execute(
                        select(DataRefreshEvent.id)
                        .where(
                            DataRefreshEvent.job == "vahan_smoke",
                            DataRefreshEvent.outcome == "success",
                        )
                        .limit(1)
                    ).scalar_one_or_none()
                    if smoke is None:
                        log.warning("VAHAN monthly refused: successful server smoke test required")
                        return
                events = list(
                    session.scalars(
                        select(DataRefreshEvent).where(
                            DataRefreshEvent.job == job, DataRefreshEvent.period == period
                        )
                    )
                )
                attempt = next_attempt(events, now)
                if attempt is None:
                    return
                session.add(
                    DataRefreshEvent(
                        job=job,
                        period=period,
                        attempt=attempt,
                        outcome="started",
                        observed_at=now,
                        payload=dict(VERSION_STAMPS),
                    )
                )
                session.commit()
            log.info("starting %s period=%s attempt=%s", job, period, attempt)
            # Keep artifacts on disk if archive commit fails. Only the success
            # path removes this bounded, verified temporary directory.
            with contextlib.nullcontext(tempfile.mkdtemp(prefix=f"evsite-{job}-")) as scratch:
                directory = Path(scratch)
                try:
                    payload = execute_job(job, directory)
                except Exception as error:
                    payload = {"outcome": "failed", "error_type": type(error).__name__}
                archive = archive_folder(directory)
                payload.update(VERSION_STAMPS, archive_sha256=hashlib.sha256(archive).hexdigest())
                with SessionLocal() as session:
                    session.add(
                        DataRefreshEvent(
                            job=job,
                            period=period,
                            attempt=attempt,
                            outcome=payload["outcome"],
                            observed_at=dt.datetime.now(dt.UTC),
                            payload=payload,
                            archive=archive,
                        )
                    )
                    session.commit()
                log.info("finished %s period=%s outcome=%s", job, period, payload["outcome"])
                target = directory.resolve()
                if target.is_relative_to(
                    Path(tempfile.gettempdir()).resolve()
                ) and target.name.startswith("evsite-"):
                    shutil.rmtree(target)
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(hashtext(:job))"), {"job": "evsite:data_refresh"}
            )
            connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    while True:
        jobs = ["stations_weekly"]
        if os.getenv("CEA_EV_ENABLED", "true").lower() == "true":
            jobs.append("cea_ev_weekly")
        if os.getenv("VAHAN_SERVER_SMOKE", "false").lower() == "true":
            jobs.append("vahan_smoke")
        if os.getenv("VAHAN_SERVER_ENABLED", "false").lower() == "true":
            jobs.append("vahan_monthly")
        for job in jobs:
            try:
                run_due(job, dt.datetime.now(dt.UTC))
            except Exception as error:
                log.error("%s scheduler failed (%s)", job, type(error).__name__)
        if args.once:
            return
        time.sleep(60)


if __name__ == "__main__":
    main()
