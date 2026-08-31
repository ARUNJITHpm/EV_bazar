"""The /assess teaser - PLAN G.2's front door. PURE.

Breakeven utilisation from arithmetic alone: what share of rated capacity
this site must sell to cover its fixed costs at the assumed price. No model
is consulted, so nothing here is a prediction - which is exactly why the
teaser can exist before the poller has recorded a single row, and why it
writes no ``predictions`` row (rule 5 governs model outputs; there is none).

Every number the customer did not supply is the v0 archetype default - the
same figures the demo report's ledger declares as "archetype default" - and
each tap echoes back what it changed, so the teaser shows its work the way
the report does.

The customer-facing taps are the design flow's four (design/flow-images):
how much space, whether a transformer is near and how big, how far it is, and
what the site is for. Of these, only SPACE moves the breakeven number - more
plugs spread the fixed costs over more capacity. The transformer answers move
CAPEX (a new transformer, the cabling run to it), which breakeven does not
read; their echo says so instead of pretending the number moved, exactly as
the shipped firewall does. The wiring numbers are signed off in
design/DECISIONS.md ("Task 3 - the design inputs, wired for real").

Money only from ``compute_roi`` (AGENTS.md rule 1): this module builds the
engine's inputs and reads its outputs, nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.roi.engine import (
    MANAGED_PEAK_FACTOR,
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
RATED_KW_EACH = 60.0
SELLING_PAISE_PER_KWH = 2200
RENT_PAISE_PER_MONTH = 4_000_000

#: Capex line items that do not scale with the connector count. Hardware is
#: not here: it scales, at PER_CONNECTOR_HARDWARE_PAISE below.
CIVIL_PAISE = 30_000_000
NEW_TRANSFORMER_PAISE = 20_000_000
DISCOM_CONNECTION_PAISE = 10_000_000
SIGNAGE_CANOPY_PAISE = 2_000_000

#: ---- The signed-off wiring numbers (design/DECISIONS.md, Task 3) ----------
#: Hardware per connector. The v0 archetype was ₹12.0 L of hardware for two
#: 60 kW connectors; ₹6.0 L each is that same figure made to scale rather than
#: fixed, so the default two-connector site is byte-identical to before.
PER_CONNECTOR_HARDWARE_PAISE = 60_000_000
#: Connectors per "how much space" tier. More plugs is the one design input
#: that lowers breakeven: the fixed costs (demand charge, rent) spread over a
#: larger ceiling.
CONNECTORS_BY_SPACE = {"small": 2, "medium": 4, "large": 6}
DEFAULT_CONNECTORS = 2
#: LT cabling + trenching from the transformer to the site, per metre. Feeds
#: the connection cost, so it moves payback, not breakeven.
CABLE_PAISE_PER_M = 200_000  # ₹2,000/m


@dataclass(frozen=True)
class Taps:
    """The customer taps, every one optional. ``None`` means the tap was
    left unanswered and the archetype default applies - shown as such, never
    silently.

    ``space``, ``transformer_kva`` and ``transformer_distance_m`` are the
    design flow's inputs. The rest are engine levers the current flow does not
    surface but the arithmetic still honours if a caller supplies them (they
    default to the archetype), so the teaser stays general."""

    #: "small" | "medium" | "large" - how much space, driving the connector
    #: count. The one tap that moves breakeven.
    space: str | None = None
    #: An existing transformer's nameplate kVA. At or above the station's
    #: managed-peak kVA it covers the load and the new-transformer cost drops.
    transformer_kva: float | None = None
    #: Metres from that transformer to the site - the cabling run to price.
    transformer_distance_m: float | None = None
    #: What the owner wants the site to do (income / fleet / visitors). It
    #: changes which operators suit the site - the matching half of the
    #: product - and none of this arithmetic; the echo says exactly that.
    intent: str | None = None

    #: Latent engine levers, not asked by the design flow (archetype default
    #: applies). Kept so the pure engine stays fully addressable.
    existing_connection: bool | None = None
    sanctioned_kva: float | None = None
    transformer_on_site: bool | None = None
    land_owned: bool | None = None


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


def _connectors(taps: Taps) -> int:
    if taps.space is None:
        return DEFAULT_CONNECTORS
    return CONNECTORS_BY_SPACE.get(taps.space, DEFAULT_CONNECTORS)


def _capex(taps: Taps, connectors: int, managed_peak_kva: float) -> Capex:
    """Build cost for this site. Hardware scales with the plug count; the
    transformer and cabling lines follow the customer's transformer answers."""
    hardware = connectors * PER_CONNECTOR_HARDWARE_PAISE

    # An existing transformer covers the load if its nameplate meets the
    # station's managed-peak kVA; then no new transformer is built. (The
    # latent transformer_on_site lever still forces it to zero if set.)
    covered = taps.transformer_on_site is True or (
        taps.transformer_kva is not None and taps.transformer_kva >= managed_peak_kva
    )
    transformer = 0 if covered else NEW_TRANSFORMER_PAISE

    discom = 0 if taps.existing_connection else DISCOM_CONNECTION_PAISE
    cabling = round((taps.transformer_distance_m or 0.0) * CABLE_PAISE_PER_M)

    return Capex(
        hardware_paise=hardware,
        civil_paise=CIVIL_PAISE,
        transformer_paise=transformer,
        discom_connection_paise=discom + cabling,
        signage_canopy_paise=SIGNAGE_CANOPY_PAISE,
    )


