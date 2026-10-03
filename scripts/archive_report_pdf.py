"""Render a stored report and freeze the bytes against it - Track B R11.

This is the second half of AGENTS.md rule 9. ``generate_demo_report.py``
writes the payload, which answers "what did you tell me". This writes the
artifact, which answers "this is not what my report LOOKED like" - a question
the payload cannot answer, because a browser render is not reproducible
across Chromium versions.

ORDER MATTERS AND IS NOT NEGOTIABLE. The renderer loads the report's own URL,
so the payload has to be stored first; the PDF is therefore always a second
step and never part of the same transaction. That is also why ``reports``
keeps its outright refusal to UPDATE and the artifact lives in its own
insert-only table (migration 0013).

Dry by default, like the demo generator: without ``--write`` it renders,
prints what it found and archives nothing.

POINT IT AT A BUILT FRONTEND, NOT THE DEV SERVER. The stamp carries the Vite
build hash, and ``render.py`` reads that hash off the page it loaded rather
than off the disk - so a dev render stamps "unbuilt" and this script refuses
to archive it.

That refusal is the point, and the margin is small enough to be worth stating
plainly: measured on the demo, same payload, same Chromium, each repeatable
to the byte, the dev server renders 848,039 bytes and the build 848,180 - 26
pages either way, and a document that LOOKS identical. It is still not the
same artifact, and an archive whose job is to answer "this is not what I
received" may not be one build out.

    npm run build --prefix frontend && npm run preview --prefix frontend
    python -m scripts.archive_report_pdf KL-TVM-DEMO-001 --base http://localhost:4173
    python -m scripts.archive_report_pdf KL-TVM-DEMO-001 --base http://localhost:4173 --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.db import SessionLocal
from app.domain.report.store import archive_pdf, get_payload, get_pdf
from app.pdf.render import render_url, vite_build_id

#: Where the SPA is served from while rendering. In production this is the
#: same origin Caddy serves; in development it is the Vite dev server, and a
#: dev render is exactly the "unbuilt" case the stamp is designed to expose.
DEFAULT_BASE = "http://localhost:5173"
DEFAULT_DIST = Path("frontend/dist")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_id", help="the report to render, e.g. KL-TVM-DEMO-001")
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"SPA origin (default {DEFAULT_BASE})")
    parser.add_argument("--dist", type=Path, default=DEFAULT_DIST, help="built frontend directory")
    parser.add_argument("--write", action="store_true", help="archive the bytes against the report")
    parser.add_argument("--out", type=Path, help="also write the PDF to this path")
    args = parser.parse_args()

    build = vite_build_id(args.dist)
    if build == "unbuilt":
        print(f"warning: {args.dist} has no Vite manifest - this render will stamp 'unbuilt'")
        print("         run `npm run build` in frontend/ before archiving anything real")

    with SessionLocal() as session:
        if get_payload(session, args.report_id) is None:
            print(f"no report {args.report_id} - nothing to render")
            return 1
        existing = get_pdf(session, args.report_id)
        if existing is not None:
            print(
                f"already archived: {existing.pages} pages, {existing.byte_size:,} bytes, "
                f"{existing.renderer_version}"
            )

        url = f"{args.base.rstrip('/')}/report/{args.report_id}"
        print(f"rendering     {url}")
        rendered = render_url(url, dist=args.dist)
        print(f"renderer      {rendered.renderer_version}")
        print(f"result        {rendered.pages} pages, {len(rendered.pdf):,} bytes")

        if args.out is not None:
            args.out.write_bytes(rendered.pdf)
            print(f"written       {args.out}")

        if not args.write:
            print("dry run - rerun with --write to archive against the report")
            return 0

        # An archive exists to be shown to someone who disputes what they
        # received. Bytes that no build produced cannot serve that purpose,
        # so this is a refusal rather than a warning - the failure it
        # prevents is silent and permanent, and the row is insert-only.
        if "unbuilt" in rendered.renderer_version:
            print("REFUSING to archive an unbuilt render - nothing could reproduce it.")
            print(f"         {args.base} is serving unbundled sources, or a different build")
            print("         than --dist. Build the frontend and serve dist/ (npm run preview).")
            return 1

        archive_pdf(
            session,
            args.report_id,
            pdf=rendered.pdf,
            renderer_version=rendered.renderer_version,
            pages=rendered.pages,
        )
        session.commit()
        print(f"archived      {args.report_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
