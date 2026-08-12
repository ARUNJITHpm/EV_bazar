"""PART 1.2 - reference geography: states, districts, PINs, crosswalk.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-12

Plain tables, not partitioned and not append-only: this is reference data that
is replaced wholesale when a new vintage is published, and every replacement
is recorded in ``reference_layers`` with its checksum. That record is what
makes an old report explicable - "which district boundaries produced this" has
an answer.

``spatial_index=False`` on every geometry column is deliberate: GeoAlchemy2
would otherwise emit its own index automatically, and the ones created
explicitly below are the ones the point-in-polygon query in PLAN 1.4 needs.
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SRID = 4326


def _geom() -> geoalchemy2.Geometry:
    return geoalchemy2.Geometry("MULTIPOLYGON", srid=SRID, spatial_index=False)


def upgrade() -> None:
    op.create_table(
        "reference_layers",
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("licence", sa.String(128), nullable=False),
        sa.Column("feature_count", sa.Integer(), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "loaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("note", sa.Text()),
    )

    op.create_table(
        "states",
        sa.Column("lgd_state_code", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("census_2011_code", sa.String(8)),
        sa.Column("geom", _geom(), nullable=False),
    )
    op.execute("CREATE INDEX ix_states_geom ON states USING GIST (geom)")

    op.create_table(
        "districts",
        sa.Column("lgd_district_code", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column(
            "lgd_state_code",
            sa.Integer(),
            sa.ForeignKey("states.lgd_state_code"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("state_name", sa.String(128), nullable=False),
        sa.Column("census_2011_code", sa.String(8)),
        sa.Column("boundary_vintage", sa.String(16)),
        sa.Column("geom", _geom(), nullable=False),
    )
    op.execute("CREATE INDEX ix_districts_geom ON districts USING GIST (geom)")
    op.create_index("ix_districts_state", "districts", ["lgd_state_code"])

    op.create_table(
        "pincodes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("pincode", sa.String(6), nullable=False),
        sa.Column("office_name", sa.String(255)),
        sa.Column("postal_circle", sa.String(128)),
        sa.Column("postal_region", sa.String(128)),
        sa.Column("postal_division", sa.String(128)),
        sa.Column("geom", _geom(), nullable=False),
    )
    op.execute("CREATE INDEX ix_pincodes_geom ON pincodes USING GIST (geom)")
    op.create_index("ix_pincodes_pincode", "pincodes", ["pincode"])

    op.create_table(
        "district_name_crosswalk",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("source_name", sa.String(128), nullable=False),
        sa.Column("source_state", sa.String(128), nullable=False),
        sa.Column("source_dataset", sa.String(64), nullable=False),
        sa.Column(
            "lgd_district_code",
            sa.Integer(),
            sa.ForeignKey("districts.lgd_district_code"),
        ),
        sa.Column("match_method", sa.String(16), nullable=False),
        sa.Column("match_score", sa.Integer()),
        # NULL until a human checks the row. Nothing in the codebase may write
        # this column - that is the entire point of it (PLAN 1.2).
        sa.Column("verified_by", sa.String(64)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("note", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "source_dataset", "source_state", "source_name", name="uq_crosswalk_source"
        ),
    )
    op.create_index(
        "ix_crosswalk_unverified", "district_name_crosswalk", ["match_method", "verified_by"]
    )

    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (5, 'PART 1.2 reference geography: states, districts, pincodes, '
                   'district_name_crosswalk, reference_layers')
        """
    )


def downgrade() -> None:
    op.drop_table("district_name_crosswalk")
    op.drop_table("pincodes")
    op.drop_table("districts")
    op.drop_table("states")
    op.drop_table("reference_layers")
    op.execute("DELETE FROM schema_version WHERE version = 5")
