"""The calculator - PART 3.2. Inputs in, one frozen result out. PURE.

Design decisions, so they are not re-litigated:

* **Utilisation is a ramp, never a flat number.** ``kwh_by_year`` is a tuple;
  a horizon longer than the tuple continues at its last value. Feeding one
  number makes good sites look bad (year 1 judged as steady state) and bad
  sites look survivable (steady state judged as year 1).
* **Breakeven is a steady-state, retail-only number.** It answers the customer
  question "how busy must this site be to stop losing money", so it excludes
  the anchor's guaranteed energy - an anchor lowers the *risk*, and that shows
  up in NPV/IRR/payback, not by flattering the breakeven.
* **Refuse rather than guess.** Impossible inputs raise ValueError. A margin
  that is zero or negative yields ``breakeven_kwh_year=None`` with the reason
  stated, never a pretend-infinite number.
* **Every default that shapes the answer is written into ``assumptions``** -
  the report's assumption ledger (PLAN 5) consumes it verbatim.
* **Integer paise for money; floats only for ratios, kWh and discounting.**
  Yearly cashflows are rounded to whole paise once, at the year boundary.

The version stamp changes whenever a formula changes, because a stored result
must be reproducible by the version that produced it (Rule 1).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

ECONOMICS_VERSION = "0.1.0"

#: Hours in a year, for the utilisation ceiling.
HOURS_PER_YEAR = 8760.0

#: kW -> kVA at the power factor DISCOMs commonly bill on.
DEFAULT_POWER_FACTOR = 0.9

#: Sanctioned-load options (PLAN 3.2: recommend the kVA, don't just accept it).
#: Fractions of the naive full-draw kVA. Managed-peak assumes charger power
#: management caps concurrent draw; battery-buffered assumes a storage buffer
#: shaves the peak harder. Both are stated in the assumption ledger.
MANAGED_PEAK_FACTOR = 0.7
BATTERY_BUFFER_FACTOR = 0.5


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChargerSpec:
    """One charger model at the site."""

    kw: float
    count: int = 1


@dataclass(frozen=True)
class TodBand:
    """A time-of-day surcharge or rebate, and the share of the site's energy
    assumed to fall inside it. The share is OUR assumption, not the SERC's."""

    share: float
    delta_paise_per_kwh: int
    name: str = ""


@dataclass(frozen=True)
class TariffTerms:
    """What the DISCOM charges. Typed from an ``electricity_tariffs`` row."""

    energy_paise_per_kwh: int
    demand_paise_per_kva_month: int = 0
    fixed_paise_per_month: int = 0
    #: Electricity duty + cess on the energy bill (0.12 = 12%).
    duty_pct: float = 0.0
    tod_bands: tuple[TodBand, ...] = ()


@dataclass(frozen=True)
class Capex:
    """One-time build cost. ``subsidy_paise`` comes from the subsidy ledger
    (PLAN 3.1) and is subtracted - capex is always net of subsidy."""

    hardware_paise: int
    civil_paise: int = 0
    transformer_paise: int = 0
    discom_connection_paise: int = 0
    signage_canopy_paise: int = 0
    subsidy_paise: int = 0

    @property
    def gross_paise(self) -> int:
        return (
            self.hardware_paise
            + self.civil_paise
            + self.transformer_paise
            + self.discom_connection_paise
            + self.signage_canopy_paise
        )

    @property
    def net_paise(self) -> int:
        return self.gross_paise - self.subsidy_paise


@dataclass(frozen=True)
class CpoTerms:
    """The network's commercial model. Both revenue-share and ₹/kWh fields
    exist so the same engine prices both models (and Part 6 runs it once per
    CPO); a plain ₹/kWh CPO simply has ``revenue_share_pct=0``."""

    revenue_share_pct: float = 0.0
    fee_paise_per_kwh: int = 0
    network_fee_paise_per_month: int = 0


@dataclass(frozen=True)
class SiteOpex:
    sanctioned_kva: float
    #: O&M / AMC as a share of HARDWARE capex (PLAN 3.2: 5-8%).
    oam_pct_of_hardware: float = 0.06
    rent_paise_per_month: int = 0
    #: Payment gateway cut of retail revenue (PLAN 3.2: ~1.5-2%).
    gateway_pct: float = 0.018


