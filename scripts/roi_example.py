"""A worked ROI example - PART 3.2's engine, end to end, on one screen.

    uv run python -m scripts.roi_example
    uv run python -m scripts.roi_example --anchor --solar --debt

No database, no network - the engine is pure, so this script is nothing but
inputs and printing. The base case is a plausible 2 x 60 kW DC site in Kerala
with guessed-but-stated numbers; every figure it prints is recomputable by
hand from the inputs shown.

This is also the seed of PLAN G.2's public teaser: drop a pin, get breakeven
in 30 seconds, pure arithmetic.
"""

from __future__ import annotations

import argparse
import sys

from app.domain.roi import (
    Capex,
    ChargerSpec,
    Financing,
    FleetAnchor,
    RoiInputs,
    SiteOpex,
    Solar,
    TariffTerms,
    TodBand,
    compute_roi,
)

LAKH = 100_000 * 100  # paise


def rupees(paise: int | float) -> str:
    r = paise / 100
    if abs(r) >= 100_000:
        return f"Rs {r / 100_000:,.2f}L"
    return f"Rs {r:,.0f}"


def build_inputs(*, anchor: bool, solar: bool, debt: bool) -> RoiInputs:
    return RoiInputs(
        chargers=(ChargerSpec(kw=60, count=2),),
        tariff=TariffTerms(
            energy_paise_per_kwh=750,  # Rs 7.50/kWh - placeholder until KSERC is typed in
            demand_paise_per_kva_month=40_000,  # Rs 400/kVA/month
            duty_pct=0.10,
            tod_bands=(
                TodBand(share=0.25, delta_paise_per_kwh=150, name="peak 18-22h"),
                TodBand(share=0.30, delta_paise_per_kwh=-125, name="solar hours"),
            ),
        ),
        capex=Capex(
            hardware_paise=20 * LAKH,
            civil_paise=6 * LAKH,
            discom_connection_paise=int(2.5 * LAKH),
        ),
        opex=SiteOpex(sanctioned_kva=150, oam_pct_of_hardware=0.06, gateway_pct=0.018),
        selling_paise_per_kwh=1800,  # Rs 18/kWh
        kwh_by_year=(60_000, 100_000, 140_000),  # a ramp, never a flat rate
        anchor=FleetAnchor(min_kwh_per_year=90_000, paise_per_kwh=1550) if anchor else None,
        solar=Solar(capex_paise=5 * LAKH, share_of_kwh=0.30, lcoe_paise_per_kwh=380)
        if solar
        else None,
        financing=Financing(debt_share=0.6, interest_pct=0.11, tenure_years=7) if debt else None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worked ROI example (PLAN 3.2)")
    parser.add_argument("--anchor", action="store_true", help="add a fleet-anchor contract")
    parser.add_argument("--solar", action="store_true", help="add solar co-location")
    parser.add_argument("--debt", action="store_true", help="add 60% debt financing")
    args = parser.parse_args(argv)

    inputs = build_inputs(anchor=args.anchor, solar=args.solar, debt=args.debt)
    r = compute_roi(inputs)

    print(f"economics_version {r.economics_version}\n")
    print(f"margin              {r.margin_paise_per_kwh / 100:.2f} Rs/kWh")
    print(f"annual fixed        {rupees(r.annual_fixed_paise)} / year")
    if r.breakeven_utilisation is not None:
        print(
            f"BREAKEVEN           {r.breakeven_kwh_year:,.0f} kWh/yr "
            f"= {r.breakeven_utilisation:.1%} utilisation"
        )
    else:
        print("BREAKEVEN           none - every kWh loses money at this price")
    print(f"NPV                 {rupees(r.npv_paise)}")
    print(f"IRR                 {f'{r.irr_pct:.1%}' if r.irr_pct is not None else '-'}")
    if r.levered_irr_pct is not None:
        print(f"levered IRR         {r.levered_irr_pct:.1%}")
    print(f"payback             {f'{r.payback_years} years' if r.payback_years else 'never'}")

    print("\nyear   kWh        revenue      cashflow     cumulative")
    for row in r.cashflow:
        print(
            f"{row.year:>4} {row.kwh:>9,.0f} {rupees(row.revenue_paise):>12} "
            f"{rupees(row.cashflow_paise):>12} {rupees(row.cumulative_paise):>12}"
        )

    print("\nprice sensitivity (PLAN 3.2: +/- Rs 2/kWh):")
    for p in r.price_sensitivity:
        util = f"{p.breakeven_utilisation:.1%}" if p.breakeven_utilisation else "no breakeven"
        print(f"  Rs {p.selling_paise_per_kwh / 100:>5.2f}/kWh -> breakeven {util}")

    print("\nsanctioned load (the advice, not just the input):")
    for o in r.sanctioned_load_options:
        saving = rupees(o.saving_vs_input_paise_per_year)
        print(f"  {o.kva:>6.1f} kVA  {o.name:<32} saves {saving}/yr vs the customer's number")

    print("\nassumptions (the report's ledger consumes these verbatim):")
    for a in r.assumptions:
        print(f"  - {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
