"""PART 3.2 - the ROI engine. PURE, and structurally so.

No database, no network, no config, no clock: the import-linter contract
"ROI engine is pure" forbids this package from importing app.db, app.models,
app.api, app.metering, app.config, httpx, sqlalchemy - so purity is enforced
at CI, not remembered.

Why it matters this much: the verdict logic lives here, and PART 7's honesty
firewall depends on nothing - not a commission, not a partner, not a panel -
being able to reach in and bend a number. A pure function of its inputs is
the strongest form of that guarantee.

Everything monetary is integer paise. Percentages cross the boundary as
floats (0.07 = 7%) because they are ratios, not money.
"""

from __future__ import annotations

from app.domain.roi.engine import (
    ECONOMICS_VERSION,
    Capex,
    ChargerSpec,
    CpoTerms,
    Financing,
    FleetAnchor,
    PriceSensitivityPoint,
    RoiInputs,
    RoiResult,
    SanctionedLoadOption,
    SiteOpex,
    Solar,
    TariffTerms,
    TodBand,
    YearRow,
    compute_roi,
)

__all__ = [
    "ECONOMICS_VERSION",
    "Capex",
    "ChargerSpec",
    "CpoTerms",
    "Financing",
    "FleetAnchor",
    "PriceSensitivityPoint",
    "RoiInputs",
    "RoiResult",
    "SanctionedLoadOption",
    "SiteOpex",
    "Solar",
    "TariffTerms",
    "TodBand",
    "YearRow",
    "compute_roi",
]
