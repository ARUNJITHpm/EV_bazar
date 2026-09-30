"""Let owner data be erased: drop the insert-only rules on the owner tables.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-30

0017 made the owner tables insert-only. That was the wrong shape for personal
data: India's DPDP Act gives an owner the right to have their data erased, and
requires it not be kept longer than its purpose needs. So the DELETE rules go,
and ``owner_bills`` also loses its UPDATE rule, because purging an expired bill
image detaches it (``image_id`` -> NULL) before the image row is deleted.

Erasure is done only by ``app.domain.owner.erasure`` (an owner's own request, or
the retention purge) - never as a side effect elsewhere. Stations, connectors,
images and forecasts keep their UPDATE rule: nothing edits them in place.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "owner_stations",
    "owner_connectors",
    "owner_bill_images",
    "owner_bills",
    "owner_forecasts",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP RULE IF EXISTS {table}_no_delete ON {table}")
    op.execute("DROP RULE IF EXISTS owner_bills_no_update ON owner_bills")
    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (18, 'Owner data erasable: DELETE allowed on owner tables (DPDP)')
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM schema_version WHERE version = 18")
    op.execute("CREATE RULE owner_bills_no_update AS ON UPDATE TO owner_bills DO INSTEAD NOTHING")
    for table in _TABLES:
        op.execute(f"CREATE RULE {table}_no_delete AS ON DELETE TO {table} DO INSTEAD NOTHING")
