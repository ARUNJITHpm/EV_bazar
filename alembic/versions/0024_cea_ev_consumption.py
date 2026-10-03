"""CEA monthly EV charging electricity consumption, per state and DISCOM.

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-03

Append-only rows keyed on the source PDF's sha256; kWh as integers, NULL where
a DISCOM did not report. Additive only.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cea_ev_consumption",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("report_month", sa.Date(), nullable=False),
        sa.Column("span", sa.String(12), nullable=False),
        sa.Column("span_start", sa.Date(), nullable=False),
        sa.Column("geography", sa.String(8), nullable=False),
        sa.Column("state_name", sa.String(128), nullable=False),
        sa.Column("lgd_state_code", sa.Integer(), sa.ForeignKey("states.lgd_state_code")),
        sa.Column("discom", sa.String(128)),
        sa.Column("pcs_kwh", sa.BigInteger()),
        sa.Column("heavy_duty_pcs_kwh", sa.BigInteger()),
        sa.Column("other_kwh", sa.BigInteger()),
        sa.Column("total_kwh", sa.BigInteger()),
        sa.Column("source_url", sa.String(512), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "source_sha256",
            "span",
            "geography",
            "state_name",
            "discom",
            name="uq_cea_ev_row",
            postgresql_nulls_not_distinct=True,
        ),
        sa.CheckConstraint("span IN ('month', 'fy_to_date')", name="ck_cea_ev_span"),
        sa.CheckConstraint("geography IN ('state', 'discom', 'india')", name="ck_cea_ev_geography"),
    )
    op.create_index(
        "ix_cea_ev_month_state", "cea_ev_consumption", ["report_month", "lgd_state_code"]
    )
    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (24, 'CEA monthly EV charging electricity consumption by state and DISCOM')
        """
    )


def downgrade() -> None:
    op.drop_table("cea_ev_consumption")
    op.execute("DELETE FROM schema_version WHERE version = 24")
