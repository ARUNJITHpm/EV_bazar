"""The report document's own record - Track B R12.

Every other console panel explains a subsystem. This one explains the
DELIVERABLE: the twelve-section document at ``/report/:id``, what each section
became over R0-R11, and - the half that cannot be written down - how much of
it the payload actually stored can fill.

The prose lives in the frontend, hand-kept like the rest of the console's
prose. What this endpoint adds is the part that would go stale silently:

  · which sections are printing LESS than they know how to, on the newest
    stored report, and what exactly is missing (``domain/report/coverage.py``);
  · whether the rendered PDF has been archived at all, which is rule 9's
    other half and needs a migration applied and a script run before it can
    be true.

Both are read live. A panel that asserted "section 06 shows the cash column"
would be describing the code; this reports the document.

Guarded: mounted on the ``guarded`` router in ``api/internal/__init__.py``.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.report.coverage import SECTION_IDS, coverage
from app.domain.roi.engine import ECONOMICS_VERSION
from app.models.report import Report, ReportPdf

router = APIRouter()


class SectionOut(BaseModel):
    n: int
    id: str
    title: str
    #: Reader-visible blocks this payload cannot fill. Empty is the good case.
    dropped: list[str]


class ArchiveOut(BaseModel):
    """Rule 9's other half, and its two open steps.

    ``table_exists`` is false until migration 0013 is applied; ``archived`` is
    false until ``scripts/archive_report_pdf.py --write`` has run. Both are
    writes to the live database and neither is the code's to take, so the
    panel reports them rather than doing them.
    """

    table_exists: bool
    archived: bool
    renderer_version: str | None = None
    pages: int | None = None
    byte_size: int | None = None
    rendered_at: dt.datetime | None = None


class DocumentOut(BaseModel):
    checked_at: dt.datetime
    #: The report examined - the newest stored one, which is the demo until a
    #: customer report exists. None when nothing has been generated.
    report_id: str | None = None
    demo: bool = False
    generated_at: str | None = None
    economics_version: str | None = None
    #: What the engine would stamp on a payload assembled TODAY. When it is
    #: ahead of the stored one, every gap below is explained by the report
    #: being old rather than by anything being unbuilt - a completely
    #: different piece of news, and the panel must not conflate them.
    engine_economics_version: str = ECONOMICS_VERSION
    model_version: str | None = None
    #: NULL on the row until a render is archived against it - which is the
    #: honest state, and what section 11 prints.
    renderer_version: str | None = None
    site_facts: int = 0
    #: How many of those carry no source yet and print as UNVERIFIED. Since
    #: section 04 was filled out to its promised length this is the number
    #: that means something - "39 checks" alone reads like a finished
    #: section, and 26 of them are named gaps.
    site_facts_unverified: int = 0
    cpo_rows: int = 0
    ledger_rows: int = 0
    sections: list[SectionOut]
    archive: ArchiveOut


def _archive(session: Session, report_id: str | None) -> ArchiveOut:
    """Ask the database, never the migration files.

    ``has_table`` rather than a count, because the interesting state today is
    that the table is not there at all - and a count against a missing
    relation is an error, not an answer.

    Inspected through ``session.connection()`` rather than the engine, so the
    question is asked INSIDE the session's own transaction. Handing the
    inspector the engine takes a second connection and returns it with a
    rollback - which on a shared connection discards whatever the session had
    pending. That is exactly what it did the first time this was written.
    """
    if not inspect(session.connection()).has_table(ReportPdf.__tablename__):
        return ArchiveOut(table_exists=False, archived=False)
    row = session.get(ReportPdf, report_id) if report_id else None
    if row is None:
        return ArchiveOut(table_exists=True, archived=False)
    return ArchiveOut(
        table_exists=True,
        archived=True,
        renderer_version=row.renderer_version,
        pages=row.pages,
        byte_size=row.byte_size,
        rendered_at=row.rendered_at,
    )


@router.get("/document", response_model=DocumentOut)
def document(session: Session = Depends(get_session)) -> DocumentOut:
    """The twelve sections against the newest stored payload."""
    report = session.execute(
        select(Report).order_by(Report.created_at.desc()).limit(1)
    ).scalar_one_or_none()

    if report is None:
        # Nothing stored: every section reports as unfillable rather than as
        # complete. An empty database must not read like a finished document.
        return DocumentOut(
            checked_at=dt.datetime.now(dt.UTC),
            engine_economics_version=ECONOMICS_VERSION,
            sections=[
                SectionOut(n=n, id=sid, title=title, dropped=["no report has been generated yet"])
                for n, sid, title in SECTION_IDS
            ],
            archive=_archive(session, None),
        )

    payload = report.payload
    facts = payload.get("site_facts") or []
    return DocumentOut(
        checked_at=dt.datetime.now(dt.UTC),
        report_id=report.report_id,
        demo=bool(payload.get("demo")),
        generated_at=payload.get("generated_at"),
        economics_version=report.economics_version,
        engine_economics_version=ECONOMICS_VERSION,
        model_version=report.model_version,
        renderer_version=report.renderer_version,
        site_facts=len(facts),
        site_facts_unverified=sum(1 for f in facts if f.get("unverified")),
        cpo_rows=len(payload.get("cpo") or []),
        ledger_rows=len(payload.get("ledger") or []),
        sections=[
            SectionOut(n=s.n, id=s.id, title=s.title, dropped=list(s.dropped))
            for s in coverage(payload)
        ],
        archive=_archive(session, report.report_id),
    )
