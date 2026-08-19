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
    utilisation: float
    kwh_year: float
    kwh_day: float


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


class SiteFact(BaseModel):
    label: str
    value: str
    source: str
    unverified: bool


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


class Scenario(BaseModel):
    label: str
    utilisation: float
    kwh_year: float
    npv_paise: int
    irr_pct: float | None
    payback_years: float | None


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


class FinancialsPayload(BaseModel):
    capex_paise: int
    selling_price_paise_kwh: int
    energy_tariff_paise_kwh: int
    scenarios: list[Scenario]
    anchor_note: AnchorNote
    sanctioned_load: SanctionedLoad
    price_sensitivity: list[PriceSensitivityPoint]


class CpoRow(BaseModel):
    operator: str
    ours: bool
    revenue_share_pct: float
    platform_fee_paise_year: int
    irr_p50_pct: float
    margin_of_safety_pp: float
    uptime: str
    ocpi_roaming: bool


class LedgerRow(BaseModel):
    item: str
    value: str
    source: str
    unverified: bool


class ProvenanceRow(BaseModel):
    label: str
    value: str
    unverified: bool = False


class ReportPayload(BaseModel):
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
    provenance: list[ProvenanceRow]
