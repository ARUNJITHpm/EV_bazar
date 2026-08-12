"""Enable PostGIS and create the schema_version registry.

Revision ID: 0001
Revises:
Create Date: 2026-08-12

The first migration does two things and nothing else:

  1. CREATE EXTENSION postgis - every spatial query in Part 1 depends on it.
  2. schema_version - Rule 1. A report generated today must be regenerable
     in three years, which means we must be able to say what shape the
     tables were in when it was made.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    schema_version = op.create_table(
        "schema_version",
        sa.Column("version", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.bulk_insert(
        schema_version,
        [{"version": 1, "note": "PostGIS enabled; schema_version registry created."}],
    )


def downgrade() -> None:
    op.drop_table("schema_version")
    # The extension is deliberately NOT dropped. Other databases in the same
    # cluster may depend on it, and dropping it cascades to every geometry
    # column in the database.
