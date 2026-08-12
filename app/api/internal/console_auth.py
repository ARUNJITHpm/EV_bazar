"""Console session endpoints and the guard - PART C.0.

    "Guard on the server, not in the router. A hidden React route is not
     access control - the endpoints are what must refuse."

``require_operator`` is that refusal, and every console endpoint takes it as a
router-level dependency so a new panel is protected by default rather than by
the author remembering. Adding an unguarded console route should require
writing something deliberate, not forgetting something.

Three states, and the middle one is the one that usually goes wrong:

  configured + valid session   -> 200
  configured + no session      -> 401
  NOT configured               -> 503, never 200. An unconfigured console must
                                  refuse, because "we have not set the
                                  password yet" is exactly when the data is
                                  least protected and most interesting.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.auth import (
    COOKIE_NAME,
    PasswordHashError,
    issue_session,
    read_session,
    verify_password,
)
from app.config import Settings, get_settings

router = APIRouter()

#: Floor on how long a login attempt takes, in seconds. Not a rate limiter -
#: it is one operator and one password - but it removes the timing difference
#: between "no session configured", "wrong password" and "malformed hash",
#: and it makes an online guessing loop tediously slow.
_MIN_LOGIN_SECONDS = 0.25


def require_operator(
    evsite_console: str | None = Cookie(default=None, alias=COOKIE_NAME),
    settings: Settings = Depends(get_settings),
) -> str:
    """FastAPI dependency. Returns the operator name or refuses the request."""
    if not settings.console_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "console auth is not configured (PLAN C.0). Set console_secret_key and "
                "console_password_hash - see `uv run python -m scripts.console_password`."
            ),
        )

    if not evsite_console:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not signed in")

    assert settings.console_secret_key is not None  # noqa: S101 - narrowed by console_configured
    operator = read_session(
        settings.console_secret_key,
        evsite_console,
        max_age_seconds=settings.console_session_max_age_seconds,
    )
    if operator is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="session expired or invalid"
        )
    return operator


class LoginIn(BaseModel):
    password: str


class Operator(BaseModel):
    operator: str


@router.post("/console/login", response_model=Operator)
def login(
    body: LoginIn,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> Operator:
    started = time.monotonic()

    def _slow_fail(code: int, detail: str) -> HTTPException:
        elapsed = time.monotonic() - started
        time.sleep(max(0.0, _MIN_LOGIN_SECONDS - elapsed))
        return HTTPException(status_code=code, detail=detail)

    if not settings.console_configured:
        raise _slow_fail(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "console auth is not configured (PLAN C.0).",
        )

    assert settings.console_password_hash is not None  # noqa: S101 - narrowed above
    assert settings.console_secret_key is not None  # noqa: S101 - narrowed above

    try:
        ok = verify_password(body.password, settings.console_password_hash)
    except PasswordHashError:
        # A hash we cannot parse is a deployment mistake. Refusing everyone is
        # the correct response; admitting everyone is not.
        raise _slow_fail(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "console password hash is malformed; regenerate it.",
        ) from None

    if not ok:
        raise _slow_fail(status.HTTP_401_UNAUTHORIZED, "incorrect password")

    token = issue_session(settings.console_secret_key, operator=settings.console_operator)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.console_session_max_age_seconds,
        # httpOnly: JavaScript must not be able to read this. The console
        # renders operator-supplied CPO notes, so an XSS that could read the
        # cookie would hand over the session outright.
        httponly=True,
        # lax rather than strict: strict breaks returning to the console from
        # any external link, and there is no cross-site GET here worth
        # protecting that lax does not already cover.
        samesite="lax",
        # Only prod is served over TLS. Dev and test run on plain http, where
        # a Secure cookie is silently dropped by the browser - which looks
        # exactly like a broken login and wastes an afternoon.
        secure=settings.env == "prod",
        path="/",
    )
    return Operator(operator=settings.console_operator)


@router.post("/console/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, settings: Settings = Depends(get_settings)) -> Response:
    """Clear the cookie.

    Deliberately unguarded: signing out must work even from a session that has
    already expired, and refusing to clear a cookie helps nobody. The attribute
    set here must match the login cookie or the browser will keep the old one.
    """
    response.delete_cookie(
        COOKIE_NAME, path="/", httponly=True, samesite="lax", secure=settings.env != "dev"
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/console/me", response_model=Operator)
def me(operator: str = Depends(require_operator)) -> Operator:
    """Who am I. The SPA calls this on load to decide login vs console."""
    return Operator(operator=operator)
