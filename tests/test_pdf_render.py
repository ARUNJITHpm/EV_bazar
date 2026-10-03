"""The PDF path - Track B R11.

AGENTS.md rule 9 says the rendered PDF is archived as immutable bytes at
generation time, because a browser render is not reproducible across Chromium
versions. Until R11 there was no renderer at all, so ``renderer_version`` was
the string "dev - unpinned" and the artifact the rule describes did not exist.

What is worth holding here is everything that does NOT need a browser: the
version stamp, the page count read back from the bytes, and the archive's
refusal to overwrite. The render itself is exercised separately against a
running dev server - a unit suite that needs Chromium and a Vite server to
pass is a unit suite that gets skipped.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.report.store import archive_pdf, get_pdf
from app.models import Base
from app.models.report import Report, ReportPdf
from app.pdf.render import _rendered_build_id, _stamp, count_pages, vite_build_id


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[Report.__table__, ReportPdf.__table__])
    with Session(engine) as s:
        yield s


def _report(s: Session, report_id: str, *, demo: bool) -> Report:
    row = Report(
        report_id=report_id,
        site_id=None,
        payload={"report_id": report_id, "demo": demo},
        economics_version="0.5.0",
        model_version="synthetic_v0",
    )
    s.add(row)
    s.flush()
    return row


# ---------------------------------------------------------------------------
# The version stamp
# ---------------------------------------------------------------------------


def test_the_stamp_carries_both_halves_of_a_render() -> None:
    """A Vite hash alone does not survive a Chromium bump and a Chromium
    version alone does not survive a frontend change. Either one on its own
    is decoration, which is what "dev - unpinned" was."""
    stamp = _stamp("CvftFPvT", "140.0.7339.16")
    assert "CvftFPvT" in stamp
    assert "140.0.7339.16" in stamp
    assert len(stamp) <= 64  # the column it is stored in


def test_the_build_id_comes_from_the_manifest_vite_is_already_writing(
    tmp_path: Path,
) -> None:
    vite = tmp_path / ".vite"
    vite.mkdir()
    (vite / "manifest.json").write_text(
        json.dumps({"index.html": {"file": "assets/index-CMCzwgq2.js", "name": "index"}}),
        encoding="utf-8",
    )
    assert vite_build_id(tmp_path) == "CMCzwgq2"


def test_an_unbuilt_tree_says_so_rather_than_inventing_a_hash(tmp_path: Path) -> None:
    """A dev tree that has never been built has no build identity. Reporting
    one would put a stamp on an artifact that nothing can be reproduced from,
    which is worse than admitting the gap."""
    assert vite_build_id(tmp_path) == "unbuilt"
    vite = tmp_path / ".vite"
    vite.mkdir()
    (vite / "manifest.json").write_text("{}", encoding="utf-8")
    assert vite_build_id(tmp_path) == "unbuilt"


def _built(tmp_path: Path, file: str) -> Path:
    vite = tmp_path / ".vite"
    vite.mkdir()
    (vite / "manifest.json").write_text(
        json.dumps({"index.html": {"file": file, "name": "index"}}), encoding="utf-8"
    )
    return tmp_path


class _FakePage:
    """Just enough of a Playwright page to answer the entry-script query."""

    def __init__(self, src: str) -> None:
        self.src = src

    def evaluate(self, _script: str) -> str:
        return self.src


def test_the_stamp_describes_what_rendered_not_what_is_on_disk(tmp_path: Path) -> None:
    """The failure this prevents is silent and permanent.

    ``vite_build_id`` reads the manifest, which is on disk whether or not the
    page came from it - so rendering the DEV server on a tree that happens to
    be built stamped a real content hash onto bytes that build never produced.
    An archive is shown to someone disputing what they received; a stamp that
    can name the wrong build is worse than no stamp at all.
    """
    dist = _built(tmp_path, "assets/index-Cmyt9u8S.js")

    # Served from the build being stamped: the hash is claimable.
    assert _rendered_build_id(_FakePage("/assets/index-Cmyt9u8S.js"), dist) == "Cmyt9u8S"

    # The Vite dev server names the source module, and matches nothing.
    assert _rendered_build_id(_FakePage("/src/main.tsx"), dist) == "unbuilt"

    # A DIFFERENT build from the one on disk: the served bundle is real, but
    # neither identity may be claimed for it.
    assert _rendered_build_id(_FakePage("/assets/index-Zz0011aa.js"), dist) == "unbuilt"

    # No module script at all - a page that never loaded the app.
    assert _rendered_build_id(_FakePage(""), dist) == "unbuilt"


# ---------------------------------------------------------------------------
# Counting pages out of the bytes
# ---------------------------------------------------------------------------


def test_pages_are_counted_from_the_bytes_not_predicted() -> None:
    pdf = b"%PDF-1.4\n/Type /Pages /Count 3\n/Type /Page\n/Type /Page\n/Type /Page\n"
    assert count_pages(pdf) == 3


def test_the_page_tree_node_is_not_counted_as_a_page() -> None:
    """``/Type /Pages`` is the tree, ``/Type /Page`` is a leaf. Off by one on
    every document is the kind of error that looks like a rounding
    disagreement rather than a bug."""
    assert count_pages(b"/Type /Pages") == 0
    assert count_pages(b"/Type /Page") == 1
    assert count_pages(b"/Type/Page /Type/Pages /Type/Page") == 2


# ---------------------------------------------------------------------------
# The archive
# ---------------------------------------------------------------------------


def test_archiving_freezes_the_bytes_and_stamps_the_report(session: Session) -> None:
    _report(session, "CW-1", demo=False)
    row = archive_pdf(
        session,
        "CW-1",
        pdf=b"%PDF-1.4\n/Type /Page\n",
        renderer_version="vite abc · chromium 140",
        pages=1,
    )
    assert row.byte_size == len(row.pdf)
    assert row.pages == 1
    stored = get_pdf(session, "CW-1")
    assert stored is not None
    assert stored.pdf.startswith(b"%PDF")
    # The stamp is duplicated onto the report so "which build rendered this"
    # is a column rather than a join.
    assert session.get(Report, "CW-1").renderer_version == "vite abc · chromium 140"


def test_a_customer_report_is_archived_once_and_never_replaced(session: Session) -> None:
    """Re-rendering on a later Chromium produces different bytes. Letting it
    overwrite would quietly replace the evidence the archive exists to be."""
    _report(session, "CW-2", demo=False)
    archive_pdf(session, "CW-2", pdf=b"%PDF-1.4\n/Type /Page\n", renderer_version="v1", pages=1)
    with pytest.raises(ValueError, match="already archived"):
        archive_pdf(session, "CW-2", pdf=b"%PDF-1.4\n/Type /Page\n", renderer_version="v2", pages=1)


def test_a_demo_may_be_re_rendered_in_place(session: Session) -> None:
    """The same one stated exception `save_report` makes: a demonstration is
    versionless by definition, and refreshing it beats accumulating dead rows."""
    _report(session, "CW-DEMO", demo=True)
    archive_pdf(session, "CW-DEMO", pdf=b"%PDF-1.4\n/Type /Page\n", renderer_version="v1", pages=1)
    archive_pdf(
        session,
        "CW-DEMO",
        pdf=b"%PDF-1.4\n/Type /Page\n/Type /Page\n",
        renderer_version="v2",
        pages=2,
    )
    stored = get_pdf(session, "CW-DEMO")
    assert stored is not None
    assert stored.pages == 2
    assert stored.renderer_version == "v2"


def test_an_empty_render_is_refused(session: Session) -> None:
    """A zero-byte archive is indistinguishable from "never rendered" on the
    read path, and would answer a dispute with nothing at all."""
    _report(session, "CW-3", demo=False)
    with pytest.raises(ValueError, match="empty render"):
        archive_pdf(session, "CW-3", pdf=b"", renderer_version="v1", pages=0)


def test_an_artifact_needs_a_report_to_belong_to(session: Session) -> None:
    with pytest.raises(ValueError, match="no report"):
        archive_pdf(session, "nope", pdf=b"%PDF", renderer_version="v1", pages=1)


def test_nothing_archived_reads_as_nothing_archived(session: Session) -> None:
    _report(session, "CW-4", demo=False)
    assert get_pdf(session, "CW-4") is None
