"""Track B R11 - the archived PDF artifact behind AGENTS.md rule 9.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-08

The stored payload answers "what did you tell me". It cannot answer "this is
not what my report LOOKED like", because a browser render is not reproducible
across Chromium versions - so the rendered bytes are frozen at generation
time and never re-derived.

WHY A SECOND TABLE RATHER THAN COLUMNS ON ``reports``. Two reasons, and both
are about not weakening something that already works.

1. ``reports`` is immutable by database rule (migration 0012): a non-demo row
   refuses UPDATE outright. The PDF is rendered AFTER the payload is stored -
   the renderer has to load the report's own URL - so attaching it to the
   same row would mean relaxing that rule, and a rule with an exception in it
   is a rule that has to be re-read every time it matters.
2. A PDF is hundreds of kilobytes and the payload is read on every request.
   ``SELECT payload`` should not drag the artifact across the wire.

Insert-only, on the same terms: a demo may be re-rendered in place, a
customer report never. Re-rendering a customer report would produce different
bytes on a different Chromium and quietly replace the evidence.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_pdfs",
        sa.Column(
            "report_id",
            sa.String(64),
            sa.ForeignKey("reports.report_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("pdf", sa.LargeBinary(), nullable=False),
        # Rule 4's stamp, and the only one that is a property of the RENDER
        # rather than of the data: the Vite build hash plus the Chromium
        # build. Either half alone survives the wrong kind of change.
        sa.Column("renderer_version", sa.String(64), nullable=False),
        # Read back from the bytes at archive time, not predicted. A page
        # count that was measured is one the archive cannot be wrong about.
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column(
            "rendered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Same line as `reports`: a demo artifact may be replaced, a customer's
    # never. Written as rules rather than as application discipline, because
    # discipline is not enforceable at 3 a.m. six months from now.
    op.execute(
        """
        CREATE RULE report_pdfs_no_update AS
            ON UPDATE TO report_pdfs DO INSTEAD NOTHING;
        CREATE RULE report_pdfs_no_delete AS
            ON DELETE TO report_pdfs
            WHERE NOT EXISTS (
                SELECT 1 FROM reports r
                WHERE r.report_id = OLD.report_id
                  AND (r.payload ->> 'demo') = 'true'
            )
            DO INSTEAD NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (13, 'Track B R11 - archived report PDFs, insert-only (rule 9)')
        """
    )


def downgrade() -> None:
    op.drop_table("report_pdfs")
    op.execute("DELETE FROM schema_version WHERE version = 13")
