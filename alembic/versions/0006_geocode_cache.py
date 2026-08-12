"""PART 1.3 - the geocode cache (L1 of the cascade).

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-12

One plain key-value table. Not append-only and not partitioned: a cache entry
is meant to be overwritten - a miss becomes a hit when a human resolves it
through the manual queue, and a stale coordinate is re-fetched by deleting its
row. The provenance that matters (which geocoder, which raw response) lives in
the row itself, not in a history of the row.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "geocode_cache",
        sa.Column("normalised_input", sa.String(512), primary_key=True),
        sa.Column("lat", sa.Float()),
        sa.Column("lng", sa.Float()),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("confidence", sa.String(8)),
        sa.Column("display_name", sa.Text()),
        sa.Column("raw_response", postgresql.JSONB()),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
    )
    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (6, 'PART 1.3 geocode cache: geocode_cache (L1 of the cascade)')
        """
    )


def downgrade() -> None:
    op.drop_table("geocode_cache")
    op.execute("DELETE FROM schema_version WHERE version = 6")