def _run(
    tariff: TariffTerms, kva: float, capex: Capex, rent_paise_month: int, connectors: int
) -> RoiResult:
    chargers = (ChargerSpec(kw=RATED_KW_EACH, count=connectors),)
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


def _lakh(paise: float) -> str:
    return f"₹{paise / 10_000_000:.1f} L"


def _echoes(taps: Taps, connectors: int, managed_peak_kva: float, cabling_paise: int) -> tuple[
    TapEcho, ...
]:
    # SPACE - the one that moves the number.
    if taps.space is None:
        space_fx = (
            f"not provided - {DEFAULT_CONNECTORS} connectors assumed, the archetype default"
        )
    else:
        tier = {"small": "a couple of car parks", "medium": "a corner of a plot or yard",
                "large": "an open site"}.get(taps.space, "the space given")
        space_fx = (
            f"{tier} - {connectors} connectors; more plugs spread the fixed costs over more "
            "capacity, which is why this breakeven figure moved"
        )

    # TRANSFORMER near + how big -> whether a new one is built (capex).
    if taps.transformer_kva is None:
        tx_fx = (
            f"not provided - a new transformer ({_lakh(NEW_TRANSFORMER_PAISE)}) stays in capex; "
            "that moves the full report's payback, not this breakeven"
        )
    elif taps.transformer_kva >= managed_peak_kva:
        tx_fx = (
            f"a {taps.transformer_kva:.0f} kVA transformer covers the station's "
            f"~{managed_peak_kva:.0f} kVA managed peak, so the {_lakh(NEW_TRANSFORMER_PAISE)} "
            "new-transformer cost drops out - that moves payback, not this breakeven"
        )
    else:
        tx_fx = (
            f"{taps.transformer_kva:.0f} kVA is under the station's ~{managed_peak_kva:.0f} kVA "
            f"managed peak, so a new transformer ({_lakh(NEW_TRANSFORMER_PAISE)}) stays in "
            "capex - payback, not this breakeven"
        )

    # DISTANCE -> the cabling run (capex).
    if taps.transformer_distance_m is None:
        dist_fx = "not provided - no cabling run is priced yet; the site survey sets it"
    else:
        dist_fx = (
            f"{taps.transformer_distance_m:.0f} m of cabling at ₹2,000/m adds "
            f"{_lakh(cabling_paise)} to the connection cost - payback, not this breakeven"
        )

    # INTENT -> operator match, never arithmetic.
    if taps.intent is not None:
        intent_fx = (
            f"noted ({taps.intent}) - it changes which operators suit the site, not this arithmetic"
        )
    else:
        intent_fx = "not provided - it would change the operator match, not this arithmetic"

    return (
        TapEcho("How much space is there?", taps.space is not None, space_fx),
        TapEcho("Transformer near the site?", taps.transformer_kva is not None, tx_fx),
        TapEcho("How far is the transformer?", taps.transformer_distance_m is not None, dist_fx),
        TapEcho("What should this site do?", taps.intent is not None, intent_fx),
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

    connectors = _connectors(taps)
    full_kva = connectors * RATED_KW_EACH / POWER_FACTOR
    managed_peak_kva = full_kva * MANAGED_PEAK_FACTOR

    capex = _capex(taps, connectors, managed_peak_kva)
    cabling_paise = round((taps.transformer_distance_m or 0.0) * CABLE_PAISE_PER_M)
    rent = 0 if taps.land_owned else RENT_PAISE_PER_MONTH

    # Same discipline as assemble.py: when the customer has not named a
    # sanctioned load, price the kVA we would actually advise - the engine's
    # managed-peak recommendation off a full-load base run.
    if taps.sanctioned_kva is not None:
        kva = taps.sanctioned_kva
    else:
        base = _run(tariff, full_kva, capex, rent, connectors)
        kva = next(o for o in base.sanctioned_load_options if o.name.startswith("managed")).kva

    run = _run(tariff, kva, capex, rent, connectors)

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
        connectors=connectors,
        rated_kw_each=RATED_KW_EACH,
        selling_paise_per_kwh=SELLING_PAISE_PER_KWH,
        sanctioned_kva=kva,
        energy_tariff_paise_per_kwh=tariff_row.energy_paise_per_kwh,
        tariff_source=f"{tariff_row.discom or 'SERC'} · {tariff_row.order_number}",
        taps=_echoes(taps, connectors, managed_peak_kva, cabling_paise),
        notes=tuple(notes),
    )
