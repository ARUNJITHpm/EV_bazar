"""Station-owner upload: submissions and monthly readings.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-29

Insert-only in the database, not by convention (AGENTS.md rule 3): a
correction is a new submission. ``forecast`` is stored as shown to the owner,
with its ``model_version`` inside and beside it (rule 4).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "owner_submissions",
        sa.Column("submission_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "competitor_station_id",
            sa.Integer(),
            sa.ForeignKey("competitor_stations.id"),
            nullable=False,
        ),
        sa.Column("connector_indices", JSONB(none_as_null=True), nullable=False),
        sa.Column("install_month", sa.Date(), nullable=False),
        sa.Column("meter_type", sa.String(16), nullable=False),
        sa.Column("consent_aggregate", sa.Boolean(), nullable=False),
        sa.Column("consent_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("forecast", JSONB(none_as_null=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "meter_type IN ('separate','shared','unsure')", name="ck_owner_meter_type"
        ),
        sa.CheckConstraint("consent_aggregate", name="ck_owner_consent_required"),
    )
    op.create_index("ix_owner_submissions_station", "owner_submissions", ["competitor_station_id"])

    op.create_table(
        "owner_readings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "submission_id",
            sa.Uuid(),
            sa.ForeignKey("owner_submissions.submission_id"),
            nullable=False,
        ),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("kwh", sa.Float(), nullable=False),
        sa.CheckConstraint("kwh > 0", name="ck_owner_reading_positive"),
    )
    op.create_index("ix_owner_readings_submission", "owner_readings", ["submission_id"])

    op.execute(
        """
        CREATE RULE owner_submissions_no_update AS
            ON UPDATE TO owner_submissions DO INSTEAD NOTHING;
        CREATE RULE owner_submissions_no_delete AS
            ON DELETE TO owner_submissions DO INSTEAD NOTHING;
        CREATE RULE owner_readings_no_update AS
            ON UPDATE TO owner_readings DO INSTEAD NOTHING;
        CREATE RULE owner_readings_no_delete AS
            ON DELETE TO owner_readings DO INSTEAD NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (14, 'Station-owner upload: owner_submissions + owner_readings (append-only)')
        """
    )


def downgrade() -> None:
    op.drop_table("owner_readings")
    op.drop_table("owner_submissions")
    op.execute("DELETE FROM schema_version WHERE version = 14")
