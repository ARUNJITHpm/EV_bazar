"""VAHAN month-wise EV registrations, by vehicle category and by maker.

Revision ID: 0023
Revises: 0021
Create Date: 2026-10-03

A new table rather than new periods in ``vahan_ev_registrations``: that table's
readers sum yearly periods, and monthly rows beside them would double-count.
Additive only.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vahan_monthly_registrations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("geography", sa.String(8), nullable=False),
        sa.Column("lgd_district_code", sa.Integer(), sa.ForeignKey("districts.lgd_district_code")),
        sa.Column("lgd_state_code", sa.Integer(), sa.ForeignKey("states.lgd_state_code")),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("breakdown", sa.String(24), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("fuel_scope", sa.String(64), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("rto_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "geography",
            "lgd_district_code",
            "lgd_state_code",
            "snapshot_date",
            "month",
            "breakdown",
            "label",
            "fuel_scope",
            name="uq_vahan_monthly_slice",
            postgresql_nulls_not_distinct=True,
        ),
        sa.CheckConstraint("geography IN ('district', 'state')", name="ck_vahan_monthly_geography"),
        sa.CheckConstraint(
            "breakdown IN ('vehicle_category', 'maker')", name="ck_vahan_monthly_breakdown"
        ),
        sa.CheckConstraint("EXTRACT(DAY FROM month) = 1", name="ck_vahan_monthly_first_day"),
    )
    op.create_index(
        "ix_vahan_monthly_state_month", "vahan_monthly_registrations", ["lgd_state_code", "month"]
    )
    op.create_index(
        "ix_vahan_monthly_district", "vahan_monthly_registrations", ["lgd_district_code"]
    )
    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (23, 'VAHAN month-wise EV registrations by vehicle category and maker')
        """
    )


def downgrade() -> None:
    op.drop_table("vahan_monthly_registrations")
    op.execute("DELETE FROM schema_version WHERE version = 23")
