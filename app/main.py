"""FastAPI app factory. JSON only - this backend renders no HTML.

Two API surfaces, mounted separately and deliberately (AGENTS.md):

  * ``api/v1``       CPO partners. Stable, versioned, contractual.
                     Breaking it breaks somebody else's integration.
  * ``api/internal`` Our own SPA. Free to reshape whenever the UI needs it.

The frontend is a build artifact served by Caddy in production, and by the
Vite dev server (proxying ``/api`` here) in development. No Node process
runs in production.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.internal import router as internal_router
from app.api.v1 import router as api_v1_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="EV Site Intelligence Platform",
        version="0.1.0",
        docs_url="/api/docs" if settings.env != "prod" else None,
        redoc_url=None,
    )

    # Dev only: Vite serves the SPA from a different origin. In production
    # Caddy serves dist/ and proxies /api, so both are same-origin and this
    # middleware adds nothing.
    if settings.env == "dev":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.frontend_origins,
            allow_credentials=True,  # console session cookie
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_v1_router, prefix="/api/v1")
    app.include_router(internal_router, prefix="/api/internal")

    return app


app = create_app()
