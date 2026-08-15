"""``electricity_tariffs`` and ``subsidy_rules`` - PART 3.1.

The tariff table is the price of the product's raw material. A site resolves
to a district, the district's state picks the tariff, and the tariff decides
the margin on every kWh - so a wrong or stale row here is wrong in every
report and looks completely normal, the same failure mode as a wrong district.

Both tables are **effective-dated and never overwritten** - the discipline
``provider_price_cards`` copied from this design before this table existed.
A report generated last March must regenerate with last March's tariff, so a
revision is a new row with a new ``effective_from`` and the old row's
``effective_to`` closed. Deleting or updating a superseded row destroys the
ability to reproduce history, which is the product's whole claim.

Every monetary value is integer paise (AGENTS.md). Percentages are integer
basis points (``duty_bp``: 1200 = 12%) so the database never holds a float
that drifts.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

#: SQLite autoincrements only plain INTEGER PKs - the shim price_cards carries.
BigIntPk = BigInteger().with_variant(Integer(), "sqlite")
JsonColumn = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class ElectricityTariff(Base):
    """One consumer category's tariff in one state, for one date range.

    ``tod_bands`` holds the time-of-day structure verbatim as published:
    a list of ``{"name": "peak", "hours": "18-22", "delta_paise_per_kwh": 120,
    "share": 0.25}``. The ``share`` (what fraction of a charging site's energy
    falls in the band) is OUR modelling assumption, not the SERC's - it feeds
    the ROI engine's ToD split and belongs in the assumption ledger.
    """

    __tablename__ = "electricity_tariffs"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)

    lgd_state_code: Mapped[int] = mapped_column(
        Integer, ForeignKey("states.lgd_state_code"), nullable=False
    )
    #: The distribution company, when the state has more than one regime
    #: (e.g. Maharashtra). NULL = the state's single/default DISCOM.
    discom: Mapped[str | None] = mapped_column(String(64))

    #: The SERC's own category name, verbatim: "LT-VIA EV", "HT-Commercial".
    consumer_category: Mapped[str] = mapped_column(String(128), nullable=False)
    #: True when the category is an EV-charging-specific tariff.
    ev_specific: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    energy_paise_per_kwh: Mapped[int] = mapped_column(Integer, nullable=False)
    demand_paise_per_kva_month: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fixed_paise_per_month: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Electricity duty + cess on the energy bill, in basis points (1200 = 12%).
    duty_bp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tod_bands: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonColumn)

    effective_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    #: NULL means "current". Superseding sets this; nothing ever deletes.
    effective_to: Mapped[dt.date | None] = mapped_column(Date)

    #: The SERC order this row was typed from. Not optional: a tariff without
    #: provenance cannot be defended to the customer whose bill disagrees.
    order_number: Mapped[str] = mapped_column(String(128), nullable=False)
    source_pdf: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_tariff_date_range",
        ),
        CheckConstraint("energy_paise_per_kwh > 0", name="ck_tariff_energy_positive"),
        Index("ix_tariff_lookup", "lgd_state_code", "consumer_category", "effective_from"),
    )


class SubsidyRule(Base):
    """One capital-subsidy or incentive rule - PM E-DRIVE, a state EV policy.

    Sibling of the tariff table with the same effective-dating discipline,
    because subsidies change amortised capex enough to flip verdicts, and a
    verdict computed under last year's scheme must recompute under it.

    Exactly one of ``amount_paise`` (fixed grant) or ``rate_bp`` (percentage
    of eligible capex, basis points) is set - enforced by a check constraint
    rather than convention.
    """

    __tablename__ = "subsidy_rules"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)

    #: NULL = a central scheme (PM E-DRIVE) that applies in every state.
    lgd_state_code: Mapped[int | None] = mapped_column(Integer, ForeignKey("states.lgd_state_code"))
    scheme: Mapped[str] = mapped_column(String(128), nullable=False)
    #: Which hardware the rule covers: "DC-60kW", "AC-22kW", "any".
    charger_class: Mapped[str] = mapped_column(String(64), nullable=False, default="any")

    amount_paise: Mapped[int | None] = mapped_column(BigInteger)
    #: Percentage of eligible capex, basis points (3000 = 30%).
    rate_bp: Mapped[int | None] = mapped_column(Integer)
    #: Eligibility conditions verbatim - first N chargers, public access, etc.
    #: Free text on purpose: conditions are read by the human filling the ROI
    #: inputs, never parsed by code.
    conditions: Mapped[str | None] = mapped_column(Text)

    effective_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[dt.date | None] = mapped_column(Date)

    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_subsidy_date_range",
        ),
        CheckConstraint(
            "(amount_paise IS NULL) != (rate_bp IS NULL)",
            name="ck_subsidy_amount_xor_rate",
        ),
        Index("ix_subsidy_lookup", "lgd_state_code", "charger_class", "effective_from"),
    )
