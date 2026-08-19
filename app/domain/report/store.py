"""Persisting and serving report payloads - AGENTS.md rule 9's I/O shell.

``save_report`` writes the assembled payload as the data of record;
``get_payload`` hands back exactly what was stored. No recomputation on the
read path, ever - a report answers with the numbers its customer saw, not
with today's.

Immutability is enforced by database rules (migration 0012); the demo row is
the one stated exception and this module honours the same line: ``save_report``
refuses to overwrite an existing report unless the stored row is a demo.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.report.payload import ReportPayload
from app.models.report import Report


def save_report(
    session: Session,
    payload: ReportPayload,
    *,
    site_id: uuid.UUID | None,
    model_version: str,
    economics_version: str,
) -> Report:
    """Insert the payload as the data of record; refuse silent overwrites.

    A demo row may be regenerated in place (delete + insert, which the
    append-only rules permit only for demo payloads). A non-demo id colliding
    is a caller bug - a correction is a NEW report id, not a rewrite.
    """
    existing = session.get(Report, payload.report_id)
    if existing is not None:
        if not bool(existing.payload.get("demo")):
            raise ValueError(
                f"report {payload.report_id} already exists and is not a demo - "
                "a correction is a new report id, never an overwrite"
            )
        session.delete(existing)
        session.flush()

    row = Report(
        report_id=payload.report_id,
        site_id=site_id,
        payload=payload.model_dump(),
        economics_version=economics_version,
        model_version=model_version,
    )
    session.add(row)
    session.flush()
    return row


def get_payload(session: Session, report_id: str) -> dict[str, object] | None:
    """The stored payload, verbatim. None when no such report exists."""
    row = session.execute(
        select(Report.payload).where(Report.report_id == report_id)
    ).scalar_one_or_none()
    return row
