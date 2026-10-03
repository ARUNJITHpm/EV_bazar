"""HTML to PDF, and the version stamp that makes the result defensible.

This is the artifact behind AGENTS.md rule 9. The stored JSONB payload is the
data of record and answers "what did you tell me"; the archived PDF answers
"this is not what my report LOOKED like", which a payload cannot, because a
browser render is not reproducible across Chromium versions. So the bytes are
frozen at generation time and never re-derived.

WHAT THIS MODULE KNOWS THAT IS EASY TO GET WRONG

* ``page.pdf()`` already renders in PRINT media. Calling
  ``emulate_media(media="screen")`` anywhere before it silently produces a
  screen-media PDF that looks plausible and honours none of ``print.css`` -
  which is exactly how a print check passes while the print styles are dead.
  Nothing here emulates media, and nothing added here should.
* **Fonts must be ready before the render, and `networkidle` is not enough.**
  Measured: with the page loaded, `[data-report-ready]` present and the
  network quiet, ``document.fonts.status`` is still ``loading``, and printing
  then lays the document out in FALLBACK METRICS - narrower text, fewer
  wraps, and one page fewer than the truth. The whole rebuild's print
  measurements were taken that way and were one page optimistic until R11
  caught it. ``document.fonts.ready`` is awaited here; anything that renders
  this document without awaiting it is measuring a different document.
* **The running head and foot are NOT Chromium's.** They repeat from a real
  ``<thead>``/``<tfoot>`` inside the document, because Chromium implements
  neither ``@page`` margin boxes nor repeating ``position: fixed`` (print.css
  carries the measurements). Chromium's own footer is used for ONE thing the
  document cannot know: the page number. Its templates get no page CSS, so
  the style is inline. Enabling it costs nothing - also measured: the content
  box stays 1017px and the page count is identical with the header/footer on
  or off, because Chromium draws the templates in a page-anchored box rather
  than taking the space out of the flow.
* ``sync_playwright`` cannot run inside a live asyncio loop. Rendering is a
  generation-time job, not a request-time one; call it from a script, a
  worker, or a thread, never straight from an async route handler.
* **The build stamp is taken from the PAGE, not from the disk.** Reading
  ``dist/.vite/manifest.json`` alone says what was last built, which is not
  the same question as what just rendered: point the renderer at the Vite dev
  server on a tree that happens to be built, and a real content hash gets
  stamped onto bytes that build never produced. So the entry script is read
  off the loaded document and matched against the manifest; a dev page
  requests ``/src/main.tsx``, matches nothing, and stamps ``unbuilt`` - which
  is the honest answer and needs nobody to remember which server they aimed
  at.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright

#: A4 less the same margins print.css sets, so the PDF and every width
#: measurement in the rebuild agree on what "the printable width" means.
#: Uniform on all four sides: the page number needs no extra room, because
#: Chromium draws it in a page-anchored box outside the flow, and 14mm
#: through 18mm were measured to produce byte-for-byte the same pagination.
MARGIN_MM = 14

#: Chromium substitutes the text of these classes; everything else in a
#: header/footer template is drawn as given. No stylesheet reaches here, so
#: every declaration is inline, and the size is in pt because the template is
#: scaled with the page rather than with the viewport.
_FOOTER = """
<div style="width:100%;padding:0 14mm;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
            font-size:7pt;color:#6b7280;display:flex;justify-content:flex-end;">
  <span>page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
