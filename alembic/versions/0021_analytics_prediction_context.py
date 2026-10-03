"""Private analytics provenance on the existing append-only prediction ledger.

Revision ID: 0021
Revises: 0022_owner_grid
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0021"
down_revision = "0022_owner_grid"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("predictions", sa.Column("analytics_context", postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column("predictions", "analytics_context")
