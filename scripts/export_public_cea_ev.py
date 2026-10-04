"""Write the public CEA EV-charging electricity dataset.

    uv run python -m scripts.export_public_cea_ev --from-archive --write   # what CI runs weekly
    uv run python -m scripts.export_public_cea_ev --write                  # from the database

Publishes, for every report month, the current file's state rows (named as in
the LGD district reference, so the public validator can join them) and the
all-India total, for the month and the financial year to date. DISCOM rows
and lines that are not one LGD state ("UT of J&K and Ladakh", "DVC") are not
published.

Two sources, one output. ``--from-archive`` reads CEA's month archive
directly - it lists the current file for each month, re-issues included - and
needs no database, so the weekly GitHub workflow
(``.github/workflows/refresh-cea-public.yml``) can run it, commit a changed
file and redeploy. Without it, rows come from ``cea_ev_consumption``, newest
fetched file per month. Nothing is written when the data is unchanged, so an
idle week makes no commit.

Exit status 2 means CEA's newest archived report could not be read - a layout
change that needs a human - reported instead of publishing stale figures
silently.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Sequence
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "public" / "cea_ev_consumption"
LISTING = "https://cea.nic.in/electric-vehicle-charging-reports/?lang=en"
POLICY = "https://cea.nic.in/website-policies/?lang=en"
FIELDS = (
    "state",
    "cea_state_name",
    "report_month",
    "span",
    "span_start",
    "pcs_kwh",
    "heavy_duty_pcs_kwh",
    "other_kwh",
    "total_kwh",
    "source_url",
    "source_sha256",
    "notes",
)
_QUERY = """
    WITH latest AS (
      SELECT DISTINCT ON (report_month) report_month, source_sha256
      FROM cea_ev_consumption
      ORDER BY report_month, fetched_at DESC, source_sha256
    )
    SELECT CASE WHEN c.geography = 'india' THEN 'India' ELSE s.name END AS state,
           c.state_name, to_char(c.report_month, 'YYYY-MM') AS report_month, c.span,
           c.span_start, c.pcs_kwh, c.heavy_duty_pcs_kwh, c.other_kwh, c.total_kwh,
           c.source_url, c.source_sha256, c.fetched_at::date AS fetched_on
    FROM cea_ev_consumption c
    JOIN latest l USING (report_month, source_sha256)
    LEFT JOIN states s ON s.lgd_state_code = c.lgd_state_code
    WHERE c.geography = 'india' OR (c.geography = 'state' AND c.lgd_state_code IS NOT NULL)
