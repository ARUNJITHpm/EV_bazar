"""``provider_price_cards`` - PART C.1.

Effective-dated rows, **exactly like the SERC tariff table**. Never overwrite
a price; insert a new row and close the old one's date range.

Same reasoning as tariffs: a cost computed last March must still recompute to
last March's price. Providers change pricing, and a spend report that
silently reprices history is worse than no spend report.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, CheckConstraint, Date, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

#: SQLite autoincrements only a plain INTEGER primary key, never BIGINT - the
#: same shim ``api_usage.py`` carries, so the card lookup and seeding can be
#: tested without standing up Postgres. Production DDL is unchanged.
BigIntPk = BigInteger().with_variant(Integer(), "sqlite")


class ProviderPriceCard(Base):
    __tablename__ = "provider_price_cards"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)

    #: Stable identifier quoted on every usage event it prices.
    version: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    #: LLM only - pricing differs per model. NULL means "all models".
    model: Mapped[str | None] = mapped_column(String(128))

    #: Paise per unit, scaled by 1e6 so sub-paise LLM token prices survive as
    #: integers. Rs 0.30 per 1k input tokens = 30 paise / 1000 tokens
    #: = 0.03 paise/token = 30_000 micro-paise per token.
    micro_paise_per_unit_in: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    micro_paise_per_unit_out: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    #: Free allowance per billing month, in units. Google India-billed
    #: Essentials is 70k calls/month; beyond that it is $5 per 1,000.
    free_units_per_month: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    effective_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    #: NULL means "current". Superseding a card sets this, never deletes.
    effective_to: Mapped[dt.date | None] = mapped_column(Date)

    source_url: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_price_card_date_range",
        ),
        Index("ix_price_card_lookup", "provider", "operation", "model", "effective_from"),
    )
