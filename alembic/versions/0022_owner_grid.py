"""Optional private owner grid revisions; erasure plan PART14_OWNER_PRIVACY.md.

Revision ID: 0022_owner_grid
Revises: 0020 (0021 is reserved for an unpublished analytics draft)
"""

import sqlalchemy as sa

from alembic import op

revision = "0022_owner_grid"
down_revision = "0020"
branch_labels = None
depends_on = None


def _base():
    return [
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("owner_stations.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.create_table(
        "owner_grid_consents",
        *_base(),
        sa.Column("consent_private", sa.Boolean(), nullable=False),
        sa.Column("ownership_review_ref", sa.String(512), nullable=False),
        sa.Column("purpose_version", sa.String(32), nullable=False),
        sa.CheckConstraint("consent_private", name="ck_owner_grid_consent"),
    )
    op.create_table(
        "owner_grid_revisions",
        *_base(),
        sa.Column("supersedes_id", sa.Integer(), sa.ForeignKey("owner_grid_revisions.id")),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("sanctioned_load_kva", sa.Float()),
        sa.Column("connected_load_kw", sa.Float()),
        sa.Column("transformer_ownership", sa.String(16), nullable=False),
        sa.Column("transformer_rating_kva", sa.Float()),
        sa.CheckConstraint(
            "sanctioned_load_kva >= 0 AND sanctioned_load_kva <= 1000000", name="ck_grid_sanctioned"
        ),
        sa.CheckConstraint(
            "connected_load_kw >= 0 AND connected_load_kw <= 1000000", name="ck_grid_connected"
        ),
        sa.CheckConstraint(
            "transformer_rating_kva > 0 AND transformer_rating_kva <= 1000000",
            name="ck_grid_rating",
        ),
        sa.CheckConstraint(
            "transformer_ownership IN ('own','shared','unknown')", name="ck_grid_ownership"
        ),
    )
    op.create_table(
        "owner_outage_revisions",
        *_base(),
        sa.Column("supersedes_id", sa.Integer(), sa.ForeignKey("owner_outage_revisions.id")),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("approximate_hours", sa.Float()),
        sa.CheckConstraint(
            "approximate_hours >= 0 AND approximate_hours <= 744", name="ck_outage_hours"
        ),
    )
    op.execute("""CREATE FUNCTION owner_grid_reject_update() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          RAISE EXCEPTION 'Owner grid records are append-only; insert a revision';
        END $$""")
    for table in ("owner_grid_consents", "owner_grid_revisions", "owner_outage_revisions"):
        op.create_index(f"ix_{table}_station_id", table, ["station_id"])
        op.execute(
            f"CREATE TRIGGER {table}_no_update BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION owner_grid_reject_update()"
        )
    op.execute(
        "INSERT INTO schema_version(version,note) VALUES (22,'Private owner grid revisions with verified erasure')"
    )


def downgrade():
    for table in ("owner_outage_revisions", "owner_grid_revisions", "owner_grid_consents"):
        op.drop_table(table)
    op.execute("DROP FUNCTION owner_grid_reject_update()")
    op.execute("DELETE FROM schema_version WHERE version=22")
