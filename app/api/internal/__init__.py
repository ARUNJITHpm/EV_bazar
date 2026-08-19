"""Internal API - consumed by our own SPA only.

Not a contract with anyone outside the building, so it may be reshaped
whenever the UI needs a different shape. That freedom is exactly why it is
kept apart from ``api/v1`` (AGENTS.md).

Two groups, and the split is the access-control boundary (PLAN C.0):

    open      liveness and readiness probes, plus login itself. No business
              data: a status code and whether the database answers.
    guarded   everything else, behind ``require_operator`` at the ROUTER
              level - so a new panel is protected because it was added here,
              not because its author remembered a decorator.

If you are adding a console endpoint, add it to ``guarded``. Adding it to the
open group should feel like a decision, because it is one.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.internal import (
    competitors,
    console_auth,
    geocoding,
    health,
    lookup,
    poller,
    progress,
    reports,
    vahan,
)
from app.api.internal.console_auth import require_operator

router = APIRouter()

# --- open ------------------------------------------------------------------
router.include_router(health.router, tags=["internal-health"])
router.include_router(poller.public_router, tags=["internal-poller"])
router.include_router(console_auth.router, tags=["console-auth"])
# Reports are open BY DECISION: the report page is customer-facing and the
# customer holds a link, not a login. The report id is the capability - see
# the module docstring.
router.include_router(reports.router, tags=["internal-reports"])

# --- guarded ---------------------------------------------------------------
guarded = APIRouter(dependencies=[Depends(require_operator)])
guarded.include_router(poller.router, tags=["internal-poller"])
guarded.include_router(geocoding.router, tags=["internal-geocoding"])
guarded.include_router(lookup.router, tags=["internal-lookup"])
guarded.include_router(progress.router, tags=["internal-progress"])
guarded.include_router(competitors.router, tags=["internal-competitors"])
guarded.include_router(vahan.router, tags=["internal-vahan"])

router.include_router(guarded)
