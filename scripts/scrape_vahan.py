"""Fresh VAHAN scraper - PART 4.1. Drive the dashboard, write a long CSV.

    uv run python -m scripts.scrape_vahan --dry-run --limit 2
    uv run python -m scripts.scrape_vahan --state kerala --years 2023,2024,2025
    uv run python -m scripts.scrape_vahan            # KL+TN, 3 years + cumulative

The government dashboard (vahan.parivahan.gov.in) is a PrimeFaces/JSF app with
no API: every figure is behind a chain of AJAX dropdowns (Y-Axis, X-Axis, Year
Type, Year, State, RTO) and a Refresh. The dropdown-driving below is adapted
from a proven scraper; what is NEW here, and the reason for a fresh fetcher, is
what it KEEPS and WHEN:

  * every vehicle-category column, not a hand-picked five - so buses and heavy
    goods (the fleet/commercial share PLAN 4.1 asks for, and the biggest
    charging anchors) are no longer thrown away;
  * one pass PER CALENDAR YEAR, not a single "Till Today" cumulative - because
    the plan weights the growth rate above the absolute count, and a growth rate
    needs more than one year to exist.

Output is a LONG CSV (one row per state, RTO, period, fuel, vehicle class,
count) at ``data/vahan/scrape_<date>.csv`` - the exact shape ``scripts.ingest_
vahan`` reads back. The scrape and the database write are deliberately two
steps: the CSV is the vintaged artifact, and its sha256 becomes each row's
provenance.

Needs a browser. Install the extra once:  uv sync --extra scrape
The scrape is long (hundreds of RTO x year reads); it saves after every RTO and
``--resume`` skips pairs already in the output file, so a crash costs minutes.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import random
import socket
import sys
import time
from pathlib import Path
from typing import Any

from app.domain.vahan.parse import EV_FUELS, RtoClassCount, normalise_class

URL = "https://vahan.parivahan.gov.in/vahan4dashboard/vahan/view/reportview.xhtml"

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "vahan"
SEED = DATA_DIR / "rto_reference.csv"

STATE_NAMES = {"KL": "Kerala", "TN": "Tamil Nadu"}


# --------------------------------------------------------------------------- IO


def load_refs(states: list[str]) -> list[dict[str, str]]:
    """The RTO seed rows for the requested two-letter state codes."""
    if not SEED.exists():
        raise SystemExit(f"missing {SEED} - build it first (see FINDINGS.md PART 4.1).")
    with SEED.open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["state_code"] in states]
    if not rows:
        raise SystemExit(f"no RTOs in the seed for states {states}.")
    return rows


def already_done(out_path: Path) -> set[tuple[str, str]]:
    """(rto, period) pairs already in a partial output file, for --resume."""
    done: set[tuple[str, str]] = set()
    if out_path.exists():
        with out_path.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                done.add((r["rto"], r["period"]))
    return done


# --------------------------------------------------- selenium / primefaces glue


def _chrome_major_version() -> int | None:
    """Installed Chrome's major version (Windows registry), or None.

    undetected-chromedriver downloads the newest driver by default; when the
    installed Chrome is one release behind, the session refuses to start
    ("only supports Chrome version N"). Pinning version_main to the browser
    actually present keeps the two in step. None falls back to uc's default.
    """
    if sys.platform != "win32":
        return None
    import winreg  # noqa: PLC0415 - windows only

    try:
        key_path = r"Software\Google\Chrome\BLBeacon"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            version, _ = winreg.QueryValueEx(key, "version")
        return int(str(version).split(".")[0])
    except OSError:
        return None


def start_driver() -> tuple[Any, Any]:
    try:
        import undetected_chromedriver as uc  # noqa: PLC0415 - optional, lazy on purpose
        from selenium.webdriver.support.ui import WebDriverWait  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit(
            "browser deps missing. Install them with:  uv sync --extra scrape"
        ) from exc

    # If Chrome dies mid-run, selenium's HTTP calls to the dead driver would
    # otherwise block forever - the run hangs instead of failing. A socket
    # default turns that into an exception the retry logic can act on.
    socket.setdefaulttimeout(180)

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=options, version_main=_chrome_major_version())
    wait = WebDriverWait(driver, 30)
    driver.get(URL)
    print("browser started")
    return driver, wait


def wait_pf_ajax_idle(driver: Any, timeout: int = 60) -> None:
    from selenium.webdriver.support.ui import WebDriverWait  # noqa: PLC0415

    # A timeout here just means "carry on and check the table anyway".
    with contextlib.suppress(Exception):
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script(
                "return (window.PrimeFaces && PrimeFaces.ajax && PrimeFaces.ajax.Queue)"
                " ? PrimeFaces.ajax.Queue.isEmpty() : true;"
            )
        )


def label_id(driver: Any, field: str) -> str | None:
    from selenium.webdriver.common.by import By  # noqa: PLC0415

    fallbacks = {
        "Y-Axis": "yaxisVar_label",
        "X-Axis": "xaxisVar_label",
        "Year Type": "selectedYearType_label",
        "Year": "selectedYear_label",
        "State": "j_idt37_label",
        "RTO": "selectedRto_label",
    }
    if field in fallbacks:
        try:
            driver.find_element(By.ID, fallbacks[field])
            return fallbacks[field]
        except Exception:  # noqa: BLE001 - fall through to the generic search
            pass
    try:
        xpath = f"//label[normalize-space(text())='{field}:']/following::select[1]"
        el = driver.find_element(By.XPATH, xpath)
        return str(el.get_attribute("id")).replace("_input", "_label")
    except Exception:  # noqa: BLE001
        return fallbacks.get(field)


def pick(driver: Any, wait: Any, lid: str | None, option: str) -> None:
    """Open a PrimeFaces dropdown and click an option by its label."""
    from selenium.common.exceptions import TimeoutException  # noqa: PLC0415
    from selenium.webdriver.common.by import By  # noqa: PLC0415
    from selenium.webdriver.support import expected_conditions as ec  # noqa: PLC0415

    if not lid:
        raise ValueError(f"no label id (selecting {option!r})")
    panel = lid.replace("_label", "_panel")
    dropdown = wait.until(ec.element_to_be_clickable((By.ID, lid)))
    driver.execute_script("arguments[0].click();", dropdown)
    try:
        wait.until(ec.visibility_of_element_located((By.ID, panel)))
    except TimeoutException:
        # A lingering open panel or in-flight AJAX swallows the first click
        # now and then; close whatever is open and try once more.
        from selenium.webdriver.common.keys import Keys  # noqa: PLC0415

        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.6)
        driver.execute_script("arguments[0].click();", dropdown)
        wait.until(ec.visibility_of_element_located((By.ID, panel)))
    time.sleep(random.uniform(0.4, 0.9))
    try:
        xp = f"//div[@id='{panel}']//li[@data-label=\"{option}\"]"
        el = wait.until(ec.element_to_be_clickable((By.XPATH, xp)))
    except Exception:  # noqa: BLE001 - fall back to a contains() match
        xp = f"//div[@id='{panel}']//li[contains(normalize-space(.), \"{option}\")]"
        el = wait.until(ec.element_to_be_clickable((By.XPATH, xp)))
    driver.execute_script("arguments[0].click();", el)
    wait_pf_ajax_idle(driver)
    time.sleep(random.uniform(0.4, 1.0))


def apply_base_filters(driver: Any, wait: Any, year: str) -> None:
    """Set the four global filters: Fuel x Vehicle Category, one calendar year."""
    pick(driver, wait, label_id(driver, "Y-Axis"), "Fuel")
    pick(driver, wait, label_id(driver, "X-Axis"), "Vehicle Category")
    pick(driver, wait, label_id(driver, "Year Type"), "Calendar Year")
    pick(driver, wait, label_id(driver, "Year"), year)


#: Pull every PrimeFaces datatable off the page as (class header row, body
#: rows), via textContent. Selenium's ``.text`` is empty for anything scrolled
#: out of view, and the scrollable table renders its real header in a cloned
#: sibling <table> - so per-cell ``.text`` against ``//thead/tr/th`` reads a
#: soup of clones and blanks. The wrapper div owns both clones; textContent
#: does not care about visibility; and the class row is the only header row
#: with every cell non-empty and none of the fixed labels.
_TABLES_JS = """
const out = [];
const FIXED = new Set(['S NO', 'FUEL', 'VEHICLE CATEGORY', 'TOTAL']);
for (const tb of document.querySelectorAll("tbody[id*='_data']")) {
  const wrapper = tb.closest('div.ui-datatable');
  if (!wrapper) continue;
  const headRows = Array.from(wrapper.querySelectorAll('thead tr'))
    .map(tr => Array.from(tr.children).map(th => th.textContent.trim()));
  const hasFuel = headRows.some(r => r.some(c => c.toUpperCase() === 'FUEL'));
  const classes = headRows.find(r =>
    r.length > 1 && r.every(c => c) &&
    !r.some(c => FIXED.has(c.toUpperCase())));
  if (!hasFuel || !classes) continue;
  const rows = Array.from(tb.querySelectorAll(':scope > tr')).map(tr =>
    Array.from(tr.children).map(td => td.textContent.trim()));
  if (rows.length) out.push({classes: classes, rows: rows});
}
return out;
"""


def extract_long_rows(driver: Any, state_code: str, rto: str, period: str) -> list[RtoClassCount]:
    """The rendered table -> long rows: every EV fuel x every class column.

    Body rows come as [S No, Fuel, <one count per class column>, TOTAL]; the
    class names arrive positionally from the table's own header, so the TOTAL
    at the end is kept under its own name and never mistaken for a class.
    """
    from selenium.webdriver.common.by import By  # noqa: PLC0415
    from selenium.webdriver.support.ui import WebDriverWait  # noqa: PLC0415

    # Wait for the AJAX block-overlay to clear; if it never appeared, move on.
    with contextlib.suppress(Exception):
        WebDriverWait(driver, 5).until(
            lambda d: (
                not d.find_elements(By.CLASS_NAME, "ui-blockui")
                or not d.find_element(By.CLASS_NAME, "ui-blockui").is_displayed()
            )
        )

    out: list[RtoClassCount] = []
    for table in driver.execute_script(_TABLES_JS):
        classes = [normalise_class(c) for c in table["classes"]]
        for cells in table["rows"]:
            if len(cells) < len(classes) + 2:
                continue
            fuel = cells[1].strip()
            if fuel not in EV_FUELS:
                continue
            named = list(zip(classes, cells[2 : 2 + len(classes)], strict=True))
            if len(cells) > len(classes) + 2:  # trailing row-total column
                named.append(("TOTAL", cells[-1]))
            for vclass, raw in named:
                raw = raw.replace(",", "").strip()
                if not raw.lstrip("-").isdigit():
                    continue
                out.append(RtoClassCount(state_code, rto, period, fuel, vclass, int(raw)))
        if out:  # first table with EV rows is the fuel table; stop there
            break
    return out


# ------------------------------------------------------------------------ drive


def scrape(
    refs: list[dict[str, str]],
    years: list[str],
    *,
    out_path: Path,
    dry_run: bool,
    resume: bool,
) -> int:
    from selenium.webdriver.common.by import By  # noqa: PLC0415
    from selenium.webdriver.common.keys import Keys  # noqa: PLC0415
    from selenium.webdriver.support import expected_conditions as ec  # noqa: PLC0415

    done = already_done(out_path) if resume and not dry_run else set()
    writer = None
    fh = None
    if not dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not out_path.exists() or not resume
        mode = "w" if new_file else "a"
        fh = out_path.open(mode, newline="", encoding="utf-8")
        writer = csv.writer(fh)
        if new_file:
            writer.writerow(("state_code", "rto", "period", "fuel", "vehicle_class", "count"))
            fh.flush()

    driver, wait = start_driver()
    time.sleep(2)
    written = 0

    try:
        by_state: dict[str, list[dict[str, str]]] = {}
        for r in refs:
            by_state.setdefault(r["state_code"], []).append(r)

        for year in years:
            print(f"\n===== YEAR {year} =====")
            # One flaky dropdown must not cost the whole run: reload the
            # dashboard and re-apply from scratch before giving up.
            for attempt in range(1, 4):
                try:
                    apply_base_filters(driver, wait, year)
                    break
                except Exception:  # noqa: BLE001 - selenium raises many shapes
                    if attempt == 3:
                        raise
                    print(f"  base filters failed (attempt {attempt}); reloading")
                    driver.get(URL)
                    time.sleep(3)
                    wait_pf_ajax_idle(driver)
            for state_code, state_refs in by_state.items():
                state_name = STATE_NAMES.get(state_code, state_code)
                print(f"--- {state_name} ({state_code}) ---")
                pick(driver, wait, label_id(driver, "State"), state_name)
                for r in state_refs:
                    rto = r["rto"]
                    if (rto, year) in done:
                        continue
                    rows: list[RtoClassCount] = []
                    for attempt in range(1, 4):
                        try:
                            pick(driver, wait, label_id(driver, "RTO"), rto)
                            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                            btn = wait.until(
                                ec.element_to_be_clickable(
                                    (By.XPATH, "//button[contains(.,'Refresh')]")
                                )
                            )
                            driver.execute_script("arguments[0].click();", btn)
                            wait_pf_ajax_idle(driver)
                            time.sleep(1.2)
                            rows = extract_long_rows(driver, state_code, rto, year)
                            break
                        except Exception as exc:  # noqa: BLE001 - retry, then skip
                            first = str(exc).splitlines()[0] if str(exc).strip() else ""
                            print(
                                f"  {rto} [{year}] attempt {attempt}/3: "
                                f"{type(exc).__name__}: {first}"
                            )
                            time.sleep(2)
                            if attempt >= 2:
                                # Two failures in a row usually means the
                                # session itself is gone - only a fresh
                                # browser can still save this RTO. If even
                                # that fails, die loudly; --resume makes the
                                # restart cheap.
                                print("  restarting browser")
                                with contextlib.suppress(Exception):
                                    driver.quit()
                                driver, wait = start_driver()
                                time.sleep(2)
                                apply_base_filters(driver, wait, year)
                                pick(driver, wait, label_id(driver, "State"), state_name)
                    ev_total = sum(x.count for x in rows if x.vehicle_class == "TOTAL")
                    print(f"  {rto} [{year}]: {len(rows)} rows, {ev_total} EV total")
                    if dry_run:
                        for x in rows[:4]:
                            print(f"      {x.fuel} {x.vehicle_class}={x.count}")
                    elif writer is not None and fh is not None:
                        for x in rows:
                            writer.writerow(
                                (x.state_code, x.rto, x.period, x.fuel, x.vehicle_class, x.count)
                            )
                        fh.flush()
                    written += len(rows)
    finally:
        if fh is not None:
            fh.close()
        with contextlib.suppress(Exception):
            driver.quit()

    return written


def default_years() -> list[str]:
    """The last three complete calendar years plus the current one."""
    this_year = dt.date.today().year
    return [str(y) for y in range(this_year - 3, this_year + 1)]


def main() -> None:
    # Line-buffer stdout so a redirected log shows progress live rather than
    # in 4KB lumps half an hour late.
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(line_buffering=True)

    p = argparse.ArgumentParser(description="Scrape VAHAN EV registrations (PLAN 4.1)")
    p.add_argument("--state", default="kerala,tamilnadu", help="comma list: kerala,tamilnadu")
    p.add_argument("--years", default="", help="comma list, e.g. 2023,2024,2025 (default: last 4)")
    p.add_argument("--cumulative", action="store_true", help="also scrape the 'Till Today' total")
    p.add_argument("--limit", type=int, default=0, help="only the first N RTOs (smoke test)")
    p.add_argument("--dry-run", action="store_true", help="print, do not write the CSV")
    p.add_argument("--no-resume", action="store_true", help="ignore any partial output file")
    args = p.parse_args()

    code_of = {"kerala": "KL", "tamilnadu": "TN", "tamil_nadu": "TN", "tn": "TN", "kl": "KL"}
    states = [code_of.get(s.strip().lower(), s.strip().upper()) for s in args.state.split(",")]

    refs = load_refs(states)
    if args.limit:
        refs = refs[: args.limit]

    years = [y.strip() for y in args.years.split(",") if y.strip()] or default_years()
    if args.cumulative:
        years = [*years, "Till Today"]

    out_path = DATA_DIR / f"scrape_{dt.date.today():%Y%m%d}.csv"
    print(f"{len(refs)} RTOs x {len(years)} periods {years}")
    print(f"output: {out_path}" if not args.dry_run else "dry run - nothing written")

    written = scrape(
        refs, years, out_path=out_path, dry_run=args.dry_run, resume=not args.no_resume
    )
    print(f"\ndone: {written} rows")
    if not args.dry_run:
        print(f"ingest with:  uv run python -m scripts.ingest_vahan --csv {out_path} --write")


if __name__ == "__main__":
    main()
