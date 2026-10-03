"""The document console panel - Track B R12.

The panel's prose is hand-kept and can be wrong the way any prose can. This
endpoint is the half that cannot: it reports what the STORED payload can fill
and whether the render has actually been archived, so the console describes
the document rather than the code that would produce one.

Two things are worth pinning, and both are about honest absence:

1. **A missing ``report_pdfs`` is an answer, not an error.** Migration 0013
   has not been applied to the live database, deliberately - it is a write
   that is the owner's to take. The panel has to say so and keep working; a
   count against a missing relation would take the whole page down instead.
2. **An empty database never reads like a finished document.** With nothing
   stored, every section reports as unfillable, because "no gaps" and "no
   data" must not look the same on a page whose job is to show gaps.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.internal.document import document
from app.domain.report.store import archive_pdf
from app.models import Base
from app.models.report import Report, ReportPdf

PAYLOAD = {
    "report_id": "KL-TVM-DEMO-001",
    "demo": True,
    "generated_at": "2026-09-08",
    "site_facts": [{"label": "Road class", "group": "Access", "direction": "favours"}],
    "cpo": [{"operator": "chargeMOD"}],
    "ledger": [{"item": "Selling price"}],
    "breakeven": {"utilisation": 0.19},
    "financials": {"scenarios": []},
    "competitors": {"within_3km": 8},
}


def _report(session: Session, **overrides: object) -> Report:
    row = Report(
        report_id=str(overrides.get("report_id", PAYLOAD["report_id"])),
        payload={**PAYLOAD, **overrides},
        economics_version="0.5.0",
        model_version="synthetic_v0",
        created_at=dt.datetime.now(dt.UTC),
    )
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def unmigrated() -> Iterator[Session]:
    """Today's live database: `reports` exists, `report_pdfs` does not."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[Report.__table__])
    with Session(engine) as s:
        yield s


@pytest.fixture
def migrated() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[Report.__table__, ReportPdf.__table__])
    with Session(engine) as s:
        yield s


def test_a_missing_archive_table_is_reported_not_raised(unmigrated: Session) -> None:
    _report(unmigrated)
    out = document(unmigrated)
    assert out.archive.table_exists is False
    assert out.archive.archived is False
    assert out.archive.pages is None


def test_an_empty_database_reports_every_section_as_unfillable(unmigrated: Session) -> None:
    out = document(unmigrated)
    assert out.report_id is None
    assert len(out.sections) == 12
    assert all(s.dropped for s in out.sections), "nothing stored must not read as nothing missing"


def test_it_reads_the_newest_report_and_names_it(unmigrated: Session) -> None:
    """Which report the panel is describing has to be on the page. The demo
    is the newest row today; a customer report generated tomorrow becomes the
    one the coverage lines are measured against, and the reader must be able
    to tell which."""
    _report(unmigrated, report_id="OLD-1")
    unmigrated.flush()
    _report(unmigrated, report_id="NEW-1")
    out = document(unmigrated)
    assert out.report_id == "NEW-1"
    assert out.economics_version == "0.5.0"
    assert out.site_facts == 1


def test_an_archived_render_is_reported_from_the_bytes(migrated: Session) -> None:
    """The page count comes back from the archive rather than from a claim
    about it - the same discipline the renderer uses when it counts pages out
    of the PDF it just produced."""
    report = _report(migrated)
    archive_pdf(
        migrated,
        report.report_id,
        pdf=b"%PDF-1.4 fake",
        renderer_version="vite C4Us6zq1 - chromium 151.0.7922.34",
        pages=23,
    )
    out = document(migrated)
    assert out.archive.table_exists is True
    assert out.archive.archived is True
    assert out.archive.pages == 23
    assert out.archive.byte_size == len(b"%PDF-1.4 fake")
    assert out.archive.renderer_version is not None
    # archive_pdf stamps the report row too, so "which build rendered this" is
    # a column and not a join. The panel reads it from there.
    assert out.renderer_version == out.archive.renderer_version


def test_the_migration_applied_but_nothing_archived_is_its_own_state(migrated: Session) -> None:
    _report(migrated)
    out = document(migrated)
    assert out.archive.table_exists is True
    assert out.archive.archived is False
    assert out.renderer_version is None
