"""Fetch CEA's monthly EV charging electricity reports and store new ones.

    uv run python -m scripts.fetch_cea_ev                      # check the listing, dry run
    uv run python -m scripts.fetch_cea_ev --write              # store any new report
    uv run python -m scripts.fetch_cea_ev --url <pdf> --write  # backfill one known report
    uv run python -m scripts.fetch_cea_ev --file report.pdf    # parse a local copy, dry run

CEA publishes "EV Public Charging Stations Monthly Power Consumption Report"
about monthly, 2-5 months after the month (March 2026 appeared in August
2026), sometimes several months at once, sometimes re-issued. The report page
lists every report with its month (August 2022 onwards); each run downloads
those whose month falls in the last ``--months`` months and stores any file it
has not seen. ``--from YYYY-MM`` backfills further back.

CEA moved its site in late October 2026: the old WordPress listing now 404s
and its month-archive AJAX endpoint answers 403, which broke this job from
2026-11-03. The reports now live on a "dashboardView" page whose table links
each PDF through ``/api/dashboardReports/view-pdf/en/<uuid>``. If that page
ever lists nothing, the run fails loudly rather than reporting "nothing new".
Every report also carries financial-year-to-date totals, so a month whose own
report was never fetched can still be recovered from two neighbours.

Each PDF is saved under ``--out`` (default ``data/cea_ev/``) before it is
parsed, so the stored figures always have their source file beside them.
Without ``--write`` nothing touches the database.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import re
import sys
import time
from pathlib import Path

import httpx

SITE = "https://cea.nic.in"
#: Reports > ... > "Electric Vehicle Charging Station / Power Consumption".
LISTING = (
    f"{SITE}/reports/dashboardView?headingId=107&subHeadingId=1003&subSubHeadingId=10015"
    "&title=Electric%20Vehicle%20Charging%20Station%20/%20Power%20Consumption&lang=en"
)
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_VIEW = re.compile(
    r"/api/dashboardReports/view-pdf/en/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})"
)
_MONTH = re.compile(r"<td[^>]*>\s*(20\d\d-(?:0[1-9]|1[0-2]))\s*</td>")
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "cea_ev"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Chargeworthy data refresh)"}


def parse_listing(html: str) -> list[tuple[str, str]]:
    """(report month "YYYY-MM", PDF URL) for each row of the report table, no repeats."""
    out: dict[str, str] = {}
    for row in _ROW.findall(html):
        pdf = _VIEW.search(row)
        month = _MONTH.search(row)
        if pdf and month:
            out.setdefault(
                f"{SITE}/api/dashboardReports/view-pdf/en/{pdf.group(1)}", month.group(1)
            )
    return [(month, url) for url, month in out.items()]


def listed_reports(client: httpx.Client, months: list[str]) -> list[str]:
    """PDF URLs of the listed reports whose month is in ``months``, oldest first."""
    page = client.get(LISTING)
    page.raise_for_status()
    rows = parse_listing(page.text)
    if not rows:
        raise SystemExit(f"no reports found on {LISTING} - has the page changed again?")
    wanted = set(months)
    return [url for month, url in sorted(rows) if month in wanted]


#: CEA's server sometimes closes a PDF download early (seen 2026-11-11: 332 of
#: 361 kB, then RemoteProtocolError). A cut transfer is retried; an HTTP error
#: status is not - that is an answer, not a dropped connection.
DOWNLOAD_ATTEMPTS = 3


def download(client: httpx.Client, url: str) -> bytes:
    """GET ``url``'s body, retrying a dropped connection up to ``DOWNLOAD_ATTEMPTS`` times."""
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            return client.get(url).raise_for_status().content
        except httpx.TransportError as exc:
            if attempt == DOWNLOAD_ATTEMPTS:
                raise
            print(f"  download cut short ({type(exc).__name__}), retrying: {url}")
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def months_back(today: dt.date, count: int, start: str | None = None) -> list[str]:
    """Report months to fetch, oldest first, as "YYYY-MM"."""
    if start:
        year, month = (int(part) for part in start.split("-"))
    else:
        index = today.year * 12 + today.month - 1 - (count - 1)
        year, month = divmod(index, 12)
        month += 1
    out: list[str] = []
    while (year, month) <= (today.year, today.month):
        out.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def pdf_pages(raw: bytes) -> list[str]:
    from pypdf import PdfReader  # noqa: PLC0415 - only this script needs it

    return [page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages]


def main() -> int:
    from app.domain.cea.parse import ReportFormatError, parse_report

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--url", action="append", default=[], help="a report PDF URL (repeatable)")
    p.add_argument("--months", type=int, default=12, help="report months to check (default 12)")
    p.add_argument("--from", dest="start", help="check the archive from YYYY-MM instead")
    p.add_argument("--file", help="parse a local PDF instead of downloading")
    p.add_argument("--out", default=str(DATA_DIR), help="where downloaded PDFs are kept")
    p.add_argument("--write", action="store_true", help="store new reports in the database")
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sources: list[tuple[str, bytes]] = []
    if args.file:
        sources.append((Path(args.file).resolve().as_uri(), Path(args.file).read_bytes()))
    else:
        with httpx.Client(timeout=120, headers=HEADERS, follow_redirects=True) as client:
            urls = args.url or listed_reports(
                client, months_back(dt.date.today(), args.months, args.start)
            )
            print(f"{len(urls)} report(s): {urls}")
            for url in urls:
                content = download(client, url)
                if not content.startswith(b"%PDF"):
                    print(f"  not a PDF: {url}")
                    return 1
                sources.append((url, content))

    failed = 0
    for url, raw in sources:
        sha = hashlib.sha256(raw).hexdigest()
        try:
            report = parse_report(pdf_pages(raw))
        except ReportFormatError as exc:
            print(f"REFUSED {url}: {exc}")
            failed += 1
            continue
        kept = out / f"cea_ev_{report.report_month:%Y_%m}_{sha[:8]}.pdf"
        kept.write_bytes(raw)
        india = report.india.month["total_kwh"] if report.india else None
        print(
            f"{report.report_month:%B %Y} "
            f"({f'FY from {report.fy_start:%b %Y}' if report.fy_start else 'month only'}): "
            f"{len(report.states)} states, {len(report.discoms)} DISCOMs, "
            f"India {india / 1e6 if india is not None else '-'} MU this month; "
            f"sha {sha[:12]}; saved {kept.name}"
        )
        for warning in report.warnings:
            print(f"  warning: {warning}")
        if not args.write:
            continue
        from app.db import SessionLocal
        from app.domain.cea.store import store_report

        with SessionLocal() as session:
            result = store_report(session, report, source_url=url, source_sha256=sha)
            session.commit()
        if result.already_stored:
            print("  already stored - skipped")
        else:
            print(f"  stored {result.inserted} rows")
        if result.unmatched_states:
            print(f"  no single LGD state for: {result.unmatched_states}")
    if not args.write:
        print("dry run - nothing stored (pass --write)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
