"""Populate district_name_crosswalk - PART 1.2.

    uv run python -m scripts.build_crosswalk --seed-aliases
    uv run python -m scripts.build_crosswalk --dataset vahan --csv names.csv
    uv run python -m scripts.build_crosswalk --report

The CSV form takes two columns, ``state`` and ``district``, as some other
dataset spells them, and proposes an LGD code for each. VAHAN exports, tariff
order annexures and census extracts all arrive in roughly that shape.

**Nothing here sets ``verified_by``.** PLAN 1.2 asks for a hand-built table
for six states and calls the failure mode out: a wrong district misattributes
every downstream number silently. So the machine narrows the work - exact and
alias matches need no thought - and a human signs off the rest. ``--report``
is the queue.

Existing rows are never overwritten once verified: re-running after a human
has been through the list must not quietly undo their decisions.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.domain.resolution.crosswalk import (
    DISTRICT_ALIASES,
    Candidate,
    Match,
    match_district,
    normalise_name,
)


def _candidates(session: Session) -> list[Candidate]:
    rows = session.execute(text("SELECT lgd_district_code, name, state_name FROM districts")).all()
    if not rows:
        raise SystemExit(
            "no districts loaded. Run scripts.fetch_reference and scripts.load_reference first."
        )
    return [Candidate(int(r[0]), r[1], r[2]) for r in rows]


def _upsert(session: Session, dataset: str, state: str, name: str, match: Match) -> str:
    """Write one proposal, leaving any human verdict intact."""
    session.execute(
        text(
            """
            INSERT INTO district_name_crosswalk
                (source_name, source_state, source_dataset, lgd_district_code,
                 match_method, match_score, note)
            VALUES (:name, :state, :dataset, :code, :method, :score, :note)
            ON CONFLICT (source_dataset, source_state, source_name) DO UPDATE SET
                lgd_district_code = EXCLUDED.lgd_district_code,
                match_method = EXCLUDED.match_method,
                match_score = EXCLUDED.match_score,
                note = EXCLUDED.note
            -- A row someone has verified is theirs. Re-running the matcher
            -- must not silently overturn a human decision.
            WHERE district_name_crosswalk.verified_by IS NULL
            """
        ),
        {
            "name": name,
            "state": state,
            "dataset": dataset,
            "code": match.lgd_district_code,
            "method": match.method,
            "score": match.score,
            "note": match.note,
        },
    )
    return match.method


def seed_aliases(session: Session) -> dict[str, int]:
    """Enter every hand-written alias against the districts actually loaded.

    This is the part with immediate value: a tariff order that says
    "Trivandrum" resolves today, without waiting for anyone to review a list.
    Aliases are hand-written by definition, so the rows they produce are the
    ones the matcher is entitled to be confident about.
    """
    candidates = _candidates(session)
    by_state: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        by_state.setdefault(candidate.state_name, []).append(candidate)

    counts: dict[str, int] = {}
    for alias in DISTRICT_ALIASES:
        for state_name, in_state in by_state.items():
            match = match_district(alias, state_name, in_state)
            # Only record the alias where it actually lands. "Trivandrum" is
            # meaningless in Bihar and a row saying so is noise.
            if match.lgd_district_code is None:
                continue
            method = _upsert(session, "aliases", state_name, alias, match)
            counts[method] = counts.get(method, 0) + 1
    return counts


def from_csv(session: Session, dataset: str, path: pathlib.Path) -> dict[str, int]:
    candidates = _candidates(session)
    counts: dict[str, int] = {}

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = {"state", "district"} - {(f or "").lower() for f in (reader.fieldnames or [])}
        if missing:
            raise SystemExit(f"{path}: missing column(s) {', '.join(sorted(missing))}")

        for row in reader:
            lowered = {(k or "").lower(): (v or "").strip() for k, v in row.items()}
            state, district = lowered["state"], lowered["district"]
            if not state or not district or not normalise_name(district):
                continue
            match = match_district(district, state, candidates)
            method = _upsert(session, dataset, state, district, match)
            counts[method] = counts.get(method, 0) + 1
    return counts


def report(session: Session) -> None:
    rows = session.execute(
        text(
            """
            SELECT source_dataset, match_method,
                   count(*) FILTER (WHERE verified_by IS NULL) AS unverified,
                   count(*) AS total
            FROM district_name_crosswalk
            GROUP BY source_dataset, match_method
            ORDER BY source_dataset, match_method
            """
        )
    ).all()
    if not rows:
        print("crosswalk is empty")
        return

    print(f"{'dataset':<14}{'method':<12}{'unverified':>12}{'total':>8}")
    for dataset, method, unverified, total in rows:
        print(f"{dataset:<14}{method:<12}{unverified:>12}{total:>8}")

    queue = session.execute(
        text(
            """
            SELECT source_state, source_name, match_method, match_score, note
            FROM district_name_crosswalk
            WHERE verified_by IS NULL AND match_method IN ('fuzzy', 'unresolved')
            ORDER BY match_method, source_state, source_name
            LIMIT 40
            """
        )
    ).all()
    if queue:
        print(f"\nNeeds a human ({len(queue)} shown):")
        for state, name, method, score, note in queue:
            print(f"  [{method:<10}] {state:<24}{name:<28}{score or '':>4}  {note or ''}")
        print(
            "\nSet verified_by (and lgd_district_code, if the proposal is wrong) by hand.\n"
            "Nothing in the codebase writes that column - that is the point of it."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build district_name_crosswalk (PLAN 1.2)")
    parser.add_argument(
        "--seed-aliases", action="store_true", help="enter the hand-written aliases"
    )
    parser.add_argument("--dataset", help="name of the foreign dataset, e.g. vahan")
    parser.add_argument("--csv", type=pathlib.Path, help="CSV with columns: state, district")
    parser.add_argument("--report", action="store_true", help="show coverage + the review queue")
    args = parser.parse_args(argv)

    if not (args.seed_aliases or args.csv or args.report):
        parser.print_help()
        return 2
    if bool(args.csv) != bool(args.dataset):
        print("--csv and --dataset go together")
        return 2

    with SessionLocal() as session:
        if args.seed_aliases:
            counts = seed_aliases(session)
            session.commit()
            print("aliases:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none")

        if args.csv:
            if not args.csv.exists():
                print(f"{args.csv}: not found")
                return 1
            counts = from_csv(session, args.dataset, args.csv)
            session.commit()
            print(
                f"{args.dataset}:",
                ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none",
            )

        if args.report:
            report(session)

    return 0


if __name__ == "__main__":
    sys.exit(main())
