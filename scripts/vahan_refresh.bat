@echo off
REM ---------------------------------------------------------------------------
REM VAHAN monthly refresh (PLAN 4.1). Scrape the dashboard, then ingest.
REM
REM Registered with Windows Task Scheduler via scripts\vahan_etl_task.xml (see
REM LOCAL_DEV.md). Runs monthly, not nightly: VAHAN's numbers move on a monthly
REM cadence, and each run is a new snapshot in the time series - never an
REM overwrite - so there is nothing to lose by spacing them out.
REM
REM Prereqs (once): uv sync --extra scrape   (installs the browser driver)
REM ---------------------------------------------------------------------------
title EV_Bazar VAHAN monthly refresh
cd /d "%~dp0.."

echo ==============================================
echo   VAHAN REFRESH - scrape then ingest (KL, TN)
echo ==============================================

echo [1/2] scraping the dashboard (this is long)...
call uv run python -m scripts.scrape_vahan --state kerala,tamilnadu

echo [2/2] ingesting the newest scrape into the database...
call uv run python -m scripts.ingest_vahan --csv latest --write

echo ==============================================
echo   VAHAN REFRESH COMPLETE
echo ==============================================
