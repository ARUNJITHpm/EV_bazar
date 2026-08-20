"""The /assess teaser - PLAN G.2's front door. PURE.

Breakeven utilisation from arithmetic alone: what share of rated capacity
this site must sell to cover its fixed costs at the assumed price. No model
is consulted, so nothing here is a prediction - which is exactly why the
teaser can exist before the poller has recorded a single row, and why it
writes no ``predictions`` row (rule 5 governs model outputs; there is none).

Every number the customer did not supply is the v0 archetype default - the
same figures the demo report's ledger declares as "archetype default" - and
each of the five taps echoes back what it changed, so the teaser shows its
work the way the report does. Two of the taps (existing connection,
transformer) move CAPEX, which breakeven does not read; their echo says so
instead of pretending the number moved.

Money only from ``compute_roi`` (AGENTS.md rule 1): this module builds the
engine's inputs and reads its outputs, nothing more.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from app.domain.roi.engine import (
    Capex,
    ChargerSpec,
    RoiInputs,
    RoiResult,
    SiteOpex,
    TariffTerms,
    compute_roi,
    max_kwh_year,
)
from app.models.tariffs import ElectricityTariff

#: PLAN 3.2's power factor; the same constant assemble.py uses.
POWER_FACTOR = 0.9

#: The v0 archetype defaults - identical to the demo report's spec, because
#: the demo's ledger already calls these "archetype default" and two surfaces
#: quoting two different defaults for the same pin would be indefensible.
ARCHETYPE = "urban_office_arterial"
CONNECTORS = 2
RATED_KW_EACH = 60.0
SELLING_PAISE_PER_KWH = 2200
DEFAULT_CAPEX = Capex(
    hardware_paise=120_000_000,
    civil_paise=30_000_000,
    transformer_paise=20_000_000,
    discom_connection_paise=10_000_000,
    signage_canopy_paise=2_000_000,
)
RENT_PAISE_PER_MONTH = 4_000_000


@dataclass(frozen=True)
class Taps:
    """The five customer taps, every one optional. ``None`` means the tap was
    left unanswered and the archetype default applies - shown as such, never
    silently."""

    existing_connection: bool | None = None
    sanctioned_kva: float | None = None
    transformer_on_site: bool | None = None
    land_owned: bool | None = None
    budget_band: str | None = None


@dataclass(frozen=True)
class TapEcho:
    """One tap, echoed back: what was (or was not) provided, and what it did
    to the arithmetic. The honesty firewall in miniature - an input that
    changed nothing must say so."""

    label: str
    provided: bool
    effect: str


@dataclass(frozen=True)
class TeaserResult:
    """The certain number and everything needed to defend it. ``utilisation``
    is None when the margin is negative at the assumed price - a real answer
    ("no utilisation breaks even"), not an error."""

    utilisation: float | None
    kwh_year: float | None
    kwh_day: float | None
    connectors: int
    rated_kw_each: float
    selling_paise_per_kwh: int
    sanctioned_kva: float
    energy_tariff_paise_per_kwh: int
    #: Provenance, straight off the tariff row: a breakeven number that cannot
    #: name its SERC order is not defensible to a customer whose bill disagrees.
    tariff_source: str
    taps: tuple[TapEcho, ...]
    notes: tuple[str, ...]


def _run(tariff: TariffTerms, kva: float, capex: Capex, rent_paise_month: int) -> RoiResult:
    chargers = (ChargerSpec(kw=RATED_KW_EACH, count=CONNECTORS),)
    return compute_roi(
        RoiInputs(
            chargers=chargers,
            tariff=tariff,
            capex=capex,
            opex=SiteOpex(sanctioned_kva=kva, rent_paise_per_month=rent_paise_month),
            selling_paise_per_kwh=SELLING_PAISE_PER_KWH,
            # Breakeven does not read the ramp, but the engine (rightly)
            # refuses an empty one - one nominal year satisfies it.
            kwh_by_year=(max_kwh_year(chargers) * 0.15,),
        )
    )


def _lakh(paise: int) -> str:
    return f"₹{paise / 10_000_000:.1f} L"


def _echoes(taps: Taps, recommended_kva: float) -> tuple[TapEcho, ...]:
    discom, transformer = DEFAULT_CAPEX.discom_connection_paise, DEFAULT_CAPEX.transformer_paise
    rent_month = f"₹{RENT_PAISE_PER_MONTH / 100:,.0f}/month"

    if taps.existing_connection is None:
        connection = f"not provided - a new discom connection ({_lakh(discom)}) stays in capex"
    elif taps.existing_connection:
        connection = (
            f"the {_lakh(discom)} new-connection cost drops out of capex; that moves the "
            "full report's payback, not breakeven utilisation"
        )
    else:
        connection = f"a new discom connection ({_lakh(discom)}) is in the capex"

    if taps.sanctioned_kva is not None:
        load = f"demand charges priced at the supplied {taps.sanctioned_kva:.0f} kVA"
    else:
        load = (
            f"not provided - the engine recommends managed-peak {recommended_kva:.0f} kVA "
            "and prices that"
        )

    if taps.transformer_on_site is None:
        transformer_fx = f"not provided - a new transformer ({_lakh(transformer)}) stays in capex"
    elif taps.transformer_on_site:
        transformer_fx = (
            f"the {_lakh(transformer)} transformer drops out of capex; that moves the "
            "full report's payback, not breakeven utilisation"
        )
    else:
        transformer_fx = f"a new transformer ({_lakh(transformer)}) is in the capex"

    if taps.land_owned is None:
        land = f"not provided - leased assumed, {rent_month} rent stays in the fixed costs"
    elif taps.land_owned:
        land = "owned - rent drops to zero, which lowers breakeven directly"
    else:
        land = f"leased - {rent_month} rent stays in the fixed costs"

    if taps.budget_band is not None:
        budget = (
            f"noted ({taps.budget_band}) - it changes no arithmetic; "
            "capex stays the archetype default"
        )
    else:
        budget = "not provided - it would change no arithmetic; capex stays the archetype default"

    connection_given = taps.existing_connection is not None
    return (
        TapEcho("Existing electricity connection?", connection_given, connection),
        TapEcho("Sanctioned load (kVA)?", taps.sanctioned_kva is not None, load),
        TapEcho("Transformer on site?", taps.transformer_on_site is not None, transformer_fx),
        TapEcho("Land owned or leased?", taps.land_owned is not None, land),
        TapEcho("Budget band?", taps.budget_band is not None, budget),
    )


def compute_teaser(tariff_row: ElectricityTariff, taps: Taps) -> TeaserResult:
    """The teaser for one pin, given the EV tariff row governing its state.

    Pure: the caller looks the row up (``state_ev_tariff``) and decides what
    "today" means; this function only does arithmetic on what it is handed.
    """
    tariff = TariffTerms(
        energy_paise_per_kwh=tariff_row.energy_paise_per_kwh,
        demand_paise_per_kva_month=tariff_row.demand_paise_per_kva_month,
        fixed_paise_per_month=tariff_row.fixed_paise_per_month,
        duty_pct=tariff_row.duty_bp / 10_000,
    )
    default_discom = DEFAULT_CAPEX.discom_connection_paise
    capex = dataclasses.replace(
        DEFAULT_CAPEX,
        discom_connection_paise=0 if taps.existing_connection else default_discom,
        transformer_paise=0 if taps.transformer_on_site else DEFAULT_CAPEX.transformer_paise,
    )
    rent = 0 if taps.land_owned else RENT_PAISE_PER_MONTH

    # Same discipline as assemble.py: when the customer has not named a
    # sanctioned load, price the kVA we would actually advise - the engine's
    # managed-peak recommendation off a full-load base run.
    full_kva = CONNECTORS * RATED_KW_EACH / POWER_FACTOR
    if taps.sanctioned_kva is not None:
        kva = taps.sanctioned_kva
    else:
        base = _run(tariff, full_kva, capex, rent)
        kva = next(o for o in base.sanctioned_load_options if o.name.startswith("managed")).kva

    run = _run(tariff, kva, capex, rent)

    notes = [
        f"Hardware, civil and price assumptions are the {ARCHETYPE} archetype defaults - "
        "the full report itemises every one in its assumption ledger.",
        "This is arithmetic, not a prediction: whether the site will REACH this "
        "utilisation is the full report's question, answered as a P10-P90 band.",
    ]
    if run.breakeven_utilisation is None:
        # The engine's own reason, repeated verbatim - never paraphrased into
        # something softer.
        notes.extend(a for a in run.assumptions if "no utilisation breaks even" in a)

    return TeaserResult(
        utilisation=run.breakeven_utilisation,
        kwh_year=run.breakeven_kwh_year,
        kwh_day=None if run.breakeven_kwh_year is None else run.breakeven_kwh_year / 365.0,
        connectors=CONNECTORS,
        rated_kw_each=RATED_KW_EACH,
        selling_paise_per_kwh=SELLING_PAISE_PER_KWH,
        sanctioned_kva=kva,
        energy_tariff_paise_per_kwh=tariff_row.energy_paise_per_kwh,
        tariff_source=f"{tariff_row.discom or 'SERC'} · {tariff_row.order_number}",
        taps=_echoes(taps, kva),
        notes=tuple(notes),
    )
