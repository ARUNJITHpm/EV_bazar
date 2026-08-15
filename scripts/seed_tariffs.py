"""Seed the Tier-1 EV-charging tariffs - PART 3.1 / 0.2, Kerala + Tamil Nadu.

    uv run python -m scripts.seed_tariffs            # insert if absent
    uv run python -m scripts.seed_tariffs --dry-run  # show, write nothing

Every row here was transcribed from a public source, and every row carries
that source in ``order_number`` + ``source_pdf`` - a tariff that cannot be
defended to a customer whose bill disagrees is not data (the NOT NULL columns
enforce this).

CONFIDENCE IS NOT UNIFORM, and the ``note`` on each row says so:

* **Kerala (LT-X, HT-VI)** - transcribed from the KSERC gazette tariff schedule
  itself (order dated 05.12.2024). High confidence on the numbers.
* **Tamil Nadu (LT-VII EV)** - from news coverage of TNERC order SMT.No.6/2025,
  NOT yet from the order PDF. The rates are right to the rupee in every source,
  but the time-band boundaries and whether the fixed charge is per kW or per
  kVA still need the gazette. Flagged accordingly.

None of this is the 3.3 exit: a row here is still UNVERIFIED against a real
electricity bill. Effective-dating means the correction is a NEW row that
supersedes, never an edit - so seeding now costs nothing later.

Idempotent: a row already present (same category + effective_from) is skipped.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from app.db import SessionLocal
from app.models.tariffs import ElectricityTariff

KERALA = 32
TAMIL_NADU = 33


@dataclass(frozen=True)
class TariffSeed:
    lgd_state_code: int
    discom: str
    consumer_category: str
    energy_paise_per_kwh: int
    effective_from: dt.date
    effective_to: dt.date | None
    order_number: str
    source_pdf: str
    note: str
    demand_paise_per_kva_month: int = 0
    fixed_paise_per_month: int = 0
    duty_bp: int = 0
    ev_specific: bool = True
    tod_bands: list[dict[str, Any]] = field(default_factory=list)


#: Gazette dates. effective_to is EXCLUSIVE, so a period ending 31.03.2027 is
#: stored as 01.04.2027.
_KSERC_PDF = (
    "https://dev.erckerala.org/api/storage/orders/vnp1XnN5z47r0dCh18rj3s2e1q2utii3T8AtwUMm.pdf"
)

SEEDS: tuple[TariffSeed, ...] = (
    # --- Kerala, gazette-exact -------------------------------------------
    TariffSeed(
        lgd_state_code=KERALA,
        discom="KSEBL",
        consumer_category="LT-X EV Public Charging Stations",
        # The flat "Ruling tariff" - what KSEB bills with no ToD election.
        energy_paise_per_kwh=715,
        # Solar/Non-solar is the ALTERNATIVE the operator may elect; stored as
        # reference with an assumed energy share (the share is OUR modelling
        # assumption, not the SERC's).
        tod_bands=[
            {
                "name": "solar",
                "hours": "09:00-16:00",
                "rate_paise_per_kwh": 500,
                "assumed_share": 0.35,
            },
            {
                "name": "non_solar",
                "hours": "16:00-09:00",
                "rate_paise_per_kwh": 930,
                "assumed_share": 0.65,
            },
        ],
        fixed_paise_per_month=0,  # gazette: Nil
        demand_paise_per_kva_month=0,
        duty_bp=0,  # see note
        effective_from=dt.date(2024, 12, 5),
        effective_to=dt.date(2027, 4, 1),
        order_number="KSERC Tariff Order / Schedule w.e.f 05.12.2024, category LT-X",
        source_pdf=_KSERC_PDF,
        note=(
            "Gazette-exact energy rates (flat 7.15; solar 5.00 / non-solar 9.30, 9AM-4PM). "
            "Nil fixed charge per gazette. FLAT vs ToD is the operator's election - the "
            "report should show both. ELECTRICITY DUTY set to 0 but UNCONFIRMED: this is "
            "the one number most likely wrong in the unsafe direction (understating cost); "
            "confirm against a real KSEB bill (PLAN 3.3)."
        ),
    ),
    TariffSeed(
        lgd_state_code=KERALA,
        discom="KSEBL",
        consumer_category="HT-VI EV Charging Stations",
        energy_paise_per_kwh=690,
        tod_bands=[
            {
                "name": "solar",
                "hours": "09:00-16:00",
                "rate_paise_per_kwh": 480,
                "assumed_share": 0.35,
            },
            {
                "name": "non_solar",
                "hours": "16:00-09:00",
                "rate_paise_per_kwh": 900,
                "assumed_share": 0.65,
            },
        ],
        demand_paise_per_kva_month=0,  # gazette: Nil
        duty_bp=0,
        effective_from=dt.date(2024, 12, 5),
        effective_to=dt.date(2025, 4, 1),
        order_number="KSERC Schedule w.e.f 05.12.2024, category HT-VI (period 1)",
        source_pdf=_KSERC_PDF,
        note="Gazette-exact (6.90 / solar 4.80 / non-solar 9.00). Duty unconfirmed; see LT-X.",
    ),
    TariffSeed(
        lgd_state_code=KERALA,
        discom="KSEBL",
        consumer_category="HT-VI EV Charging Stations",
        energy_paise_per_kwh=700,
        tod_bands=[
            {
                "name": "solar",
                "hours": "09:00-16:00",
                "rate_paise_per_kwh": 500,
                "assumed_share": 0.35,
            },
            {
                "name": "non_solar",
                "hours": "16:00-09:00",
                "rate_paise_per_kwh": 920,
                "assumed_share": 0.65,
            },
        ],
        demand_paise_per_kva_month=0,
        duty_bp=0,
        effective_from=dt.date(2025, 4, 1),
        effective_to=dt.date(2027, 4, 1),
        order_number="KSERC Schedule w.e.f 01.04.2025, category HT-VI (period 2)",
        source_pdf=_KSERC_PDF,
        note="Gazette-exact (7.00 / solar 5.00 / non-solar 9.20). Supersedes HT-VI period 1.",
    ),
    # --- Tamil Nadu, news-sourced (LOWER confidence) ---------------------
    TariffSeed(
        lgd_state_code=TAMIL_NADU,
        discom="TANGEDCO",
        consumer_category="LT-VII EV Charging Stations",
        # Pure ToD, no flat option. Base = the off-peak/night rate (most hours);
        # solar and peak are the elective bands around it.
        energy_paise_per_kwh=810,
        tod_bands=[
            {
                "name": "solar",
                "hours": "09:00-16:00",
                "rate_paise_per_kwh": 650,
                "assumed_share": 0.30,
            },
            {
                "name": "peak",
                "hours": "06:00-09:00,18:00-22:00",
                "rate_paise_per_kwh": 975,
                "assumed_share": 0.30,
            },
            {
                "name": "off_peak",
                "hours": "16:00-18:00,22:00-06:00",
                "rate_paise_per_kwh": 810,
                "assumed_share": 0.40,
            },
        ],
        # Sources say Rs 304 per kW/month; our column is per kVA. Stored here,
        # flagged in the note - the gazette resolves kW-vs-kVA.
        demand_paise_per_kva_month=30_400,
        duty_bp=0,
        effective_from=dt.date(2025, 7, 1),
        effective_to=None,
        order_number="TNERC Order SMT.No.6 of 2025 (FY2025-26), category LT-VII EV",
        source_pdf="https://www.prokerala.com/news/articles/a1650680.html",
        note=(
            "NEWS-SOURCED, not yet from the TNERC order PDF. Rates (solar 6.50 / peak 9.75 / "
            "off-peak 8.10) agree across sources; the exact time-band edges and whether the "
            "Rs 304 charge is per kW or per kVA still need the gazette. Fixed charge stored as "
            "per-kVA. A prior order (~Rs 8/10/12, eff. 01.07.2023) exists and should be added "
            "as a superseded row when the PDFs are collected. Confirm all against a TANGEDCO bill."
        ),
    ),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed KL+TN EV tariffs (PLAN 3.1)")
    parser.add_argument("--dry-run", action="store_true", help="show, write nothing")
    args = parser.parse_args(argv)

    inserted = skipped = 0
    with SessionLocal() as session:
        for s in SEEDS:
            exists = session.execute(
                select(ElectricityTariff.id).where(
                    ElectricityTariff.lgd_state_code == s.lgd_state_code,
                    ElectricityTariff.consumer_category == s.consumer_category,
                    ElectricityTariff.effective_from == s.effective_from,
                )
            ).first()
            tag = f"{s.discom} {s.consumer_category} from {s.effective_from}"
            if exists:
                print(f"  skip   {tag} (already present)")
                skipped += 1
                continue
            verb = "would add" if args.dry_run else "ADD"
            print(f"  {verb}   {tag}: {s.energy_paise_per_kwh / 100:.2f} Rs/unit")
            if not args.dry_run:
                session.add(
                    ElectricityTariff(
                        lgd_state_code=s.lgd_state_code,
                        discom=s.discom,
                        consumer_category=s.consumer_category,
                        ev_specific=s.ev_specific,
                        energy_paise_per_kwh=s.energy_paise_per_kwh,
                        demand_paise_per_kva_month=s.demand_paise_per_kva_month,
                        fixed_paise_per_month=s.fixed_paise_per_month,
                        duty_bp=s.duty_bp,
                        tod_bands=s.tod_bands or None,
                        effective_from=s.effective_from,
                        effective_to=s.effective_to,
                        order_number=s.order_number,
                        source_pdf=s.source_pdf,
                        note=s.note,
                    )
                )
                inserted += 1
        if not args.dry_run:
            session.commit()

    print(f"\n{'dry run - ' if args.dry_run else ''}inserted {inserted}, skipped {skipped}")
    print("Every row is UNVERIFIED against a real bill (PLAN 3.3). See each row's note.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
