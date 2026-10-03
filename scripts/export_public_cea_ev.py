"""Write the public CEA EV-charging electricity dataset from the database.

    uv run python -m scripts.export_public_cea_ev            # dry run: print what would change
    uv run python -m scripts.export_public_cea_ev --write    # write data/public/cea_ev_consumption/

Publishes, for every report month stored by ``scripts.fetch_cea_ev``, the
most recently fetched file's state rows (named as in the LGD district
reference, so the public validator can join them) and the all-India total,
for the month and the financial year to date. DISCOM rows and lines that are
not one LGD state ("UT of J&K and Ladakh", "DVC") stay in the database only.

The public build validates the result like any other source; this script
never edits the validator's rules. Re-run it after a new report is stored,
then commit the two files - the site is static, so new figures go live with
the next deploy.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

from sqlalchemy import text

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
_QUERY = text(
    """
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
    ORDER BY c.report_month, c.span, state
    """
)

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
    """The CSV text and metadata for the rows, deterministic for a given input."""
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


def main() -> int:
    from app.db import SessionLocal

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--write", action="store_true", help="write the files (default: dry run)")
    args = p.parse_args()
    with SessionLocal() as session:
        rows = [dict(r._mapping) for r in session.execute(_QUERY)]
    if not rows:
        print("no CEA rows stored - run scripts.fetch_cea_ev --write first")
        return 1
    data, meta = build(rows)
    meta_text = json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
    old = (OUT / "data.csv").read_text(encoding="utf-8") if (OUT / "data.csv").exists() else ""
    print(f"{len(rows)} rows, {meta['time_coverage']}")
    print("unchanged" if old == data else f"data.csv changes ({len(old)} -> {len(data)} bytes)")
    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "data.csv").write_text(data, encoding="utf-8", newline="")
        (OUT / "meta.json").write_text(meta_text, encoding="utf-8", newline="")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
