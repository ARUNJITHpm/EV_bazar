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
* **There are TWO breakevens, and they answer different questions.**
  ``breakeven_*`` covers the running bills only - "how busy to stop losing
  money this month". ``full_cost_breakeven_*`` also recovers the build cost -
  "how busy to have been worth building at all". A site can clear the first,
  earn a BUILD verdict, and still be short over the horizon; the report used
  to print both facts pages apart and reconcile them nowhere
  (CPO_SELECTION_PLAN.md, Track B - R0 found it, R5 decided it).
* **The full-cost breakeven is DISCOUNTED, and that is not a detail.** It is
  the steady-state annual volume at which NPV is exactly zero:
  ``(annual_fixed + build_cost / annuity) / margin``, where ``annuity`` is
  the present value of 1 per year over the horizon at ``discount_pct``. The
  obvious cheaper definition - bills plus ``build_cost / horizon_years``,
  undiscounted - was measured against the three sample payloads and
  **contradicted the NPV already in the document on two cases out of nine**,
  including the one that prompted the whole question: a site whose downside
  cleared that threshold while its downside NPV was 1.94 lakh short. A second
  number that argues with the first two is worse than one number with a
  caveat, so the definition that agrees by construction is the one that
  ships. Like ``breakeven_*`` it is steady-state, so a ramped ``kwh_by_year``
  will not cross it in exactly the year the cashflow turns.
  ``full_cost_build_recovery_paise_year`` is the ``build_cost / annuity``
  term on its own, because section 09 prints the formula and a report that
  shows a sum has to be able to show every term in it. Deriving it in the
  component instead would be a financial number computed outside the engine,
  which is the one thing AGENTS.md rule 1 forbids (Track B - R7).
* **Refuse rather than guess.** Impossible inputs raise ValueError. A margin
  that is zero or negative yields ``breakeven_kwh_year=None`` with the reason
  stated, never a pretend-infinite number.
* **A breakdown always adds up to the total it explains.** ``capex_lines``,
  ``fixed_cost_lines`` and ``unit_economics`` are decompositions of
  ``capex.net_paise``, ``annual_fixed_paise`` and ``margin_paise_per_kwh`` -
  never second opinions about them. Each line is rounded to whole paise on
  its own, so the residue is absorbed into the largest line rather than left
  to show: a report that prints "9 + 3 + 3 = 14" has spent more trust than
  the fraction of a paise was worth (Track B - R6).
* **Every default that shapes the answer is written into ``assumptions``** -
  the report's assumption ledger (PLAN 5) consumes it verbatim.
* **Integer paise for money; floats only for ratios, kWh and discounting.**
  Yearly cashflows are rounded to whole paise once, at the year boundary.

The version stamp changes whenever a formula changes, because a stored result
must be reproducible by the version that produced it (Rule 1).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

#: 0.2.0 added the full-cost breakeven (Track B - R5); 0.3.0 added the three
#: breakdowns section 05 prints its arithmetic from (Track B - R6); 0.4.0
#: exposed the annual build-cost recovery so section 09 can print the
#: full-cost formula term by term (Track B - R7). A stored result must be
#: reproducible by the version that produced it, and a 0.2.0 result has no
#: breakdown to reproduce.
#:
#: 0.5.0 is the first version whose ``assumptions`` are PRINTED (Track B -
#: R10). They were always written and never reached a page, so their wording
#: was free to drift; from here it is part of the deliverable, and two
#: reports stamped the same version have to say the same thing. The only
#: change to the text itself is that the full-cost line now carries the
#: annual recovery figure, which section 09 already prints - one number, one
#: origin.
ECONOMICS_VERSION = "0.5.0"

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
class CostLine:
    """One line of a breakdown. ``paise`` is per year for the cost tables and
    per kWh for :class:`UnitEconomics`; the breakdown says which."""

    name: str
    paise: int


