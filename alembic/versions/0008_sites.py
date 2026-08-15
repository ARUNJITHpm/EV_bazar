"""PART 1.5 - the ``sites`` table.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-12

The output of Part 1 and the input to Parts 2, 3 and 5.

``geom`` is a **generated column**, not one the application writes:
``GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lng, lat), 4326)) STORED``. It
therefore cannot disagree with the ``lat``/``lng`` beside it, which a
separately-written geometry column silently can - and a spatial join against a
stale point returns the wrong neighbourhood rather than an error.

Everything about the geography is nullable on purpose. An address no geocoder
could place is still a lead worth keeping (PLAN 1.6: "log the site anyway"),
and it is the row the manual queue's answer eventually lands in.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("site_id", sa.Uuid(), primary_key=True),
        sa.Column("raw_input", sa.Text(), nullable=False),
        sa.Column("normalised_input", sa.String(512), nullable=False, unique=True),
        sa.Column("lat", sa.Float()),
        sa.Column("lng", sa.Float()),
        sa.Column(
            "geom",
            Geometry("POINT", srid=4326, spatial_index=False),
            sa.Computed("ST_SetSRID(ST_MakePoint(lng, lat), 4326)", persisted=True),
            nullable=True,
        ),
        sa.Column("lgd_state_code", sa.Integer(), sa.ForeignKey("states.lgd_state_code")),
        sa.Column("lgd_district_code", sa.Integer(), sa.ForeignKey("districts.lgd_district_code")),
        sa.Column("pincode", sa.String(6)),
        # NULL until the built-up/town layer from 1.2 is loaded.
        sa.Column("urban_rural", sa.String(8)),
        sa.Column("geocode_source", sa.String(32)),
        sa.Column("geocode_confidence", sa.String(8)),
        sa.Column("district_method", sa.String(16)),
        sa.Column("boundary_ambiguous", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reasons", sa.Text()),
        # NULL until PLAN 1.6 builds data_coverage.
        sa.Column("data_tier", sa.Integer()),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "first_requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_sites_geom", "sites", ["geom"], postgresql_using="gist")
    op.create_index("ix_sites_district", "sites", ["lgd_district_code"])
    op.create_index("ix_sites_tier", "sites", ["data_tier", "lgd_district_code"])

    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (8, 'PART 1.5 sites: resolved site rows, geom generated from lat/lng')
        """
    )


def downgrade() -> None:
    op.drop_index("ix_sites_tier", table_name="sites")
    op.drop_index("ix_sites_district", table_name="sites")
    op.drop_index("ix_sites_geom", table_name="sites")
    op.drop_table("sites")
    op.execute("DELETE FROM schema_version WHERE version = 8")
