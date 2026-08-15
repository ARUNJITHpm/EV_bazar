"""PART 2.3 - the competitor inventory.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-15

A cache of known charging stations (existence + specs), upserted by
(source, source_id). NOT the poller's append-only occupancy archive - this is
who/where/how-powerful; the poller supplies free/busy over time and attaches
to these rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "competitor_stations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("name", sa.Text()),
        sa.Column("operator", sa.String(128)),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column(
            "geom",
            Geometry("POINT", srid=4326, spatial_index=False),
            sa.Computed("ST_SetSRID(ST_MakePoint(lng, lat), 4326)", persisted=True),
            nullable=True,
        ),
        sa.Column("lgd_district_code", sa.Integer(), sa.ForeignKey("districts.lgd_district_code")),
        sa.Column("lgd_state_code", sa.Integer(), sa.ForeignKey("states.lgd_state_code")),
        sa.Column("town", sa.String(128)),
        sa.Column("postcode", sa.String(12)),
        sa.Column("access", sa.String(16)),
        sa.Column("is_operational", sa.Boolean()),
        sa.Column("number_of_points", sa.Integer()),
        sa.Column("max_power_kw", sa.Float()),
        sa.Column("connectors", postgresql.JSONB()),
        sa.Column("data_provider", sa.String(128)),
        sa.Column("source_last_status_update", sa.DateTime(timezone=True)),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("source", "source_id", name="uq_competitor_source"),
    )
    op.create_index("ix_competitor_geom", "competitor_stations", ["geom"], postgresql_using="gist")
    op.create_index("ix_competitor_district", "competitor_stations", ["lgd_district_code"])

    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (10, 'PART 2.3 competitor_stations: charging inventory, upsert by source')
        """
    )


def downgrade() -> None:
    op.drop_table("competitor_stations")
    op.execute("DELETE FROM schema_version WHERE version = 10")
