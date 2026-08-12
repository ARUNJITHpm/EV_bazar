"""Liveness and readiness.

Feeds the console Overview panel (PLAN Part C.0) as well as the container
orchestrator.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.config import get_settings
from app.db import engine

router = APIRouter()


class Health(BaseModel):
    status: str


class Readiness(BaseModel):
    database: str
    postgis: str
    env: str
    paid_providers_enabled: list[str]


@router.get("/healthz", response_model=Health)
def healthz() -> Health:
    """Liveness only. Does not touch the database."""
    return Health(status="ok")


@router.get("/readyz", response_model=Readiness)
def readyz() -> JSONResponse:
    """Readiness: database reachable and PostGIS actually installed.

    PostGIS is checked explicitly because every spatial query in Part 1
    silently becomes an error without it, and the failure surfaces far from
    the cause.
    """
    settings = get_settings()
    database = "unavailable"
    postgis = "unavailable"
    status_code = 200

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            database = "ok"
            postgis = str(conn.execute(text("SELECT postgis_version()")).scalar_one())
    except Exception as exc:  # noqa: BLE001 - readiness reports, it does not raise
        database = f"error: {exc.__class__.__name__}"
        status_code = 503

    payload = Readiness(
        database=database,
        postgis=postgis,
        env=settings.env,
        paid_providers_enabled=[
            name for name, provider in settings.paid_providers.items() if provider.enabled
        ],
    )
    return JSONResponse(payload.model_dump(), status_code=status_code)
