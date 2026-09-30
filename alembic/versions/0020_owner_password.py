"""Owner accounts get a password.

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-30

Owners sign up and log in with a mobile number and a password (a one-time-code
method comes later). The column is nullable only so the migration is additive;
an account with no hash cannot log in.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("owner_accounts", sa.Column("password_hash", sa.String(200)))
    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (20, 'Owner accounts: password_hash (mobile number + password sign-in)')
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM schema_version WHERE version = 20")
    op.drop_column("owner_accounts", "password_hash")
