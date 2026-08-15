"""PART 1.3 - the manual queue (L6) and the provider place handle.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-12

Two changes, both arriving with the paid levels of the cascade:

``geocode_cache.provider_place_id``
    Mappls eLoc / Google place_id / Ola place_id / Nominatim osm_id. PLAN 1.3
    L4 asks for the eLoc by name; a generic column serves all four rather than
    one vendor.

``geocode_manual_queue``
    L6. An ordinary mutable work queue - a row is meant to change state, which
    is why it carries no append-only RULE unlike the event tables. The history
    that matters (what the cascade decided, and what it cost) is already
    immutable in ``api_usage_events``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("geocode_cache", sa.Column("provider_place_id", sa.String(128)))

    op.create_table(
        "geocode_manual_queue",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("normalised_input", sa.String(512), nullable=False, unique=True),
        sa.Column("raw_input", sa.Text(), nullable=False),
        sa.Column("pincode", sa.String(6)),
        sa.Column("reason", sa.Text()),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("lat", sa.Float()),
        sa.Column("lng", sa.Float()),
        sa.Column("note", sa.Text()),
        sa.Column("resolved_by", sa.String(64)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # A resolved row with no coordinates cannot be written back to the
        # cache, so it must not be possible to create one.
        sa.CheckConstraint(
            "status <> 'resolved' OR (lat IS NOT NULL AND lng IS NOT NULL)",
            name="ck_manual_queue_resolved_has_point",
        ),
    )
    op.create_index("ix_manual_queue_status", "geocode_manual_queue", ["status", "hits"])

    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (7, 'PART 1.3 paid levels: manual queue (L6) + geocode_cache.provider_place_id')
        """
    )


def downgrade() -> None:
    op.drop_index("ix_manual_queue_status", table_name="geocode_manual_queue")
    op.drop_table("geocode_manual_queue")
    op.drop_column("geocode_cache", "provider_place_id")
    op.execute("DELETE FROM schema_version WHERE version = 7")
