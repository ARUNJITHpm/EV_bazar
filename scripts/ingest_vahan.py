"""Ingest a VAHAN scrape CSV into the database - PART 4.1.

    uv run python -m scripts.ingest_vahan --csv data/vahan/scrape_20260815.csv --write

Reads the long CSV that ``scripts.scrape_vahan`` produced, resolves every RTO's
office coordinate to its district, sums the counts into districts, and upserts
one snapshot. The CSV's sha256 is stamped on every row as provenance, so a
figure can always be traced back to the exact capture behind it.

The scrape and this ingest are separate on purpose: the CSV is the vintaged
artifact (slow, irreplaceable), and writing it to the database is fast and
repeatable. ``--snapshot-date`` defaults to today - the capture vintage, since
VAHAN itself carries no as-of date.

Without ``--write`` it resolves and aggregates and prints the summary, touching
nothing - the safe way to see what a CSV would produce.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
from pathlib import Path

from app.db import SessionLocal
from app.domain.vahan.parse import parse_vahan_csv
from app.domain.vahan.store import RtoRef, ingest

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "vahan"
SEED = DATA_DIR / "rto_reference.csv"


def resolve_csv(value: str) -> Path:
    """A path, or the literal "latest" for the newest scrape in data/vahan/.

    The scheduled job scrapes to a dated file and then ingests "latest", so the
    two steps need not agree on a filename.
    """
    if value == "latest":
        scrapes = sorted(DATA_DIR.glob("scrape_*.csv"))
        if not scrapes:
            raise SystemExit(f"no scrape_*.csv found in {DATA_DIR}")
        return scrapes[-1]
    return Path(value)


def load_refs() -> list[RtoRef]:
    with SEED.open(newline="", encoding="utf-8") as fh:
        out = []
        for r in csv.DictReader(fh):
            lat = r.get("lat") or ""
            lng = r.get("lng") or ""
            out.append(
                RtoRef(
                    state_code=r["state_code"],
                    rto=r["rto"],
                    lat=float(lat) if lat else None,
                    lng=float(lng) if lng else None,
                )
            )
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest a VAHAN scrape CSV (PLAN 4.1)")
    p.add_argument("--csv", required=True, help='the long scrape CSV, or "latest"')
    p.add_argument("--snapshot-date", default="", help="YYYY-MM-DD; default today (capture date)")
    p.add_argument("--write", action="store_true", help="commit; without it, dry aggregate only")
    args = p.parse_args()

    csv_path = resolve_csv(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"no such file: {csv_path}")
    print(f"reading {csv_path}")

    raw = csv_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    counts = parse_vahan_csv(raw.decode("utf-8"))
    refs = load_refs()

    snapshot = (
        dt.date.fromisoformat(args.snapshot_date) if args.snapshot_date else dt.date.today()
    )

    periods = sorted({c.period for c in counts})
    print(f"{len(counts):,} count rows, {len(refs)} RTOs, periods {periods}")
    print(f"snapshot_date={snapshot}  source_sha256={sha[:12]}...")

    with SessionLocal() as session:
        result = ingest(
            session,
            counts,
            refs,
            snapshot_date=snapshot,
            source_sha256=sha,
            resolve_districts=True,
        )
        if args.write:
            session.commit()
            print("committed.")
        else:
            session.rollback()
            print("dry run - rolled back (pass --write to commit).")

    print(
        f"RTOs placed {result.placed}/{result.rtos} "
        f"(unplaced {result.unplaced}); "
        f"{result.slices} district slices: inserted {result.inserted}, updated {result.updated}"
    )


if __name__ == "__main__":
    main()
