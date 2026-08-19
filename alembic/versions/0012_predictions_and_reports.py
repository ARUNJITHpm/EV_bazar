"""PLAN 4.3 + PLAN 5 - the prediction log and the report data-of-record.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-19

Two tables that exist for the long game:

* ``predictions`` - Rule 2: every demand prediction, written with a NULL
  ``actual_kwh`` from the very first (synthetic) one. Demo runs flagged, not
  skipped (AGENTS.md rule 5). Append-only by database rule, like the poller's
  event tables.
* ``reports`` - AGENTS.md rule 9: the 7-section payload as stored JSONB, the
  thing ``GET /api/internal/reports/{id}`` serves verbatim forever.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("site_id", sa.Uuid(), sa.ForeignKey("sites.site_id"), nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("economics_version", sa.String(16), nullable=False),
        sa.Column("predicted_p10", sa.Float(), nullable=False),
        sa.Column("predicted_p50", sa.Float(), nullable=False),
        sa.Column("predicted_p90", sa.Float(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "predicted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("actual_kwh", sa.Float()),
        sa.Column("actual_observed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_predictions_site", "predictions", ["site_id"])

    # Append-only in the database, not by convention (AGENTS.md rule 3).
    # Backfilling an actual later means a superseding row, same as tariffs.
    op.execute(
        """
        CREATE RULE predictions_no_update AS
            ON UPDATE TO predictions DO INSTEAD NOTHING;
        CREATE RULE predictions_no_delete AS
            ON DELETE TO predictions DO INSTEAD NOTHING;
        """
    )

    op.create_table(
        "reports",
        sa.Column("report_id", sa.String(64), primary_key=True),
        sa.Column("site_id", sa.Uuid(), sa.ForeignKey("sites.site_id")),
        sa.Column("payload", JSONB(none_as_null=True), nullable=False),
        sa.Column("economics_version", sa.String(16), nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("renderer_version", sa.String(64)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_reports_site", "reports", ["site_id"])

    # Immutable, with the one stated exception: a row whose payload says
    # demo:true may be refreshed in place by the demo generator. Customer
    # reports never update - a correction is a NEW report id.
    op.execute(
        """
        CREATE RULE reports_no_update AS
            ON UPDATE TO reports
            WHERE (OLD.payload ->> 'demo') IS DISTINCT FROM 'true'
            DO INSTEAD NOTHING;
        CREATE RULE reports_no_delete AS
            ON DELETE TO reports
            WHERE (OLD.payload ->> 'demo') IS DISTINCT FROM 'true'
            DO INSTEAD NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (12, 'PLAN 4.3 predictions (append-only) + PLAN 5 reports (stored JSONB payload)')
        """
    )


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("predictions")
    op.execute("DELETE FROM schema_version WHERE version = 12")
