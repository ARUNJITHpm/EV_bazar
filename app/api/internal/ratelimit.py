"""Per-IP throttle for /assess - the one open endpoint that writes.

/assess is the funnel's front door (api/internal/assess.py): no login, and it
records a ``sites`` lead row on every call. Unauthenticated *and* writing is
the combination worth a ceiling - without one, a loop (a buggy client, or a
deliberate flood) fills the leads table and re-runs the ROI arithmetic for
free. This caps how fast a single caller can do that.

What it is NOT: an edge WAF. It keys on the caller's IP as the proxy chain
reports it (``X-Forwarded-For``), which a determined attacker can spoof or
rotate. The real defence against that lives at the edge - HF's front proxy,
Caddy, a CDN. This stops the honest failure - a runaway client, a naive
scraper - cheaply and in-process, and is documented as doing only that rather
than pretending to more.

In-process and per-worker on purpose: no Redis, no new dependency. One uvicorn
worker serves this Space, so one window per IP is the whole picture. Were it
scaled to N workers the effective ceiling becomes N x the configured rate - a
limit that loosens under scale, never one that wrongly rejects.
"""

from __future__ import annotations

import ipaddress
import math
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import NamedTuple

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings

#: Past this many distinct keys, sweep out the ones whose window has drained.
#: Comfortably above the distinct-IP count one small Space sees in a window; it
#: exists so a long uptime under churn cannot grow the map without bound.
_SWEEP_ABOVE = 4096


class RateDecision(NamedTuple):
    allowed: bool
    #: Seconds until the oldest hit ages out and a slot frees. 0 when allowed.
    retry_after: float


class SlidingWindowLimiter:
    """A trailing time window of hit timestamps per key.

    ``check(key, limit)`` records the moment and answers whether the key is
    still at or under ``limit`` hits within the trailing ``window_seconds``.
    The limit rides in per call rather than being fixed at construction, so a
    single process-wide instance serves whatever the live settings say and
    tests can vary it freely. Exact for the volumes one small Space sees;
    memory is bounded by sweeping keys whose window has fully drained.
    """

    def __init__(
        self,
        *,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int) -> RateDecision:
        now = self._clock()
        cutoff = now - self._window
        # Sync endpoints run in a threadpool, so several threads can land here
        # at once; the read-modify-write of one window must be atomic.
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                hits = self._hits[key] = deque()
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                # The oldest hit still in the window frees a slot when it ages out.
                return RateDecision(False, max(0.0, hits[0] + self._window - now))
            hits.append(now)
            if len(self._hits) > _SWEEP_ABOVE:
                self._sweep(cutoff)
            return RateDecision(True, 0.0)

    def _sweep(self, cutoff: float) -> None:
        # Drop keys whose most recent hit has itself aged out - they hold only
        # an empty or drained window and would otherwise linger forever.
        drained = [k for k, h in self._hits.items() if not h or h[-1] <= cutoff]
        for k in drained:
            del self._hits[k]


#: Process-wide, holding every live window. The dependency reads the ceiling
#: from settings on each call, so this instance never needs rebuilding.
_limiter = SlidingWindowLimiter()


def _chain_client(chain: str) -> str | None:
    """The last public address in a proxy chain, or None if there is none.

    Each proxy appends the address it received the request from, so the RIGHT
    end was written by infrastructure and the left end by whoever made the
    request. Walking in from the right, past our own private hops, lands on the
    address the outermost proxy actually saw - which a caller cannot choose.
    """
    for part in reversed(chain.split(",")):
        try:
            ip = ipaddress.ip_address(part.strip())
        except ValueError:
            continue
        if ip.is_global:
            return str(ip)
    return None


def client_key(request: Request) -> str:
    """The caller's IP, seen through the proxy chain.

    On the HF Space, Caddy does not trust the Space's front proxy and rewrites
    ``X-Forwarded-For`` to that proxy's own address, so every visitor would
    share a handful of windows. The Caddyfile therefore copies the chain the
    front proxy sent into ``X-Client-Chain`` before it is lost, and that is
    preferred here: it is only ever set by Caddy (``header_up`` replaces a
    caller's value), and we read the end the proxy wrote, not the end the
    caller can write. Without it (compose, a local run) the leftmost
    ``X-Forwarded-For`` is used - client-supplied and so spoofable (see the
    module docstring), still the right key for the failure modes this guards.
    """
    chain = request.headers.get("x-client-chain")
    if chain:
        found = _chain_client(chain)
        if found:
            return found
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def _refuse(decision: RateDecision, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers={"Retry-After": str(max(1, math.ceil(decision.retry_after)))},
    )


