@echo off
REM ---------------------------------------------------------------------------
REM VAHAN monthly refresh (PLAN 4.1). Scrape the dashboard, then ingest.
REM
REM Registered with Windows Task Scheduler via scripts\vahan_etl_task.xml (see
REM LOCAL_DEV.md). Runs monthly, not nightly: VAHAN's numbers move on a monthly
REM cadence, and each run is a new snapshot in the time series - never an
REM overwrite - so there is nothing to lose by spacing them out.
REM
REM The output CSV is stamped ONCE here and pinned with --out, so a run that
REM crosses midnight keeps appending to the same file instead of restarting
REM from scratch under the new day's name. The scraper's browser dies every
REM few hours on the real dashboard, so the scrape is retried in a loop until
REM its "done:" marker appears in the log - resume makes each retry cheap.
REM
REM "vahan_refresh.bat --smoke" is a fast end-to-end rehearsal: 2 RTOs, its
REM own scrape_smoke.csv, and a sentinel snapshot date (2000-01-01) so it can
REM never touch a real snapshot. Clean up after with:
REM   delete from vahan_ev_registrations where snapshot_date='2000-01-01'
REM   del data\vahan\scrape_smoke.csv data\vahan\refresh_smoke.log
REM
REM Prereqs (once): uv sync --extra scrape   (installs the browser driver)
REM ---------------------------------------------------------------------------
title EV_Bazar VAHAN monthly refresh
cd /d "%~dp0.."

set SCRAPE_EXTRA=
set INGEST_EXTRA=
if "%~1"=="--smoke" (
    set STAMP=smoke
    set SCRAPE_EXTRA=--limit 2
    set INGEST_EXTRA=--snapshot-date 2000-01-01
) else (
    for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set STAMP=%%i
)
set CSV=data\vahan\scrape_%STAMP%.csv
set LOG=data\vahan\refresh_%STAMP%.log

echo ==============================================
echo   VAHAN REFRESH - scrape then ingest (KL, TN)
echo ==============================================

echo [1/2] scraping the dashboard into %CSV% (this is long, log: %LOG%)...
set ATTEMPT=0
:scrape
set /a ATTEMPT+=1
echo REFRESH: scrape attempt %ATTEMPT% >> "%LOG%"
call uv run python -m scripts.scrape_vahan --state kerala,tamilnadu --out %CSV% %SCRAPE_EXTRA% >> "%LOG%" 2>&1
findstr /b /c:"done: " "%LOG%" >nul
if %errorlevel%==0 goto scraped
if %ATTEMPT% geq 12 (
    echo scrape failed after 12 attempts - see %LOG%
    exit /b 1
)
timeout /t 90 /nobreak >nul
goto scrape
:scraped

echo [2/2] ingesting %CSV% into the database...
call uv run python -m scripts.ingest_vahan --csv %CSV% --write %INGEST_EXTRA%
if not %errorlevel%==0 (
    echo ingest failed - the CSV is safe, rerun: uv run python -m scripts.ingest_vahan --csv %CSV% --write %INGEST_EXTRA%
    exit /b 1
)

echo ==============================================
echo   VAHAN REFRESH COMPLETE
echo ==============================================
