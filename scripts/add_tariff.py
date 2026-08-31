"""Add a state's electricity tariff, safely - PART 3.1's entry path.

    uv run python -m scripts.add_tariff --template            # print a blank row
    uv run python -m scripts.add_tariff --file karnataka.json  # dry run: show the plan
    uv run python -m scripts.add_tariff --file karnataka.json --write

``seed_tariffs.py`` seeded Kerala and Tamil Nadu as reviewable literals; this is
the tool for the NEXT state and for revisions. You fill one JSON file with the
figures read off the SERC order (money as INTEGER PAISE - the preview echoes it
back in rupees so you can check it against the PDF), and the tool:

  * validates the row against the table's constraints, in plain language;
  * works out whether it is a clean insert or a SUPERSESSION of the current
    order (which it closes at the new start date - never edits, never deletes),
    and REFUSES anything that overlaps history ambiguously;
  * previews the breakeven a default site in that state would get; and
  * on --write, applies the whole file in ONE transaction and prints the state's
    new coverage tier - the "it worked" signal (a first tariff flips Tier 3 → 2,
    so /assess starts answering instead of waitlisting).

The planning itself is ``app/domain/tariffs/entry.py`` - pure and tested. This
script is only the shell that reads the file and talks to the database.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db import SessionLocal
from app.domain.report.teaser import Taps, compute_teaser
from app.domain.resolution.coverage import state_tier
from app.domain.tariffs import Action, InsertionPlan, plan_insertion
from app.domain.tariffs.select import is_effective
from app.models.tariffs import ElectricityTariff

#: Required in every row; the rest default the way the table does.
_REQUIRED = (
    "lgd_state_code",
    "consumer_category",
    "energy_paise_per_kwh",
    "effective_from",
    "order_number",
    "source_pdf",
)

_TEMPLATE_JSON = json.dumps(
    [
        {
            "lgd_state_code": 29,
            "discom": "BESCOM",
            "consumer_category": "LT EV Charging Stations",
            "ev_specific": True,
            "energy_paise_per_kwh": 700,
            "demand_paise_per_kva_month": 0,
            "fixed_paise_per_month": 0,
            "duty_bp": 0,
            "tod_bands": None,
            "effective_from": "2025-04-01",
            "effective_to": None,
            "order_number": "KERC Order dated ..., category ...",
            "source_pdf": "https://... the order PDF or its public mirror",
            "note": "Confidence + what the gazette leaves open. UNVERIFIED until a real bill.",
        }
    ],
    indent=2,
)


def _to_row(raw: dict[str, Any]) -> ElectricityTariff:
    missing = [k for k in _REQUIRED if raw.get(k) in (None, "")]
    if missing:
        raise ValueError(f"row missing required field(s): {', '.join(missing)}")

    def date(key: str) -> dt.date | None:
        value = raw.get(key)
        return dt.date.fromisoformat(value) if value else None

    return ElectricityTariff(
        lgd_state_code=int(raw["lgd_state_code"]),
        discom=raw.get("discom"),
        consumer_category=str(raw["consumer_category"]),
        ev_specific=bool(raw.get("ev_specific", True)),
        energy_paise_per_kwh=int(raw["energy_paise_per_kwh"]),
        demand_paise_per_kva_month=int(raw.get("demand_paise_per_kva_month", 0)),
        fixed_paise_per_month=int(raw.get("fixed_paise_per_month", 0)),
        duty_bp=int(raw.get("duty_bp", 0)),
        tod_bands=raw.get("tod_bands") or None,
        effective_from=date("effective_from"),
        effective_to=date("effective_to"),
        order_number=str(raw["order_number"]),
        source_pdf=str(raw["source_pdf"]),
        note=raw.get("note"),
    )


def parse_rows(data: Any) -> list[ElectricityTariff]:
    """JSON (a list of row objects, or a single object) -> candidate rows.

    Pure and DB-free. Structural problems - a non-object, a missing required
    field, an unparseable date - raise here with a readable message rather than
    surfacing as an IntegrityError three steps later.
    """
    rows = data if isinstance(data, list) else [data]
    if not rows:
        raise ValueError("no rows in the file")
    out: list[ElectricityTariff] = []
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise ValueError(f"row {i} is not a JSON object")
        try:
            out.append(_to_row(raw))
        except (ValueError, TypeError) as e:
            raise ValueError(f"row {i}: {e}") from None
    return out


def _rupees(paise: int) -> str:
    return f"₹{paise / 100:,.2f}"


def _breakeven_line(candidate: ElectricityTariff, on: dt.date) -> str:
    """What a default site in this state would be told, if this row governs
    ``on`` - the tangible payoff of adding it. Uses the same pure teaser
    arithmetic /assess serves, so the preview cannot drift from the product."""
    if not candidate.ev_specific:
        return "    (not an EV-specific tariff - the teaser prices off the EV row, not this one)"
    if not is_effective(candidate, on):
        return f"    (historical row - not the order governing {on}; no live breakeven to show)"
    teaser = compute_teaser(candidate, Taps())
    if teaser.utilisation is None:
        return "    sample breakeven: none - margin is negative at the assumed selling price"
    return (
        f"    sample breakeven: a default {teaser.connectors}-connector site must clear "
        f"{teaser.utilisation * 100:.1f}% utilisation"
    )


def render_plan(plan: InsertionPlan, *, on: dt.date) -> str:
    """One plan as text: the verdict, the row in rupees, the reason, and - for a
    row that will govern ``on`` - the breakeven it implies. Pure."""
    c = plan.candidate
    verdict = {
        Action.INSERT: "INSERT",
        Action.SUPERSEDE: "SUPERSEDE",
        Action.DUPLICATE: "skip (duplicate)",
        Action.REFUSE: "REFUSE",
        Action.INVALID: "INVALID",
    }[plan.action]

    window = f"{c.effective_from} - {c.effective_to or 'open'}"
    money = f"energy {_rupees(c.energy_paise_per_kwh)}/kWh"
    if c.demand_paise_per_kva_month:
        money += f", demand {_rupees(c.demand_paise_per_kva_month)}/kVA-month"
    if c.fixed_paise_per_month:
        money += f", fixed {_rupees(c.fixed_paise_per_month)}/month"
    if c.duty_bp:
        money += f", duty {c.duty_bp / 100:.2f}%"

    lines = [
        f"[{verdict}] state {c.lgd_state_code} / {c.discom or '(default discom)'} / "
        f"{c.consumer_category}",
        f"    {window}   {money}",
        f"    why: {plan.reason}",
    ]
    if plan.action in (Action.INSERT, Action.SUPERSEDE, Action.DUPLICATE):
        lines.append(_breakeven_line(c, on))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add a state's EV tariff safely (PLAN 3.1)")
    parser.add_argument("--file", help="a JSON file: a list of tariff rows (see --template)")
    parser.add_argument("--template", action="store_true", help="print a blank row and exit")
    parser.add_argument("--write", action="store_true", help="apply the plans (default: dry run)")
    parser.add_argument("--on", help="preview date YYYY-MM-DD for the breakeven (default: today)")
    args = parser.parse_args(argv)

    if args.template:
        print(_TEMPLATE_JSON)
        return 0
    if not args.file:
        parser.error("give --file PATH (a JSON list of tariff rows), or --template")

    on = dt.date.fromisoformat(args.on) if args.on else dt.date.today()
    try:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        candidates = parse_rows(data)
    except (OSError, ValueError) as e:
        print(f"Could not read {args.file}: {e}")
        return 2

    with SessionLocal() as session:
        # Existing rows per state, fetched once; in-batch writable candidates are
        # folded in so a file that supersedes then re-supersedes plans correctly.
        db_rows: dict[int, list[ElectricityTariff]] = {}
        planned: dict[int, list[ElectricityTariff]] = {}
        plans: list[InsertionPlan] = []

        for cand in candidates:
            code = cand.lgd_state_code
            if code not in db_rows:
                db_rows[code] = list(
                    session.execute(
                        select(ElectricityTariff).where(ElectricityTariff.lgd_state_code == code)
                    )
                    .scalars()
                    .all()
                )
                planned[code] = []
            plan = plan_insertion(db_rows[code] + planned[code], cand)
            plans.append(plan)
            if plan.writable:
                planned[code].append(cand)
            print(render_plan(plan, on=on))
            print()

        blockers = [p for p in plans if p.action in (Action.INVALID, Action.REFUSE)]
        if blockers:
            print(f"{len(blockers)} row(s) cannot be added - NOTHING written. Fix them and re-run.")
            return 1

        if not args.write:
            print("Dry run - re-run with --write to apply the plans above.")
            return 0

        applied = skipped = 0
        affected: set[int] = set()
        for plan in plans:
            if plan.action is Action.DUPLICATE:
                skipped += 1
                continue
            if plan.action is Action.SUPERSEDE and plan.supersedes is not None:
                plan.supersedes.effective_to = plan.close_prior_at
            session.add(plan.candidate)
            affected.add(plan.candidate.lgd_state_code)
            applied += 1
        session.commit()

        print(f"Wrote {applied} row(s); skipped {skipped} duplicate(s).")
        for code in sorted(affected):
            verdict = state_tier(session, code)
            print(f"  state {code}: now Tier {verdict.tier} - {verdict.why}")
    print("\nEvery row is UNVERIFIED against a real bill (PLAN 3.3) - see each row's note.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
