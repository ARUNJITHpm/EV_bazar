"""The report payload contract - PLAN 5's 7-section shape, typed.

One pydantic model per section slice, mirroring
``frontend/src/features/report/payload.ts`` field for field. The frontend
renders this shape and nothing else; the assembler produces it; the ``reports``
table stores its ``model_dump()``. Because stored payloads ARE dumps of this
model, serving "verbatim" (AGENTS.md rule 9) and serving "validated" are the
same bytes - validation on the way out is an identity, not a rewrite.

Money is integer paise throughout (the frontend's ``lib/money.ts`` is the only
place paise become ₹). Utilisation is a fraction. Every uncertain figure is a
P10/P50/P90 band (AGENTS.md rule 6).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SitePayload(BaseModel):
    name: str
    line: str
    district: str
    lgd_district_code: int
    lat: float
    lng: float
    archetype: str
    data_tier: Literal[1, 2, 3]


class HardwarePayload(BaseModel):
    connectors: int
    rated_kw_each: float
    sanctioned_kva_full: float


class BreakevenPayload(BaseModel):
    """Two thresholds, and they answer different questions.

    The first three fields are the RUNNING-BILL breakeven: how busy the site
    must be to stop losing money month to month, build cost excluded - and
    the line the VERDICT is measured against. The ``full_cost_*`` trio is the
    harder one: the steady-state volume at which the ten-year NPV is zero, so
    it recovers the build cost at the same rate the rest of the document
    discounts at.

    They are separate numbers rather than one relabelled, because a site can
    clear the first, earn a BUILD verdict, and still be short over ten years
    (Track B - R0 found it in the fixtures, R5 decided it). The definition is
    discounted rather than straight-line for a measured reason recorded in
    ``roi/engine.py``: the cheaper definition disagreed with the NPV printed
    four pages away. Optional so a payload stored by economics 0.1.0 still
    validates; the sections that print it omit the row when it is absent.
    """

    utilisation: float
    kwh_year: float
    kwh_day: float
    full_cost_utilisation: float | None = None
    full_cost_kwh_year: float | None = None
    full_cost_kwh_day: float | None = None
    #: The build-cost half of the full-cost line, per year (Track B - R7).
    #: Section 09 prints the division rather than asserting its answer, and a
    #: sum the reader is invited to check has to show every term in it. The
    #: alternative was the component dividing the build cost by an annuity
    #: factor of its own, which is a financial number computed outside the
    #: engine.
    full_cost_recovery_paise_year: int | None = None


class UtilisationBand(BaseModel):
    p10: float
    p50: float
    p90: float
    model_version: str
    modelled_not_measured: bool


class VerdictPayload(BaseModel):
    value: Literal["build", "conditional", "dont"]
    reason: str


class DemandPayload(BaseModel):
    district_ev_2025: int
    district_growth_yoy_pct: float
    two_wheeler_share_pct: float
    vahan_snapshot: str


#: Which side of the argument a fact lands on. Rendered as a sign AND a word
#: ("+ FAVOURS", "− AGAINST", "· NEUTRAL") so a photocopied page keeps it.
Direction = Literal["favours", "against", "neutral"]


class SiteFact(BaseModel):
    label: str
    value: str
    source: str
    unverified: bool
    #: The heading the fact sits under ("Access and geometry", "Demand", ...).
    #: Optional so payloads stored before the marker existed still validate.
    group: str | None = None
    direction: Direction | None = None
    #: One plain sentence saying why this check is on the list at all -- a
    #: property of the FACTOR, not of this site's value ("A divider can force
    #: a driver into a U-turn they will not make"). Section 04 prints it under
    #: the direction marker, which is what turns a table of readings into
    #: something a landowner can argue with.
    #:
    #: Optional for the same reason ``group`` is: a payload stored before the
    #: column existed still validates, and the section omits the line rather
    #: than inventing one.
    means: str | None = None


class CompetitorRow(BaseModel):
    name: str
    operator: str
    distance_m: int
    max_power_kw: float
    points: int


class CompetitorsPayload(BaseModel):
    within_3km: int
    nearest: list[CompetitorRow]
    source: str
    #: The wider rings, added with the direction markers; optional for the
    #: same reason ``SiteFact.group`` is.
    within_5km: int | None = None
    dc_fast_within_3km: int | None = None


class PlainMoney(BaseModel):
    """The same case again, in money an owner can check against a bank
    statement (Track B - R6).

    NPV, IRR and payback are all still above this - R5 kept them - but none
    of them is a number a landowner has ever been handed before. These are:
    what comes in, what goes out, what is left, and the running total against
    the setup cost.

    The annual figures are the STEADY year - the last year of the demand ramp
    - which is the same year ``Scenario.kwh_year`` reports. The earlier years
    are lower, and ``cumulative_paise`` is where that shows: it is the
    engine's own year-by-year cashflow, ramp and all, from year 0 (the build,
    always negative) to the end of the horizon.

    Optional on the parent for the usual reason: a payload stored by
    economics 0.2.0 has none of this, and the sections omit the blocks rather
    than invent them.
    """

    revenue_paise_year: int
    #: Electricity, the operator's cut and the payment gateway - everything
    #: that scales with what is sold. The engine's ``energy_cost_paise``.
    running_cost_paise_year: int
    fixed_cost_paise_year: int
    cash_paise_year: int
    revenue_paise_month: int
    cash_paise_month: int
    #: Year 0 through the horizon, inclusive: ``len`` is ``horizon + 1``.
    #: Negative means the setup money is not back yet.
    cumulative_paise: list[int]


class Scenario(BaseModel):
    label: str
    utilisation: float
    kwh_year: float
    npv_paise: int
    irr_pct: float | None
    payback_years: float | None
    plain: PlainMoney | None = None


class AnchorNote(BaseModel):
    kwh_year: float
    npv_paise: int
    irr_pct: float


class SanctionedLoad(BaseModel):
    full_kva: float
    recommended_kva: float
    recommended_label: str
    saving_paise_year: int
    buffered_kva: float


class PriceSensitivityPoint(BaseModel):
    price_paise_kwh: int
    breakeven_utilisation: float


class CostLine(BaseModel):
    """One line of a breakdown. Per year in ``fixed_costs``, one-off in
    ``capex_lines``, per unit in ``unit_economics``."""

    label: str
    paise: int


class UnitEconomics(BaseModel):
    """One unit's price, and everyone who takes a piece before the site does.

    ``selling_paise_kwh`` minus every deduction is exactly
    ``margin_paise_kwh``, which is the margin both breakevens divide by. The
    engine guarantees it (``roi/engine.py``, ``_reconcile``) so section 05
    can print it as a sentence the reader checks in their head.
    """

    selling_paise_kwh: int
    deductions: list[CostLine]
    margin_paise_kwh: int


class FixedCosts(BaseModel):
    """``annual_fixed_paise``, itemised. The lines sum to the total, and zero
    lines are omitted rather than printed."""

    lines: list[CostLine]
    total_paise_year: int
    total_paise_month: int


class FinancialsPayload(BaseModel):
    capex_paise: int
    selling_price_paise_kwh: int
    energy_tariff_paise_kwh: int
    scenarios: list[Scenario]
    anchor_note: AnchorNote
    sanctioned_load: SanctionedLoad
    price_sensitivity: list[PriceSensitivityPoint]
    #: The working behind the headline (Track B - R6): the one-time budget
    #: summing to ``capex_paise``, the per-unit chain, and the monthly bills.
    #: All optional so a payload stored by economics 0.2.0 still validates;
    #: section 05 falls back to its one-line summary when they are absent.
    capex_lines: list[CostLine] | None = None
    unit_economics: UnitEconomics | None = None
    fixed_costs: FixedCosts | None = None


class CpoRow(BaseModel):
    operator: str
    ours: bool
    revenue_share_pct: float
    platform_fee_paise_year: int
    #: None when the central case never returns the capital - a fact, not 0%.
    irr_p50_pct: float | None
    margin_of_safety_pp: float
    #: The steady-year cash THIS operator's terms leave, from that operator's
    #: own engine run - the same figure section 02 prints, for the operator
    #: section 02 is about. A return is comparable but abstract; this is the
    #: number the owner actually feels, and it is what makes the revenue share
    #: beside it mean something. None on payloads stored before the column
    #: existed, which drops the column rather than printing a blank one.
    cash_p50_paise_year: int | None = None
    uptime: str
    ocpi_roaming: bool
    #: Signed service terms - hours to attend a fault, and the years the owner
    #: is locked in. Both wait on ``cpo_terms`` (PLAN 2.3): until that table
    #: exists the assembler has nothing to put here, so section 06 drops both
    #: columns rather than printing one dash per operator. A column of
    #: repeated placeholder is furniture, which is the same rule ``uptime``
    #: has lived under since this section was written.
    repair_hours: int | None = None
    tie_in_years: float | None = None
    #: How much of THIS operator's own network already sits around the site
    #: (domain/cpo/presence.py). None where the name could not be matched to a
    #: network we inventory, or is not a network at all - unknown, which is a
    #: different fact from zero and must not render as one.
    stations_district: int | None = None
    stations_state: int | None = None
    own_within_3km: int | None = None
    own_within_10km: int | None = None
    #: One plain sentence: what this operator's own nearby stations do to the
    #: volume this site would see. Never a score, never blended with the money.
    presence_note: str = ""


class LedgerRow(BaseModel):
    item: str
    value: str
    source: str
    unverified: bool


class ProvenanceRow(BaseModel):
    label: str
    value: str
    unverified: bool = False


class PublicSourceContext(BaseModel):
    dataset: str
    status: str
    source_name: str
    retrieved_on: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    transformation_version: str | None = None
    time_coverage: str | None = None
    licence: str | None = None
    licence_url: str | None = None


class PublicContextPayload(BaseModel):
    version: Literal["public_context_v1"] = "public_context_v1"
    snapshot_sha256: str
    sources: list[PublicSourceContext]
    grid_conditions: list[str] = []


class ReportPayload(BaseModel):
    public_context: PublicContextPayload | None = None
    report_id: str
    demo: bool
    site: SitePayload
    hardware: HardwarePayload
    breakeven: BreakevenPayload
    predicted: UtilisationBand
    margin_of_safety_pp: float
    verdict: VerdictPayload
    demand: DemandPayload
    site_facts: list[SiteFact]
    competitors: CompetitorsPayload
    financials: FinancialsPayload
    cpo: list[CpoRow]
    ledger: list[LedgerRow]
    #: The ENGINE's own assumption ledger, verbatim (``RoiResult.assumptions``).
    #:
    #: engine.py has written every default that shapes the answer into this
    #: tuple since it was built, and its docstring said "the report's
    #: assumption ledger consumes it verbatim" - which was not true until
    #: R10. Two ledgers existed: this one, generated from the inputs actually
    #: used, and ``ledger`` above, hand-written in this module and printed.
    #: Only the second reached a page, so only the first could quietly go
    #: stale. They are different things and both belong in section 10: these
    #: are the MODEL's choices (discount rate, O&M share, what the utilisation
    #: ceiling means), ``ledger`` is where each INPUT came from and whether
    #: anyone has confirmed it.
    #:
    #: Empty on payloads stored before R10; section 10 then prints the input
    #: table alone, as it always did.
    model_assumptions: list[str] = []
    provenance: list[ProvenanceRow]
    #: The day this payload was assembled, ISO. A document with no date on it
    #: cannot defend itself, which is the whole job of section 11 - and the
    #: date has to be IN the payload rather than read off the row at render
    #: time, because the payload is the data of record and is served verbatim
    #: (Rule 9). None on payloads stored before R10.
    generated_at: str | None = None