def rate_limit(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """FastAPI dependency: refuse a caller past the /assess ceiling.

    A non-positive ceiling disables the guard entirely - handy for a local run
    or a test that means to hammer the endpoint. Prod carries a real number.
    """
    limit = settings.assess_rate_limit_per_minute
    if limit <= 0:
        return
    decision = _limiter.check(client_key(request), limit)
    if not decision.allowed:
        raise _refuse(
            decision,
            "Too many site checks from this address in a short span. Wait a moment and try again.",
        )


#: Owner submissions, an hour wide and a bucket of their own. A submission is a
#: permanent row (the tables are append-only, so a bad one cannot be deleted),
#: which makes a per-minute ceiling the wrong shape: it lets a slow trickle
#: fill the table all day. Kept apart from ``_limiter`` so searching for a
#: station, or running /assess, never spends the submission allowance.
_submit_limiter = SlidingWindowLimiter(window_seconds=3600.0)


def owner_submit_limit(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """FastAPI dependency for ``POST /owner/submissions``: a per-IP hourly cap.

    Counts every attempt, refused-for-validation ones included - a caller
    probing the endpoint spends the allowance the same as one filling it.
    Non-positive disables it, like ``rate_limit``.
    """
    limit = settings.owner_submit_limit_per_hour
    if limit <= 0:
        return
    decision = _submit_limiter.check(client_key(request), limit)
    if not decision.allowed:
        raise _refuse(
            decision,
            "You have sent a lot of submissions from this address. Please try again in a while.",
        )


#: Owner sign-up and login attempts, an hour wide and separate from the rest: a
#: password guess is the abuse here, and it must not spend (or be spent by) the
#: submission allowance.
_auth_limiter = SlidingWindowLimiter(window_seconds=3600.0)

#: Attempts on ONE mobile number, whichever address they come from: a guesser who
#: rotates IPs still hits this. Every attempt counts, so a wrong guess is not free.
_phone_limiter = SlidingWindowLimiter(window_seconds=900.0)
PHONE_ATTEMPTS_PER_15_MIN = 10


def owner_auth_limit(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """FastAPI dependency for ``/owner/signup`` and ``/owner/login``: a per-IP hourly cap."""
    limit = settings.owner_auth_limit_per_hour
    if limit <= 0:
        return
    decision = _auth_limiter.check(client_key(request), limit)
    if not decision.allowed:
        raise _refuse(decision, "Too many sign-in attempts. Please try again in a while.")


#: Console password guesses. Its own bucket so a guesser cannot lock out, or be
#: helped by, the owner sign-in allowance.
_console_login_limiter = SlidingWindowLimiter(window_seconds=3600.0)


def console_login_limit(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """FastAPI dependency for ``POST /console/login``: a per-IP hourly cap."""
    limit = settings.console_login_limit_per_hour
    if limit <= 0:
        return
    decision = _console_login_limiter.check(client_key(request), limit)
    if not decision.allowed:
        raise _refuse(decision, "Too many sign-in attempts. Please try again in a while.")


#: Report reads, a minute wide. The report id is the capability, so a caller
#: walking ids is the abuse; this makes that walk slow.
_report_limiter = SlidingWindowLimiter()


def report_read_limit(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """FastAPI dependency for ``GET /reports/{id}``: a per-IP per-minute cap."""
    limit = settings.report_read_limit_per_minute
    if limit <= 0:
        return
    decision = _report_limiter.check(client_key(request), limit)
    if not decision.allowed:
        raise _refuse(decision, "Too many requests. Wait a moment and try again.")


def check_phone_attempts(phone: str, settings: Settings) -> None:
    """Refuse a login for a number that has been tried too often in the last 15 minutes."""
    if settings.owner_auth_limit_per_hour <= 0:
        return
    decision = _phone_limiter.check(phone, PHONE_ATTEMPTS_PER_15_MIN)
    if not decision.allowed:
        raise _refuse(decision, "Too many attempts for this number. Please try again later.")
