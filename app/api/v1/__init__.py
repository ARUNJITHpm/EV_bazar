"""Partner API v1.

Fills out in Part 7 (attribution reconciliation export). Versioned from the
start because a partner's finance team will pin to whatever they integrate
against first.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["partner-api"])


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok", "api_version": "v1"}