@dataclass(frozen=True)
class UnitEconomics:
    """What becomes of one unit's price, in the order it leaves.

    ``selling_paise`` minus every deduction is exactly ``margin_paise`` - the
    same margin the breakevens divide by, decomposed rather than recomputed.
    Section 05 prints it as a sentence a reader can do in their head, which
    only works if it is true to the paise.
    """

    selling_paise: int
    deductions: tuple[CostLine, ...]
    margin_paise: int


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
    #: The same threshold with the build cost spread over the horizon: what
    #: the site must sell to have been worth building, not merely to stop
    #: losing money. ``None`` for the same reason the pair above is - a margin
    #: at or below zero has no breakeven at any volume.
    full_cost_breakeven_kwh_year: float | None
    full_cost_breakeven_utilisation: float | None
    #: The build cost spread over the horizon at ``discount_pct`` - one term
    #: of the line above, published because the report prints the division
    #: rather than asserting its answer. Always present, even where the
    #: breakeven is ``None``: what the build costs per year does not stop
    #: being true because the margin went negative.
    full_cost_build_recovery_paise_year: int
    max_kwh_year: float

    npv_paise: int
    irr_pct: float | None
    payback_years: float | None
    levered_irr_pct: float | None

    cashflow: tuple[YearRow, ...]
    price_sensitivity: tuple[PriceSensitivityPoint, ...]
    sanctioned_load_options: tuple[SanctionedLoadOption, ...]

    #: The three breakdowns, each summing exactly to a headline above it:
    #: ``capex_lines`` to the net build cost, ``fixed_cost_lines`` to
    #: ``annual_fixed_paise``, ``unit_economics`` to ``margin_paise_per_kwh``.
    #: They exist so the report can show its working (Track B - R6) without a
    #: second component doing arithmetic the engine already did.
    capex_lines: tuple[CostLine, ...]
    fixed_cost_lines: tuple[CostLine, ...]
    unit_economics: UnitEconomics

    assumptions: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Plain data for storage/serialisation - PLAN 3.2's 'dict out'.

        Tuples become lists so the result is JSON-shaped as-is; ``asdict``
        already turned the nested rows into dicts.
        """
        d = asdict(self)
        for key in (
            "cashflow",
            "price_sensitivity",
            "sanctioned_load_options",
            "assumptions",
            "capex_lines",
            "fixed_cost_lines",
        ):
            d[key] = list(d[key])
        unit = d["unit_economics"]
        assert isinstance(unit, dict)
        unit["deductions"] = list(unit["deductions"])
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


#: Capex field -> the words an owner would use for it. Ordered as the money
#: is spent, which is also the order a quotation arrives in.
CAPEX_LINE_NAMES: tuple[tuple[str, str], ...] = (
    ("hardware_paise", "Chargers, installation and commissioning"),
    ("civil_paise", "Civil work and site preparation"),
    ("transformer_paise", "Transformer"),
    ("discom_connection_paise", "Power connection and cabling"),
    ("signage_canopy_paise", "Canopy, signage and lighting"),
)


def _reconcile(lines: list[CostLine], total: int) -> tuple[CostLine, ...]:
    """Make a breakdown add up to the number it explains.

    Every line is rounded to whole paise on its own, so a five-line breakdown
    can miss its total by a few paise. The residue goes onto the largest line
    - least visible there, and the largest line is usually a blend already.
    """
    if not lines:
        return ()
    residue = total - sum(line.paise for line in lines)
    if residue == 0:
        return tuple(lines)
    biggest = max(range(len(lines)), key=lambda i: abs(lines[i].paise))
    out = list(lines)
    out[biggest] = CostLine(name=out[biggest].name, paise=out[biggest].paise + residue)
    return tuple(out)


def capex_lines(capex: Capex) -> tuple[CostLine, ...]:
    """The one-time budget, line by line, summing to ``capex.net_paise``.

    The subsidy is a line of its own rather than quietly netted off, because
    a subsidy that is applied for and refused is the single most common way a
    build budget moves after the report is written.
    """
    lines = [
        CostLine(name=name, paise=int(getattr(capex, field_name)))
        for field_name, name in CAPEX_LINE_NAMES
        if getattr(capex, field_name)
    ]
    if capex.subsidy_paise:
        lines.append(CostLine(name="Less subsidy", paise=-capex.subsidy_paise))
    return tuple(lines)


def fixed_cost_lines(inputs: RoiInputs) -> tuple[CostLine, ...]:
    """``annual_fixed_paise``, itemised. Paise per YEAR, zero lines omitted."""
    t, o, c = inputs.tariff, inputs.opex, inputs.cpo
    raw: tuple[tuple[str, float], ...] = (
        (
            "Demand charge on the sanctioned connection",
            o.sanctioned_kva * t.demand_paise_per_kva_month * 12,
        ),
        ("DISCOM fixed charge", t.fixed_paise_per_month * 12.0),
        ("Maintenance and repair reserve", inputs.capex.hardware_paise * o.oam_pct_of_hardware),
        ("Rent", o.rent_paise_per_month * 12.0),
        ("Operator platform fee", c.network_fee_paise_per_month * 12.0),
    )
    lines = [CostLine(name=n, paise=round(v)) for n, v in raw if round(v)]
    return _reconcile(lines, annual_fixed_paise(inputs))


def unit_economics(inputs: RoiInputs) -> UnitEconomics:
    """One unit's price, and everyone who takes a piece of it before the
    site does. Deductions sum to ``selling - margin``, exactly."""
    price = inputs.selling_paise_per_kwh
    margin = round(margin_paise_per_kwh(inputs))
    raw: tuple[tuple[str, float], ...] = (
        ("Electricity, all-in", effective_energy_paise_per_kwh(inputs.tariff, inputs.solar)),
        ("Operator fee per unit", float(inputs.cpo.fee_paise_per_kwh)),
        ("Operator revenue share", price * inputs.cpo.revenue_share_pct),
        ("Payment gateway", price * inputs.opex.gateway_pct),
    )
    lines = [CostLine(name=n, paise=round(v)) for n, v in raw if round(v)]
    return UnitEconomics(
        selling_paise=price,
        deductions=_reconcile(lines, price - margin),
        margin_paise=margin,
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
    # The money that leaves once, before a single kWh is sold. Needed here as
    # well as by the cashflow below, because the second breakeven recovers it.
    build_cost = inputs.capex.net_paise + (inputs.solar.capex_paise if inputs.solar else 0)
    # Present value of 1 per year for the horizon: what turns a one-off build
    # cost into the annual margin that repays it at the document's own rate.
    annuity = sum(
        1.0 / (1.0 + inputs.discount_pct) ** y for y in range(1, inputs.horizon_years + 1)
    )
    build_per_year = build_cost / annuity

    if margin <= 0:
        breakeven_kwh: float | None = None
        breakeven_util: float | None = None
        full_cost_kwh: float | None = None
        full_cost_util: float | None = None
        assumptions.append(
            f"margin is {margin:.0f} paise/kWh - at this price every kWh sold loses "
            "money, so no utilisation breaks even; the price or the tariff has to move"
        )
    else:
        breakeven_kwh = fixed / margin
        breakeven_util = breakeven_kwh / ceiling if ceiling > 0 else None
        full_cost_kwh = (fixed + build_per_year) / margin
        full_cost_util = full_cost_kwh / ceiling if ceiling > 0 else None
        assumptions.append(
            f"full-cost breakeven spreads the {build_cost / 100_000_00:.2f} lakh build cost "
            f"over {inputs.horizon_years} years at {inputs.discount_pct:.0%}, which is "
            f"{build_per_year / 100_000_00:.2f} lakh a year - it is the steady-state volume "
            "at which NPV is zero, so it agrees with the NPV above rather than offering a "
            "second opinion"
        )

    # --- cashflow table ----------------------------------------------------
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
        full_cost_breakeven_kwh_year=full_cost_kwh,
        full_cost_breakeven_utilisation=full_cost_util,
        full_cost_build_recovery_paise_year=round(build_per_year),
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
        capex_lines=capex_lines(inputs.capex),
        fixed_cost_lines=fixed_cost_lines(inputs),
        unit_economics=unit_economics(inputs),
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
