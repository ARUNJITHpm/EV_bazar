"""Seed the effective-dated price cards - PART C.1.

    uv run python -m scripts.seed_price_cards          # show what would change
    uv run python -m scripts.seed_price_cards --write

Run this **before** configuring any paid API key: ``build_cascade`` refuses to
assemble a paid level that has no card, on the grounds that a call which cannot
be priced will not appear in the spend report at its real cost.

Idempotent, and it never updates a row. Superseding a price means adding a new
card with a new version and closing the old one's date range - the same rule as
the SERC tariff table, and for the same reason: last March's cost must still
recompute to last March's price.
"""

from __future__ import annotations

import argparse
import sys

from app.db import SessionLocal
from app.metering.cards import GEOCODING_CARDS, seed_price_cards


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed provider price cards (PLAN C.1)")
    parser.add_argument("--write", action="store_true", help="commit; otherwise dry-run")
    args = parser.parse_args(argv)

    unverified = [c for c in GEOCODING_CARDS if not c.verified]

    with SessionLocal() as session:
        inserted, skipped = seed_price_cards(session)
        if args.write:
            session.commit()
        else:
            session.rollback()

    for version in skipped:
        print(f"  = {version}  already present, untouched")
    for version in inserted:
        print(f"  + {version}  {'inserted' if args.write else 'WOULD insert'}")

    if unverified:
        print(
            f"\n{len(unverified)} card(s) carry an UNCONFIRMED rate. Our spend report will not "
            "reconcile against these providers' bills until someone checks them:"
        )
        for card in unverified:
            rate = card.micro_paise_per_unit_in / 1_000_000
            print(
                f"  ! {card.provider:<12} {rate:>6.2f} paise/call, "
                f"{card.free_units_per_month:,} free"
            )
            print(f"      {card.source_url}")

    if not args.write:
        print("\nDry run. Re-run with --write to commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
