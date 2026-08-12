"""``schema_version`` - Rule 1 support.

Reports must be byte-regenerable in three years. Every report stamps the
``schema_version`` that was current when it was generated, so a stored
payload can always be matched back to the shape of the tables that made it.

Append-only, like everything else here: bumping the schema inserts a row.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SchemaVersion(Base):
    __tablename__ = "schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    applied_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
