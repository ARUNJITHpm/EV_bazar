"""Alembic-only SQLite fixture schema for the actual prediction ORM ledger."""

import sqlalchemy as sa

from alembic import op


def upgrade() -> None:
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("economics_version", sa.String(16), nullable=False),
        sa.Column("predicted_p10", sa.Float(), nullable=False),
        sa.Column("predicted_p50", sa.Float(), nullable=False),
        sa.Column("predicted_p90", sa.Float(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("predicted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actual_kwh", sa.Float()),
        sa.Column("actual_observed_at", sa.DateTime(timezone=True)),
        sa.Column("analytics_context", sa.JSON()),
    )
