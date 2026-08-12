"""``api_usage_events`` - PART C.1. Append-only spend meter.

AGENTS.md constraint 10: every metered external call writes one row *before*
its response is used. Including retries. Including errors. Including cache
hits.

Cache hits are logged with the cost they *avoided*, because Part 1's exit
criterion is "median cascade cost per address = Rs 0" and that has to be
evidenced rather than asserted.

Never UPDATE. Never DELETE. A wrong row is still evidence.
"""

from __future__ import annotations

import datetime as dt
import enum
import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

#: JSONB in Postgres, plain JSON elsewhere. The variants keep the production
#: column types correct while letting the metering tests run on SQLite without
#: standing up a database.
#:
#: ``none_as_null`` so an absent detail is a SQL NULL, not the JSON value
#: ``null`` - otherwise "no detail" and "detail is literally null" become
#: indistinguishable in a spend query.
JsonColumn = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")

#: SQLite autoincrements only plain INTEGER primary keys, never BIGINT.
BigIntPk = BigInteger().with_variant(Integer(), "sqlite")


class UsageStatus(enum.StrEnum):
    OK = "ok"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    CAPPED = "capped"  # we refused the call ourselves
    CACHE_HIT = "cache_hit"  # cost avoided, not incurred


#: Statuses that represent money actually leaving the building.
BILLABLE_STATUSES = frozenset({UsageStatus.OK, UsageStatus.ERROR, UsageStatus.RATE_LIMITED})


class ApiUsageEvent(Base):
    __tablename__ = "api_usage_events"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    #: LLM only. NULL for geocoding and maps.
    model: Mapped[str | None] = mapped_column(String(128))

    #: Calls, or input tokens for an LLM.
    units_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Output tokens. NULL where the concept does not apply.
    units_out: Mapped[int | None] = mapped_column(Integer)

    #: Money in paise as integers (AGENTS.md). Formatted to Rs only at the
    #: render boundary, which for this project is frontend/src/lib/money.ts.
    cost_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    #: Which price card priced this. Lets a historical cost be recomputed.
    price_card_version: Mapped[str] = mapped_column(String(64), nullable=False)

    #: The quota window this counts against. First of the month, UTC.
    billing_month: Mapped[dt.date] = mapped_column(Date, nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False)

    #: What triggered the spend - a site resolution, a tariff parse, a poll.
    caused_by: Mapped[str | None] = mapped_column(String(64))
    site_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())

    latency_ms: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn)
    error: Mapped[str | None] = mapped_column(Text)

    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # The counter's hot path: sum this month's units for one provider.
        Index(
            "ix_api_usage_provider_month",
            "provider",
            "billing_month",
            "status",
        ),
        Index("ix_api_usage_occurred_at", "occurred_at"),
    )