</div>
"""
#: Empty, but present: with `display_header_footer` on, Chromium reserves the
#: top margin box whether or not anything is drawn in it. Passing nothing
#: makes it draw its own default title-and-date header instead.
_HEADER = "<span></span>"


@dataclass(frozen=True)
class RenderedPdf:
    """Immutable bytes, and what produced them."""

    pdf: bytes
    renderer_version: str
    #: Pages, read back from the bytes rather than predicted. A page count
    #: that has to be measured is a page count that cannot be wrong in the
    #: archive.
    pages: int


def vite_build_id(dist: Path) -> str:
    """The frontend build identity, from Vite's manifest.

    `vite.config.ts` sets `manifest: true` for this and no other reason. The
    entry chunk's filename carries the content hash of the whole build, so
    two reports with the same hash were rendered by the same bytes of
    JavaScript and CSS. Absent in a dev tree that has never been built, which
    is honestly reported rather than papered over.

    This is what was BUILT. Whether it is also what RENDERED is a different
    question, and ``_rendered_build_id`` is the one that answers it.
    """
    path = dist / ".vite" / "manifest.json"
    if not path.exists():
        return "unbuilt"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entry = manifest.get("index.html")
    if not isinstance(entry, dict):
        return "unbuilt"
    file = str(entry.get("file", ""))
    return entry_hash(file)


def entry_hash(file: str) -> str:
    """The content hash out of a Vite entry filename, or ``unbuilt``."""
    match = re.search(r"-([A-Za-z0-9_-]{8,})\.js(?:\?.*)?$", file)
    return match.group(1) if match else "unbuilt"


#: The entry script the loaded document actually asked for. A built page
#: names a hashed chunk; the dev server names the source module.
_ENTRY = """() => {
  const el = document.querySelector('script[type="module"][src]');
  return el ? el.getAttribute('src') : '';
}"""


def _rendered_build_id(page: object, dist: Path) -> str:
    """The build that produced THIS page, not the one last written to disk.

    The manifest still has to agree: a hash scraped off a page proves the
    page was built, and matching it against the manifest proves it was built
    from the tree being stamped. Disagreement means the served bundle and the
    local dist are different builds, and neither may be claimed.
    """
    src = str(page.evaluate(_ENTRY))  # type: ignore[attr-defined]
    served = entry_hash(src)
    if served == "unbuilt":
        return "unbuilt"
    return served if served == vite_build_id(dist) else "unbuilt"


def _stamp(build: str, browser_version: str) -> str:
    """The two halves of a reproducible render, in one string.

    Rule 4 wants a `renderer_version` on every output; rule 9 wants it to
    mean something. A Vite hash alone does not survive a Chromium bump, and a
    Chromium version alone does not survive a frontend change, so it is both
    or it is decoration.
    """
    return f"vite {build} · chromium {browser_version}"


def render_url(url: str, *, dist: Path, timeout_ms: int = 30_000) -> RenderedPdf:
    """Render one report URL to archived-quality PDF bytes."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            version = browser.version
            page = browser.new_page(viewport={"width": 1200, "height": 900})
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            # The document says when it is ready; never race it (STACK.md §6).
            page.wait_for_selector("[data-report-ready]", timeout=timeout_ms)
            page.evaluate("() => document.fonts.ready")
            # Stamped from the page, after it loaded - see the module note.
            stamp = _stamp(_rendered_build_id(page, dist), version)
            # The payload cannot know what rendered it - the render happens
            # after the payload is stored, and the payload is served verbatim
            # (rule 9). So the archived artifact is stamped here, in the DOM,
            # rather than by editing the data of record.
            page.evaluate(
                "(v) => { const el = document.querySelector('[data-renderer-version]');"
                " if (el) el.textContent = v; }",
                stamp,
            )
            pdf = page.pdf(
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template=_HEADER,
                footer_template=_FOOTER,
                margin={side: f"{MARGIN_MM}mm" for side in ("top", "bottom", "left", "right")},
            )
        finally:
            browser.close()
    return RenderedPdf(pdf=pdf, renderer_version=stamp, pages=count_pages(pdf))


def count_pages(pdf: bytes) -> int:
    """Pages in a PDF, without a PDF library.

    ``/Type /Page`` appears once per page object and ``/Type /Pages`` is the
    tree node, so the negative lookahead is the whole trick. Counting bytes
    we already hold beats adding a dependency to the production path for one
    integer - the test suite may use `pypdf`; the renderer does not need it.
    """
    return len(re.findall(rb"/Type\s*/Page(?![sA-Za-z])", pdf))
