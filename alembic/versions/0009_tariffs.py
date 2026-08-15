"""PART 3.1 - electricity tariffs and the subsidy ledger.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-15

Two effective-dated tables, never overwritten - the discipline
provider_price_cards copied from this design. A report generated last March
must regenerate with last March's tariff and last March's subsidy scheme.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "electricity_tariffs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "lgd_state_code",
            sa.Integer(),
            sa.ForeignKey("states.lgd_state_code"),
            nullable=False,
        ),
        sa.Column("discom", sa.String(64)),
        sa.Column("consumer_category", sa.String(128), nullable=False),
        sa.Column("ev_specific", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("energy_paise_per_kwh", sa.Integer(), nullable=False),
        sa.Column("demand_paise_per_kva_month", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fixed_paise_per_month", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duty_bp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tod_bands", postgresql.JSONB()),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("order_number", sa.String(128), nullable=False),
        sa.Column("source_pdf", sa.Text(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_tariff_date_range",
        ),
        sa.CheckConstraint("energy_paise_per_kwh > 0", name="ck_tariff_energy_positive"),
    )
    op.create_index(
        "ix_tariff_lookup",
        "electricity_tariffs",
        ["lgd_state_code", "consumer_category", "effective_from"],
    )

    op.create_table(
        "subsidy_rules",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("lgd_state_code", sa.Integer(), sa.ForeignKey("states.lgd_state_code")),
        sa.Column("scheme", sa.String(128), nullable=False),
        sa.Column("charger_class", sa.String(64), nullable=False, server_default="any"),
        sa.Column("amount_paise", sa.BigInteger()),
        sa.Column("rate_bp", sa.Integer()),
        sa.Column("conditions", sa.Text()),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_subsidy_date_range",
        ),
        sa.CheckConstraint(
            "(amount_paise IS NULL) != (rate_bp IS NULL)",
            name="ck_subsidy_amount_xor_rate",
        ),
    )
    op.create_index(
        "ix_subsidy_lookup",
        "subsidy_rules",
        ["lgd_state_code", "charger_class", "effective_from"],
    )

    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (9, 'PART 3.1 tariffs: electricity_tariffs + subsidy_rules, effective-dated')
        """
    )


def downgrade() -> None:
    op.drop_table("subsidy_rules")
    op.drop_table("electricity_tariffs")
    op.execute("DELETE FROM schema_version WHERE version = 9")
