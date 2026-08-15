"""PART 4.1 - VAHAN EV registrations per district.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-15

A time series of EV counts per district, split by vehicle class and fuel, read
from the VAHAN dashboard. Tall (one row per district/snapshot/period/fuel/class)
and append-only across snapshots - never overwritten, because PLAN 4.1 wants the
growth rate, which only exists once there is more than one reading.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vahan_ev_registrations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("lgd_district_code", sa.Integer(), sa.ForeignKey("districts.lgd_district_code")),
        sa.Column("lgd_state_code", sa.Integer(), sa.ForeignKey("states.lgd_state_code")),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("fuel_category", sa.String(24), nullable=False),
        sa.Column("vehicle_class", sa.String(16), nullable=False),
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
            "lgd_district_code",
            "snapshot_date",
            "period",
            "fuel_category",
            "vehicle_class",
            name="uq_vahan_slice",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index("ix_vahan_district", "vahan_ev_registrations", ["lgd_district_code"])
    op.create_index(
        "ix_vahan_state_period", "vahan_ev_registrations", ["lgd_state_code", "period"]
    )

    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (11, 'PART 4.1 vahan_ev_registrations: EV counts per district, time series')
        """
    )


def downgrade() -> None:
    op.drop_table("vahan_ev_registrations")
    op.execute("DELETE FROM schema_version WHERE version = 11")
