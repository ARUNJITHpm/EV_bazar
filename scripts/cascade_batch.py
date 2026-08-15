"""Run a batch of real addresses through the whole of Part 1 - the exit criteria.

    uv run python -m scripts.cascade_batch addresses.txt
    uv run python -m scripts.cascade_batch addresses.csv --out verify.csv --write

Part 1's exit criteria are five numbers, and this prints all five:

    200 real charging-station addresses (KL + TN) run through the cascade
    >= 95%  resolve to a district code
    >= 90%  resolve without touching Google
    100%    of resolved districts correct  -- BY HAND, from --out
    median cascade cost per address = Rs 0

The fourth cannot be automated and is not pretended to be: the script writes a
CSV with the input, the matched address, the district and the coordinates, and
a human checks all 200. PLAN Part 1 calls that "the only cheap ground truth
you'll ever get", and a script that graded its own homework would throw it away.

Input is one address per line, or a CSV whose first column is the address (a
second column, if present, is read as the expected district and *reported*, not
asserted). Blank lines and lines starting with ``#`` are skipped.

Cost is measured, not assumed: the ``api_usage_events`` total is read before and
after each address, so the median is the real per-address spend including the
addresses that reached a paid level.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.domain.resolution import manual
from app.domain.resolution.cascade import build_cascade
from app.domain.resolution.geocode import GeocodeStatus, geocode
from app.domain.resolution.geography import resolve
from app.models.api_usage import ApiUsageEvent

#: Reaching this level is what the "≥90% without Google" criterion counts.
GOOGLE = "google_maps"


@dataclass
class Row:
    raw: str
    expected: str | None
    status: str
    source: str | None
    lat: float | None
    lng: float | None
    matched: str | None
    district: str | None
    lgd_district_code: int | None
    state: str | None
    method: str | None
    confidence: str | None
    boundary_ambiguous: bool
    cost_paise: int
    used_google: bool
    reasons: str


def read_addresses(path: Path) -> list[tuple[str, str | None]]:
    text = path.read_text(encoding="utf-8-sig")
    out: list[tuple[str, str | None]] = []
    if path.suffix.lower() == ".csv":
        for record in csv.reader(text.splitlines()):
            if not record or not record[0].strip() or record[0].lstrip().startswith("#"):
                continue
            expected = record[1].strip() if len(record) > 1 and record[1].strip() else None
            out.append((record[0].strip(), expected))
        return out

    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            out.append((stripped, None))
    return out


def _spend(session: Session) -> int:
    stmt = select(func.coalesce(func.sum(ApiUsageEvent.cost_paise), 0)).where(
        ApiUsageEvent.operation == "geocode"
    )
    return int(session.execute(stmt).scalar_one())


def _paid_calls(session: Session, provider: str) -> int:
    stmt = (
        select(func.count())
        .select_from(ApiUsageEvent)
        .where(ApiUsageEvent.operation == "geocode", ApiUsageEvent.provider == provider)
    )
    return int(session.execute(stmt).scalar_one())


def run(path: Path, *, limit: int | None, write: bool, use_cache: bool) -> tuple[list[Row], int]:
    settings = get_settings()
    addresses = read_addresses(path)
    if limit:
        addresses = addresses[:limit]

    rows: list[Row] = []
    with SessionLocal() as session, httpx.Client() as client:
        geocoders = build_cascade(session, settings)
        print(f"cascade: {' -> '.join(g.source for g in geocoders)}")
        print(f"addresses: {len(addresses)}\n")

        for raw, expected in addresses:
            before_spend = _spend(session)
            before_google = _paid_calls(session, GOOGLE)

            outcome = geocode(session, raw, geocoders=geocoders, client=client, use_cache=use_cache)

            row = Row(
                raw=raw,
                expected=expected,
                status=str(outcome.status),
                source=outcome.source,
                lat=outcome.lat,
                lng=outcome.lng,
                matched=outcome.display_name,
                district=None,
                lgd_district_code=None,
                state=None,
                method=None,
                confidence=str(outcome.confidence) if outcome.confidence else None,
                boundary_ambiguous=False,
                cost_paise=_spend(session) - before_spend,
                used_google=_paid_calls(session, GOOGLE) > before_google,
                reasons=" | ".join(outcome.reasons),
            )

            if outcome.status is GeocodeStatus.MISS:
                # The refusal is the signal that feeds L6 (PLAN 1.3).
                manual.enqueue(session, outcome)
            elif outcome.lat is not None and outcome.lng is not None:
                # PART 1.4 - the coordinate is only useful if it lands in a district.
                district = resolve(
                    session,
                    outcome.lat,
                    outcome.lng,
                    expected_pincode=outcome.normalised.pincode,
                )
                row.method = str(district.method)
                row.boundary_ambiguous = district.boundary_ambiguous
                if district.district is not None:
                    row.district = district.district.name
                    row.lgd_district_code = district.district.lgd_district_code
                    row.state = district.district.state_name
                row.reasons += " || " + " | ".join(district.reasons)

            rows.append(row)
            flag = "OK " if row.lgd_district_code else "XX "
            print(f"  {flag} {raw[:48]:<48} -> {str(row.district):<20} {row.status}")

        if write:
            session.commit()
        else:
            session.rollback()

    return rows, len(addresses)


def report(rows: list[Row]) -> int:
    total = len(rows)
    if not total:
        print("no addresses read")
        return 2

    to_district = sum(1 for r in rows if r.lgd_district_code is not None)
    without_google = sum(1 for r in rows if not r.used_google)
    costs = [r.cost_paise for r in rows]
    median = statistics.median(costs)
    ambiguous = sum(1 for r in rows if r.boundary_ambiguous)
    escalated = [r for r in rows if r.used_google]

    def pct(n: int) -> float:
        return 100.0 * n / total

    print("\n--- PART 1 exit criteria ------------------------------------------")
    checks = [
        (total >= 200, f"addresses run                {total:>6}          (want >= 200)"),
        (
            pct(to_district) >= 95,
            f"resolved to a district       {pct(to_district):>5.1f}%  "
            f"{to_district}/{total}  (want >= 95%)",
        ),
        (
            pct(without_google) >= 90,
            f"resolved without Google      {pct(without_google):>5.1f}%  "
            f"{without_google}/{total}  (want >= 90%)",
        ),
        (median == 0, f"median cost per address      {median / 100:>6.2f} Rs      (want 0.00)"),
    ]
    for ok, line in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {line}")

    print(f"\n  ----  total spend            {sum(costs) / 100:>6.2f} Rs")
    print(f"  ----  boundary-ambiguous     {ambiguous:>6}          (report must say so)")
    print(f"  MANUAL  100% of districts correct - verify all {total} by hand from the CSV")

    if escalated:
        print(
            f"\n{len(escalated)} address(es) reached Google. PLAN Part 1: every one of these is "
            "reviewed and the finding written into the normalisation backlog:"
        )
        for r in escalated[:20]:
            print(f"  - {r.raw}")

    return 0 if all(ok for ok, _ in checks) else 1


def write_csv(rows: list[Row], out: Path) -> None:
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "raw_input",
                "expected_district",
                "status",
                "geocode_source",
                "lat",
                "lng",
                "matched_address",
                "district",
                "lgd_district_code",
                "state",
                "method",
                "confidence",
                "boundary_ambiguous",
                "cost_paise",
                "used_google",
                # The column a human fills in. Left empty on purpose.
                "correct_y_n",
                "reasons",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r.raw,
                    r.expected or "",
                    r.status,
                    r.source or "",
                    r.lat if r.lat is not None else "",
                    r.lng if r.lng is not None else "",
                    r.matched or "",
                    r.district or "",
                    r.lgd_district_code or "",
                    r.state or "",
                    r.method or "",
                    r.confidence or "",
                    "yes" if r.boundary_ambiguous else "",
                    r.cost_paise,
                    "yes" if r.used_google else "",
                    "",
                    r.reasons,
                ]
            )
    print(f"\nwrote {out} - verify the district column by hand, all {len(rows)} rows")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Part 1 exit criteria over a batch of addresses")
    parser.add_argument("path", type=Path, help="one address per line, or CSV")
    parser.add_argument("--out", type=Path, default=Path("cascade_batch.csv"))
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--write",
        action="store_true",
        help="commit the cache, usage events and manual-queue rows (default: roll back)",
    )
    parser.add_argument("--no-cache", action="store_true", help="force every level, ignore L1")
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"no such file: {args.path}", file=sys.stderr)
        return 2

    rows, _ = run(args.path, limit=args.limit, write=args.write, use_cache=not args.no_cache)
    write_csv(rows, args.out)
    return report(rows)


if __name__ == "__main__":
    sys.exit(main())
