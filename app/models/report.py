"""``reports`` - PLAN 5's data of record.

AGENTS.md rule 9: the report payload is persisted as JSONB and **served from
storage** - ``GET /api/internal/reports/{id}`` returns the stored payload
verbatim and never re-runs the pipeline against today's data. Every number a
customer saw is recoverable from this row forever; that is the guarantee that
matters in a dispute (STACK.md §6).

The version stamps are duplicated out of the payload into columns purely so
"which reports did economics 0.1.0 produce" is a WHERE clause, not a JSON
scan. The payload remains the authority.

Immutable by rule (migration 0012), with one stated exception: a row whose
payload carries ``demo: true`` may be regenerated in place by the demo script
- a demonstration is versionless by definition, and letting it refresh beats
accumulating dead demo rows. Customer reports never update; a correction is a
NEW report with a new id, superseding the old, which stays retrievable.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

#: JSONB in Postgres, plain JSON elsewhere - same variant every table uses.
JsonColumn = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class Report(Base):
    __tablename__ = "reports"

    #: Client-visible - it appears in report URLs. A string so demo reports can
    #: carry a readable id; customer reports use UUID strings, which do not
    #: leak volume the way a sequence would (same reasoning as sites.site_id).
    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    site_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), ForeignKey("sites.site_id"))

    #: The 7-section payload, exactly as the frontend renders it. The data of
    #: record - served verbatim, never recomputed.
    payload: Mapped[dict[str, Any]] = mapped_column(JsonColumn, nullable=False)

    economics_version: Mapped[str] = mapped_column(String(16), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    #: NULL until the Playwright PDF path stamps a pinned build (STACK.md §6).
    renderer_version: Mapped[str | None] = mapped_column(String(64))

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_reports_site", "site_id"),)