"""

_COLUMNS = {
    "state": ("not applicable", "LGD state name, or India for CEA's Grand Total"),
    "cea_state_name": ("not applicable", "State as CEA prints it, verbatim"),
    "report_month": ("YYYY-MM", "Month the report is for"),
    "span": ("not applicable", "month: the report month; fy_to_date: April to the report month"),
    "span_start": ("YYYY-MM-DD", "First day the value covers"),
    "pcs_kwh": ("kWh", "Public charging stations excluding heavy duty"),
    "heavy_duty_pcs_kwh": ("kWh", "Heavy-duty public charging stations only"),
    "other_kwh": ("kWh", "EV charging other than public stations; printed from December 2025"),
    "total_kwh": ("kWh", "Total EV charging electricity as printed"),
    "source_url": ("not applicable", "The CEA report PDF this row was read from"),
    "source_sha256": ("not applicable", "SHA-256 of that PDF"),
    "notes": ("not applicable", "Row notes"),
}
_NULLABLE = {"pcs_kwh", "heavy_duty_pcs_kwh", "other_kwh", "total_kwh"}


def _cell(value: object) -> str:
    return "" if value is None else str(value)


def build(rows: list[dict[str, object]]) -> tuple[str, dict[str, object]]:
    """The CSV text and metadata for the rows, deterministic for a given input.

    Rows are sorted here, in Python, so the database and the archive produce
    byte-identical files for the same figures.
    """
    rows = sorted(rows, key=lambda r: (str(r["report_month"]), str(r["span"]), str(r["state"])))
    seen: set[tuple[object, object, object]] = set()
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(FIELDS)
    for row in rows:
        key = (row["state"], row["report_month"], row["span"])
        if key in seen:
            raise SystemExit(f"two CEA lines map to one state-month: {key}")
        seen.add(key)
        writer.writerow(
            [
                row["state"],
                row["state_name"],
                row["report_month"],
                row["span"],
                row["span_start"],
                *(_cell(row[m]) for m in sorted(_NULLABLE, key=FIELDS.index)),
                row["source_url"],
                row["source_sha256"],
                "",
            ]
        )
    months = sorted({str(r["report_month"]) for r in rows})
    newest = max(rows, key=lambda r: (str(r["report_month"]), str(r["fetched_on"])))
    meta: dict[str, object] = {
        "id": "cea_ev_consumption",
        "title": "Electricity used by EV charging, by state (CEA)",
        "description": (
            "Monthly electricity consumed by EV charging in each state and in India, as DISCOMs "
            "report it to the Central Electricity Authority: public stations, heavy-duty public "
            "stations and other EV charging, for the month and the financial year to date"
        ),
        "source_name": (
            "Central Electricity Authority (CEA), Ministry of Power, Government of India"
        ),
        "source_url": LISTING,
        "retrieved_on": str(max(r["fetched_on"] for r in rows)),
        "licence": (
            "Government of India publication; CEA publishes no reuse licence. Reproduced "
            "unaltered with attribution (Chargeworthy publication decision, 2026-10-03)"
        ),
        "licence_url": POLICY,
        "attribution": (
            "Source: Central Electricity Authority, Ministry of Power, Government of India - "
            "Electric Vehicles Public Charging Stations Monthly Power Consumption Report"
        ),
        "geography_level": "state",
        "time_coverage": (
            f"Report months {months[0]} to {months[-1]}; {len(months)} months. Missing: "
            "Nov 2024 - Jun 2025 (tables published as images) and months CEA did not publish"
        ),
        "update_frequency": (
            "Checked weekly; CEA publishes irregularly, about 2-5 months after the month"
        ),
        "notes": (
            "Values are kWh, exact to 10,000 kWh (CEA prints MU to 0.01). Blank means the "
            "utility did not report, never zero. Reports to Nov 2025 have no 'other' column; "
            "Apr 2024 has no year-to-date figures. Coverage grows over time (17 states in mid "
            "2024, 33 in 2026), so state totals are not comparable across that change. Where a "
            "month was re-issued the newest file is used. DISCOM rows and lines covering more "
            "than one state stay out of this file. Provisional, as reported by DISCOMs."
        ),
        "columns": [
            {
                "name": name,
                "type": {
                    "report_month": "month",
                    "span_start": "date",
                    **dict.fromkeys(_NULLABLE, "integer"),
                }.get(name, "string"),
                "unit": unit,
                "description": description,
                **({"nullable": True} if name in _NULLABLE else {}),
            }
            for name, (unit, description) in _COLUMNS.items()
        ],
        "source_sha256": newest["source_sha256"],
        "review_ref": "docs/analytics/CEA_EV_CONSUMPTION.md",
        "transformation_version": "cea_ev_report_parse_v1",
    }
    return buffer.getvalue(), meta


def rows_from_reports(
    reports: Sequence[tuple[str, str, object]], lgd_states: set[str], fetched_on: str
) -> list[dict[str, object]]:
    """Rows in the database query's shape, from parsed reports (no database).

    ``reports`` is (source URL, PDF sha256, parsed Report); ``lgd_states`` the
    district reference's state names. A CEA line that is not one LGD state is
    left out, as in the database export.
    """
    from app.domain.cea.parse import SPANS, Report, lgd_state_code

    names = {name: name for name in lgd_states}
    out: list[dict[str, object]] = []
    for url, sha, parsed in reports:
        assert isinstance(parsed, Report)
        lines = [*parsed.states, *([parsed.india] if parsed.india else [])]
        for line in lines:
            state = "India" if line.geography == "india" else lgd_state_code(line.state_name, names)
            if state is None:
                continue
            for span in SPANS:
                values = getattr(line, span)
                start = parsed.report_month if span == "month" else parsed.fy_start
                if values is None or start is None:
                    continue
                out.append(
                    {
                        "state": state,
                        "state_name": line.state_name,
                        "report_month": f"{parsed.report_month:%Y-%m}",
                        "span": span,
                        "span_start": start.isoformat(),
                        **values,
                        "source_url": url,
                        "source_sha256": sha,
                        "fetched_on": fetched_on,
                    }
                )
    return out


def _lgd_states() -> set[str]:
    reference = OUT.parent / "district_reference" / "data.csv"
    with reference.open(encoding="utf-8", newline="") as stream:
        return {row["state_name"] for row in csv.DictReader(stream)}


def _from_archive(start: str) -> tuple[list[dict[str, object]], bool]:
    """Rows from CEA's archive, and whether the newest archived report was read."""
    import datetime as dt
    import hashlib

    import httpx

    from app.domain.cea.parse import ReportFormatError, parse_report
    from scripts.fetch_cea_ev import HEADERS, archived_reports, months_back, pdf_pages

    parsed: list[tuple[str, str, object]] = []
    newest_ok = True
    with httpx.Client(timeout=120, headers=HEADERS, follow_redirects=True) as client:
        urls = archived_reports(client, months_back(dt.date.today(), 0, start))
        for index, url in enumerate(urls):
            raw = client.get(url).raise_for_status().content
            try:
                report = parse_report(pdf_pages(raw))
            except ReportFormatError as exc:
                print(f"skipped {url}: {exc}")
                if index == len(urls) - 1:
                    newest_ok = False
                continue
            parsed.append((url, hashlib.sha256(raw).hexdigest(), report))
    return rows_from_reports(parsed, _lgd_states(), dt.date.today().isoformat()), newest_ok


def _from_database() -> list[dict[str, object]]:
    from sqlalchemy import text

    from app.db import SessionLocal

    with SessionLocal() as session:
        return [dict(r._mapping) for r in session.execute(text(_QUERY))]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--write", action="store_true", help="write changed files (default: dry run)")
    p.add_argument("--from-archive", action="store_true", help="read CEA directly, no database")
    p.add_argument("--from", dest="start", default="2022-08", help="first archive month YYYY-MM")
    args = p.parse_args()
    newest_ok = True
    if args.from_archive:
        rows, newest_ok = _from_archive(args.start)
    else:
        rows = _from_database()
    if not rows:
        print("no CEA rows found")
        return 1
    data, meta = build(rows)
    path = OUT / "data.csv"
    old = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""
    changed = old != data
    print(f"{len(rows)} rows, {meta['time_coverage']}")
    print(f"data.csv {'changes' if changed else 'unchanged'} ({len(old)} -> {len(data)} bytes)")
    if args.write and changed:
        OUT.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8", newline="")
        meta_text = json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
        (OUT / "meta.json").write_text(meta_text, encoding="utf-8", newline="")
        print(f"wrote {OUT}")
    if not newest_ok:
        print("ERROR: CEA's newest archived report could not be read - check its layout")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
