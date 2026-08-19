"""Report payloads - PLAN 5's read side.

``GET /api/internal/reports/{report_id}`` returns the STORED payload
(AGENTS.md rule 9): it never re-runs the pipeline, so a customer rereading
last quarter's report sees last quarter's numbers.

Mounted on the OPEN group, and that is a decision, not an oversight
(``api/internal/__init__.py`` asks for one): the report page is the
customer-facing surface, and a customer holds a link, not a console login.
The report id is the capability - customer ids are UUID strings that do not
enumerate (the same reasoning as ``sites.site_id``); the demo id is readable
because the demo is public by design.

The response is validated against ``ReportPayload`` on the way out. Stored
payloads ARE ``model_dump()`` outputs of that same model, so validation is an
identity - it exists to publish the shape into the OpenAPI schema the
frontend's generated types are built from, not to rewrite data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.report.payload import ReportPayload
from app.domain.report.store import get_payload

router = APIRouter()


@router.get("/reports/{report_id}", response_model=ReportPayload)
def report(report_id: str, session: Session = Depends(get_session)) -> ReportPayload:
    payload = get_payload(session, report_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="no such report")
    return ReportPayload.model_validate(payload)
