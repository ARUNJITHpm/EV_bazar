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


def client_key(request: Request) -> str:
    """The caller's IP, seen through the proxy chain.

    Behind Caddy (prod) and HF's own front proxy, ``request.client`` is the
    loopback proxy, not the caller - every request would share one window. The
    chain is in ``X-Forwarded-For``, left-to-right from the original client, so
    the leftmost entry is the closest thing to the real caller we can see. It
    is client-supplied and so spoofable (see the module docstring); it is still
    the right key for the failure modes this guards.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


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
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many site checks from this address in a short span. "
                "Wait a moment and try again."
            ),
            headers={"Retry-After": str(max(1, math.ceil(decision.retry_after)))},
        )
