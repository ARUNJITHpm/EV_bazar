"""Fetch CEA's monthly EV charging electricity reports and store new ones.

    uv run python -m scripts.fetch_cea_ev                      # check the listing, dry run
    uv run python -m scripts.fetch_cea_ev --write              # store any new report
    uv run python -m scripts.fetch_cea_ev --url <pdf> --write  # backfill one known report
    uv run python -m scripts.fetch_cea_ev --file report.pdf    # parse a local copy, dry run

CEA publishes "EV Public Charging Stations Monthly Power Consumption Report"
about monthly, 2-5 months after the month (March 2026 appeared in August
2026). The listing page shows only the newest report, so this runs weekly and
stores whatever it has not seen; an older month is backfilled with ``--url``.
Every report also carries financial-year-to-date totals, so a month whose own
report was never fetched can still be recovered from two neighbours.

Each PDF is saved under ``--out`` (default ``data/cea_ev/``) before it is
parsed, so the stored figures always have their source file beside them.
Without ``--write`` nothing touches the database.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import sys
from pathlib import Path

import httpx

LISTING = "https://cea.nic.in/electric-vehicle-charging-reports/?lang=en"
_PDF = re.compile(r"https://cea\.nic\.in/wp-content/uploads/ev_charging_rep/[^\"'\s<>]+\.pdf")
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "cea_ev"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Chargeworthy data refresh)"}


def listed_reports(client: httpx.Client) -> list[str]:
    """Report PDF URLs on the listing page, in page order, without repeats."""
    page = client.get(LISTING)
    page.raise_for_status()
    return list(dict.fromkeys(_PDF.findall(page.text)))


def pdf_pages(raw: bytes) -> list[str]:
    from pypdf import PdfReader  # noqa: PLC0415 - only this script needs it

    return [page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages]


def main() -> int:
    from app.domain.cea.parse import ReportFormatError, parse_report

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--url", action="append", default=[], help="a report PDF URL (repeatable)")
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
            urls = args.url or listed_reports(client)
            print(f"{len(urls)} report(s): {urls}")
            for url in urls:
                response = client.get(url)
                response.raise_for_status()
                if not response.content.startswith(b"%PDF"):
                    print(f"  not a PDF: {url}")
                    return 1
                sources.append((url, response.content))

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
            f"{report.report_month:%B %Y} (FY from {report.fy_start:%b %Y}): "
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
