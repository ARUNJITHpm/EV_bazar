"""Declarative base.

Every table in the project hangs off this metadata so that Alembic
autogenerate sees it. AGENTS.md: never CREATE TABLE outside a migration.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
