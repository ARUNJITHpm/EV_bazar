"""Owner submissions point at the charging-network tables.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-30

Additive. ``station_id`` / ``connector_ids`` reference ``stations`` and
``connectors`` (0015), so a submission names real connectors instead of
positions in a JSON list that shifts when the list does. The two legacy columns
stay, now nullable, because ``owner_submissions`` is append-only in the database
(0014's rules): rows already written cannot be rewritten, and must keep meaning
what they meant. A check requires one complete pair.

Downgrade is only possible while no new-style submission exists - restoring NOT
NULL on the legacy columns would fail on them, which is the safe outcome.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "owner_submissions",
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id")),
    )
    op.add_column("owner_submissions", sa.Column("connector_ids", JSONB(none_as_null=True)))
    op.alter_column("owner_submissions", "competitor_station_id", nullable=True)
    op.alter_column("owner_submissions", "connector_indices", nullable=True)
    op.create_check_constraint(
        "ck_owner_station_ref",
        "owner_submissions",
        "(station_id IS NOT NULL AND connector_ids IS NOT NULL) "
        "OR (competitor_station_id IS NOT NULL AND connector_indices IS NOT NULL)",
    )
    op.create_index("ix_owner_submissions_network_station", "owner_submissions", ["station_id"])
    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (16, 'Owner submissions reference stations/connectors (station_id, connector_ids)')
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM schema_version WHERE version = 16")
    op.drop_index("ix_owner_submissions_network_station", table_name="owner_submissions")
    op.drop_constraint("ck_owner_station_ref", "owner_submissions", type_="check")
    op.alter_column("owner_submissions", "connector_indices", nullable=False)
    op.alter_column("owner_submissions", "competitor_station_id", nullable=False)
    op.drop_column("owner_submissions", "connector_ids")
    op.drop_column("owner_submissions", "station_id")