@dataclass(frozen=True)
class FleetAnchor:
    """A minimum-guarantee offtake contract - the single biggest de-risker in
    Indian charging economics. Take-or-pay: the anchor pays for
    ``min_kwh_per_year`` at ``paise_per_kwh`` whether it charges or not."""

    min_kwh_per_year: float
    paise_per_kwh: int


@dataclass(frozen=True)
class Solar:
    """Canopy/rooftop co-location: a share of delivered energy costs the
    solar LCOE instead of the grid rate (and pays no duty)."""

    capex_paise: int
    share_of_kwh: float
    lcoe_paise_per_kwh: int


@dataclass(frozen=True)
class Financing:
    """Optional debt block -> levered IRR for a credit committee."""

    debt_share: float
    interest_pct: float
    tenure_years: int


@dataclass(frozen=True)
class RoiInputs:
    chargers: tuple[ChargerSpec, ...]
    tariff: TariffTerms
    capex: Capex
    opex: SiteOpex
    selling_paise_per_kwh: int
    kwh_by_year: tuple[float, ...]

    cpo: CpoTerms = field(default_factory=CpoTerms)
    anchor: FleetAnchor | None = None
    solar: Solar | None = None
    financing: Financing | None = None

    horizon_years: int = 10
    discount_pct: float = 0.12


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class YearRow:
    """One year of the cashflow table. Year 0 is the build."""

    year: int
    kwh: float
    revenue_paise: int
    energy_cost_paise: int
    fixed_cost_paise: int
    cashflow_paise: int
    cumulative_paise: int


@dataclass(frozen=True)
class PriceSensitivityPoint:
    selling_paise_per_kwh: int
    margin_paise_per_kwh: int
    breakeven_utilisation: float | None


@dataclass(frozen=True)
class SanctionedLoadOption:
    name: str
    kva: float
    demand_charge_paise_per_year: int
    saving_vs_input_paise_per_year: int


