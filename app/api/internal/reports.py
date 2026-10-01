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

The stored payload is validated against ``ReportPayload`` for the API contract,
then returned directly as JSON. Optional fields on old reports are never filled
into the response, and no context or financial calculation runs on this path.
The response model continues to publish the generated OpenAPI client shape.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.report.payload import ReportPayload
from app.domain.report.store import get_payload

router = APIRouter()


@router.get("/reports/{report_id}", response_model=ReportPayload)
def report(report_id: str, session: Session = Depends(get_session)) -> JSONResponse:
    payload = get_payload(session, report_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="no such report")
    ReportPayload.model_validate(payload)
    return JSONResponse(content=payload)
