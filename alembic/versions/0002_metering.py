"""PART C.1 - spend metering tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-12

Two tables:

  api_usage_events     append-only; one row per metered external call
  provider_price_cards effective-dated, exactly like the SERC tariff table

Together they turn the ``monthly_cap`` in config.py from a declaration into
an enforced limit (AGENTS.md constraints 7 and 10).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_price_cards",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(64), nullable=False, unique=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128)),
        sa.Column("micro_paise_per_unit_in", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("micro_paise_per_unit_out", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("free_units_per_month", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("source_url", sa.Text()),
        sa.Column("note", sa.Text()),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_price_card_date_range",
        ),
    )
    op.create_index(
        "ix_price_card_lookup",
        "provider_price_cards",
        ["provider", "operation", "model", "effective_from"],
    )

    op.create_table(
        "api_usage_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128)),
        sa.Column("units_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("units_out", sa.Integer()),
        sa.Column("cost_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("price_card_version", sa.String(64), nullable=False),
        sa.Column("billing_month", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("caused_by", sa.String(64)),
        sa.Column("site_id", postgresql.UUID(as_uuid=True)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("detail", postgresql.JSONB()),
        sa.Column("error", sa.Text()),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # The counter's hot path: sum this month's units for one provider.
    op.create_index(
        "ix_api_usage_provider_month",
        "api_usage_events",
        ["provider", "billing_month", "status"],
    )
    op.create_index("ix_api_usage_occurred_at", "api_usage_events", ["occurred_at"])

    # Append-only, enforced in the database rather than by convention.
    # AGENTS.md constraint 3: a wrong row is still evidence.
    op.execute(
        """
        CREATE RULE api_usage_events_no_update AS
            ON UPDATE TO api_usage_events DO INSTEAD NOTHING;
        CREATE RULE api_usage_events_no_delete AS
            ON DELETE TO api_usage_events DO INSTEAD NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (2, 'PART C.1 metering: api_usage_events + provider_price_cards')
        """
    )


def downgrade() -> None:
    op.execute("DROP RULE IF EXISTS api_usage_events_no_update ON api_usage_events")
    op.execute("DROP RULE IF EXISTS api_usage_events_no_delete ON api_usage_events")
    op.drop_table("api_usage_events")
    op.drop_table("provider_price_cards")
    op.execute("DELETE FROM schema_version WHERE version = 2")