@dataclass(frozen=True)
class RoiResult:
    economics_version: str

    margin_paise_per_kwh: int
    annual_fixed_paise: int
    breakeven_kwh_year: float | None
    breakeven_utilisation: float | None
    max_kwh_year: float

    npv_paise: int
    irr_pct: float | None
    payback_years: float | None
    levered_irr_pct: float | None

    cashflow: tuple[YearRow, ...]
    price_sensitivity: tuple[PriceSensitivityPoint, ...]
    sanctioned_load_options: tuple[SanctionedLoadOption, ...]

    assumptions: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Plain data for storage/serialisation - PLAN 3.2's 'dict out'.

        Tuples become lists so the result is JSON-shaped as-is; ``asdict``
        already turned the nested rows into dicts.
        """
        d = asdict(self)
        for key in ("cashflow", "price_sensitivity", "sanctioned_load_options", "assumptions"):
            d[key] = list(d[key])
        return d


# ---------------------------------------------------------------------------
# Validation - refuse rather than guess
# ---------------------------------------------------------------------------


def _validate(inputs: RoiInputs) -> None:
    if not inputs.chargers or all(c.count <= 0 or c.kw <= 0 for c in inputs.chargers):
        raise ValueError("at least one charger with positive kW and count is required")
    if not inputs.kwh_by_year:
        raise ValueError(
            "kwh_by_year is empty. The engine consumes a ramp curve, never a flat "
            "rate (PLAN 3.2) - pass at least one year"
        )
    if any(k < 0 for k in inputs.kwh_by_year):
        raise ValueError("kwh_by_year values cannot be negative")
    if inputs.selling_paise_per_kwh <= 0:
        raise ValueError("selling price must be positive paise per kWh")
    if inputs.tariff.energy_paise_per_kwh <= 0:
        raise ValueError("tariff energy charge must be positive paise per kWh")
    tod_share = sum(b.share for b in inputs.tariff.tod_bands)
    if tod_share > 1.0 + 1e-9 or any(b.share < 0 for b in inputs.tariff.tod_bands):
        raise ValueError(f"ToD band shares must be >= 0 and sum to <= 1 (got {tod_share:.3f})")
    if not 0 <= inputs.cpo.revenue_share_pct < 1:
        raise ValueError("revenue_share_pct must be in [0, 1)")
    if not 0 <= inputs.opex.gateway_pct < 1:
        raise ValueError("gateway_pct must be in [0, 1)")
    if inputs.solar is not None and not 0 <= inputs.solar.share_of_kwh <= 1:
        raise ValueError("solar share_of_kwh must be in [0, 1]")
    if inputs.financing is not None:
        f = inputs.financing
        if not 0 < f.debt_share < 1:
            raise ValueError("debt_share must be in (0, 1)")
        if f.tenure_years <= 0:
            raise ValueError("financing tenure must be positive")
    if inputs.horizon_years <= 0:
        raise ValueError("horizon_years must be positive")
    if inputs.capex.net_paise < 0:
        raise ValueError(
            "subsidy exceeds gross capex - check the subsidy ledger row against its conditions"
        )


# ---------------------------------------------------------------------------
# The pieces, each pure and separately testable
# ---------------------------------------------------------------------------


def effective_energy_paise_per_kwh(tariff: TariffTerms, solar: Solar | None) -> float:
    """What one delivered kWh costs us, all-in.

    Grid energy carries the ToD-weighted rate plus duty; solar energy costs
    its LCOE and pays no duty. Blended by the solar share.
    """
    tod_delta = sum(b.share * b.delta_paise_per_kwh for b in tariff.tod_bands)
    grid = (tariff.energy_paise_per_kwh + tod_delta) * (1.0 + tariff.duty_pct)
    if solar is None or solar.share_of_kwh == 0:
        return grid
    return (1.0 - solar.share_of_kwh) * grid + solar.share_of_kwh * solar.lcoe_paise_per_kwh


def margin_paise_per_kwh(inputs: RoiInputs, *, selling_paise: int | None = None) -> float:
    """Retail margin on one kWh, after everyone else takes their cut.

    Revenue-side percentages (revenue share, gateway) scale with the price;
    energy cost and the ₹/kWh CPO fee do not - which is why margin is not
    linear in utilisation but IS linear in price.
    """
    price = inputs.selling_paise_per_kwh if selling_paise is None else selling_paise
    take = 1.0 - inputs.cpo.revenue_share_pct - inputs.opex.gateway_pct
    return (
        price * take
        - effective_energy_paise_per_kwh(inputs.tariff, inputs.solar)
        - inputs.cpo.fee_paise_per_kwh
    )


def annual_fixed_paise(inputs: RoiInputs) -> int:
    """Costs that arrive whether or not a single kWh is sold."""
    t, o, c = inputs.tariff, inputs.opex, inputs.cpo
    return round(
        o.sanctioned_kva * t.demand_paise_per_kva_month * 12
        + t.fixed_paise_per_month * 12
        + inputs.capex.hardware_paise * o.oam_pct_of_hardware
        + o.rent_paise_per_month * 12
        + c.network_fee_paise_per_month * 12
    )


def max_kwh_year(chargers: tuple[ChargerSpec, ...]) -> float:
    """The physical ceiling: every plug at full power, all year."""
    return sum(c.kw * c.count for c in chargers) * HOURS_PER_YEAR


def _kwh_for_year(inputs: RoiInputs, year: int) -> float:
    """Ramp lookup; beyond the ramp, steady state at its last value."""
    ramp = inputs.kwh_by_year
    return ramp[min(year - 1, len(ramp) - 1)]


def _year_economics(inputs: RoiInputs, year: int) -> tuple[float, int, int]:
    """(kwh_delivered, revenue_paise, energy_cost_paise) for one year.

    The anchor is take-or-pay: its minimum is billed at the contract price
    even when organic demand alone would not reach it, and delivered energy
    is at least the minimum. The gateway cut applies to retail revenue only -
    a fleet contract is invoiced, not swiped - while the CPO's revenue share
    applies to all revenue. Stated in the assumption ledger.
    """
    organic = _kwh_for_year(inputs, year)
    anchor = inputs.anchor

    if anchor is None:
        delivered = organic
        anchor_kwh, retail_kwh = 0.0, organic
    else:
        delivered = max(organic, anchor.min_kwh_per_year)
        anchor_kwh = anchor.min_kwh_per_year
        retail_kwh = delivered - anchor_kwh

    retail_revenue = retail_kwh * inputs.selling_paise_per_kwh
    anchor_revenue = anchor_kwh * (anchor.paise_per_kwh if anchor else 0)
    revenue = retail_revenue + anchor_revenue

    energy_cost = delivered * effective_energy_paise_per_kwh(inputs.tariff, inputs.solar)

    # Per-kWh CPO fee on everything delivered; percentages per the docstring.
    fees = (
        delivered * inputs.cpo.fee_paise_per_kwh
        + revenue * inputs.cpo.revenue_share_pct
        + retail_revenue * inputs.opex.gateway_pct
    )
    return delivered, round(revenue), round(energy_cost + fees)


def _npv(cashflows: list[int], rate: float) -> float:
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))


def _irr(cashflows: list[int]) -> float | None:
    """Bisection on NPV. None when no sign change exists in (-0.99, 10) -
    an all-negative project has no IRR, and pretending otherwise is worse."""
    lo, hi = -0.99, 10.0
    f_lo, f_hi = _npv(cashflows, lo), _npv(cashflows, hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = _npv(cashflows, mid)
        if abs(f_mid) < 1e-6:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def _payback_years(cashflows: list[int]) -> float | None:
    """First moment cumulative cash turns non-negative, interpolated within
    the year. None if it never does inside the horizon."""
    cumulative = 0
    for year, cf in enumerate(cashflows):
        previous = cumulative
        cumulative += cf
        if year > 0 and cumulative >= 0 and cf > 0:
            return year - 1 + (-previous / cf)
    return None


def _annuity_paise(principal: int, rate: float, years: int) -> int:
    """Level annual debt service."""
    if rate == 0:
        return round(principal / years)
    factor = rate * (1 + rate) ** years / ((1 + rate) ** years - 1)
    return round(principal * factor)


def sanctioned_load_options(
    inputs: RoiInputs, *, power_factor: float = DEFAULT_POWER_FACTOR
) -> tuple[SanctionedLoadOption, ...]:
    """Recommend the kVA rather than accepting it (PLAN 3.2).

    Cutting Rs 2-4 lakh/yr of demand charges is advice worth paying for, and
    it is pure arithmetic: three options against the customer's number.
    """
    connected_kw = sum(c.kw * c.count for c in inputs.chargers)
    naive_kva = connected_kw / power_factor
    rate_year = inputs.tariff.demand_paise_per_kva_month * 12
    input_cost = round(inputs.opex.sanctioned_kva * rate_year)

    options = []
    for name, factor in (
        ("full connected load", 1.0),
        ("managed peak (load management)", MANAGED_PEAK_FACTOR),
        ("battery buffered", BATTERY_BUFFER_FACTOR),
    ):
        kva = round(naive_kva * factor, 1)
        cost = round(kva * rate_year)
        options.append(
            SanctionedLoadOption(
                name=name,
                kva=kva,
                demand_charge_paise_per_year=cost,
                saving_vs_input_paise_per_year=input_cost - cost,
            )
        )
    return tuple(options)


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

#: PLAN 3.2: breakeven at +/- Rs 2 around the assumed selling price.
_PRICE_STEPS_PAISE = (-200, -100, 0, 100, 200)


def compute_roi(inputs: RoiInputs) -> RoiResult:
    """Everything the report's money section needs, from inputs alone."""
    _validate(inputs)

    margin = margin_paise_per_kwh(inputs)
    fixed = annual_fixed_paise(inputs)
    ceiling = max_kwh_year(inputs.chargers)

    assumptions: list[str] = [
        f"economics_version {ECONOMICS_VERSION}",
        f"discount rate {inputs.discount_pct:.0%} for NPV",
        f"O&M at {inputs.opex.oam_pct_of_hardware:.1%} of hardware capex per year",
        f"payment gateway {inputs.opex.gateway_pct:.2%} of retail revenue "
        "(fleet-anchor revenue is invoiced, not swiped, so it carries no gateway cut)",
        "utilisation ceiling assumes every plug at full rated power all 8,760 hours",
        f"demand ramp given for {len(inputs.kwh_by_year)} year(s); "
        "later years continue at the final year's value",
    ]
    if inputs.tariff.tod_bands:
        assumptions.append(
            "ToD energy shares are our modelling assumption, not the SERC's: "
            + ", ".join(
                f"{b.name or 'band'} {b.share:.0%} at {b.delta_paise_per_kwh:+d} paise"
                for b in inputs.tariff.tod_bands
            )
        )
    if inputs.solar is not None:
        assumptions.append(
            f"solar serves {inputs.solar.share_of_kwh:.0%} of delivered energy at "
            f"LCOE {inputs.solar.lcoe_paise_per_kwh} paise/kWh, duty-free"
        )
    if inputs.anchor is not None:
        assumptions.append(
            f"fleet anchor is take-or-pay: {inputs.anchor.min_kwh_per_year:,.0f} kWh/yr "
            f"billed at {inputs.anchor.paise_per_kwh} paise/kWh regardless of organic demand"
        )

    # --- breakeven: steady-state, retail-only ------------------------------
    if margin <= 0:
        breakeven_kwh: float | None = None
        breakeven_util: float | None = None
        assumptions.append(
            f"margin is {margin:.0f} paise/kWh - at this price every kWh sold loses "
            "money, so no utilisation breaks even; the price or the tariff has to move"
        )
    else:
        breakeven_kwh = fixed / margin
        breakeven_util = breakeven_kwh / ceiling if ceiling > 0 else None

    # --- cashflow table ----------------------------------------------------
    build_cost = inputs.capex.net_paise + (inputs.solar.capex_paise if inputs.solar else 0)
    rows: list[YearRow] = [
        YearRow(
            year=0,
            kwh=0.0,
            revenue_paise=0,
            energy_cost_paise=0,
            fixed_cost_paise=0,
            cashflow_paise=-build_cost,
            cumulative_paise=-build_cost,
        )
    ]
    cumulative = -build_cost
    for year in range(1, inputs.horizon_years + 1):
        kwh, revenue, variable_cost = _year_economics(inputs, year)
        cashflow = revenue - variable_cost - fixed
        cumulative += cashflow
        rows.append(
            YearRow(
                year=year,
                kwh=kwh,
                revenue_paise=revenue,
                energy_cost_paise=variable_cost,
                fixed_cost_paise=fixed,
                cashflow_paise=cashflow,
                cumulative_paise=cumulative,
            )
        )

    flows = [r.cashflow_paise for r in rows]
    npv = round(_npv(flows, inputs.discount_pct))
    irr = _irr(flows)
    payback = _payback_years(flows)

    # --- levered IRR (optional) -------------------------------------------
    levered_irr: float | None = None
    if inputs.financing is not None:
        f = inputs.financing
        debt = round(build_cost * f.debt_share)
        service = _annuity_paise(debt, f.interest_pct, f.tenure_years)
        equity_flows = [-(build_cost - debt)] + [
            r.cashflow_paise - (service if r.year <= f.tenure_years else 0) for r in rows[1:]
        ]
        levered_irr = _irr(equity_flows)
        assumptions.append(
            f"financing: {f.debt_share:.0%} debt at {f.interest_pct:.1%} over "
            f"{f.tenure_years} years, level annual service"
        )

    return RoiResult(
        economics_version=ECONOMICS_VERSION,
        margin_paise_per_kwh=round(margin),
        annual_fixed_paise=fixed,
        breakeven_kwh_year=breakeven_kwh,
        breakeven_utilisation=breakeven_util,
        max_kwh_year=ceiling,
        npv_paise=npv,
        irr_pct=round(irr, 4) if irr is not None else None,
        payback_years=round(payback, 2) if payback is not None else None,
        levered_irr_pct=round(levered_irr, 4) if levered_irr is not None else None,
        cashflow=tuple(rows),
        price_sensitivity=tuple(
            _sensitivity_point(inputs, step, fixed, ceiling) for step in _PRICE_STEPS_PAISE
        ),
        sanctioned_load_options=sanctioned_load_options(inputs),
        assumptions=tuple(assumptions),
    )


def _sensitivity_point(
    inputs: RoiInputs, step_paise: int, fixed: int, ceiling: float
) -> PriceSensitivityPoint:
    price = inputs.selling_paise_per_kwh + step_paise
    if price <= 0:
        return PriceSensitivityPoint(
            selling_paise_per_kwh=price, margin_paise_per_kwh=0, breakeven_utilisation=None
        )
    m = margin_paise_per_kwh(inputs, selling_paise=price)
    util = (fixed / m) / ceiling if m > 0 and ceiling > 0 else None
    return PriceSensitivityPoint(
        selling_paise_per_kwh=price,
        margin_paise_per_kwh=round(m),
        breakeven_utilisation=util,
    )
