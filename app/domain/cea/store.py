"""Persisting a parsed CEA report - the I/O shell around ``parse``.

Append-only: a file already stored (same sha256) is skipped, never rewritten;
a re-issued report is a different file and lands beside the first.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.cea.parse import MEASURES, SPANS, Report, lgd_state_code
from app.models.cea import CeaEvConsumption
from app.models.reference import State


@dataclass
class StoreResult:
    inserted: int = 0
    already_stored: bool = False
    unmatched_states: list[str] = field(default_factory=list)


def is_stored(session: Session, source_sha256: str) -> bool:
    return (
        session.execute(
            select(CeaEvConsumption.id)
            .where(CeaEvConsumption.source_sha256 == source_sha256)
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def store_report(
    session: Session, report: Report, *, source_url: str, source_sha256: str
) -> StoreResult:
    """Insert every state, DISCOM and all-India row, for both spans."""
    result = StoreResult()
    if is_stored(session, source_sha256):
        result.already_stored = True
        return result
    states = {
        name: code for code, name in session.execute(select(State.lgd_state_code, State.name))
    }
    rows = [*report.states, *report.discoms, *([report.india] if report.india else [])]
    for row in rows:
        code = None if row.geography == "india" else lgd_state_code(row.state_name, states)
        if (
            code is None
            and row.geography == "state"
            and row.state_name not in result.unmatched_states
        ):
            result.unmatched_states.append(row.state_name)
        for span in SPANS:
            values = getattr(row, span)
            session.add(
                CeaEvConsumption(
                    report_month=report.report_month,
                    span=span,
                    span_start=report.report_month if span == "month" else report.fy_start,
                    geography=row.geography,
                    state_name=row.state_name,
                    lgd_state_code=code,
                    discom=row.discom,
                    source_url=source_url,
                    source_sha256=source_sha256,
                    **{measure: values[measure] for measure in MEASURES},
                )
            )
            result.inserted += 1
    session.flush()
    return result
