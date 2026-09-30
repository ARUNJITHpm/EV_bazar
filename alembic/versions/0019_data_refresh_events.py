"""Durable scheduler outcomes and zipped scraper artifacts.

Revision ID: 0019
Revises: 0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_refresh_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job", sa.String(32), nullable=False),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column(
            "observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("archive", sa.LargeBinary()),
    )
    op.create_index("ix_refresh_period", "data_refresh_events", ["job", "period", "observed_at"])
    for action in ("update", "delete"):
        op.execute(
            f"CREATE RULE data_refresh_events_no_{action} AS ON {action.upper()} "
            "TO data_refresh_events DO INSTEAD NOTHING"
        )
    op.execute(
        "INSERT INTO schema_version (version, note) VALUES "
        "(19, 'Durable weekly inventory and server VAHAN refresh outcomes')"
    )


def downgrade() -> None:
    op.drop_table("data_refresh_events")
    op.execute("DELETE FROM schema_version WHERE version = 19")
