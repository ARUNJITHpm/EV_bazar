"""The VAHAN store shell's resolution logic - PART 4.1.

The upsert itself is exercised live by ``scripts.ingest_vahan --dry-run`` against
the real PostGIS database; what is pinned here without a database is the one
non-trivial decision in ``resolve_rto_districts``: an RTO whose office point
fails to place must still carry its state, taken from its own two-letter code and
never lost to a NULL. The point-in-polygon call is patched out - this test is
about the fallback, not the geometry.
"""

from __future__ import annotations

from app.domain.vahan import store
from app.domain.vahan.store import RtoRef, resolve_rto_districts


def test_placed_rto_takes_pip_district_and_state(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    refs = [RtoRef("KL", "ERNAKULAM RTO - KL7", 9.98, 76.28)]
    monkeypatch.setattr(store, "bulk_resolve_districts", lambda _s, _p: [(302, 32)])
    placement = resolve_rto_districts(session=None, refs=refs)  # type: ignore[arg-type]
    assert placement[("KL", "ERNAKULAM RTO - KL7")] == (302, 32)


def test_unplaced_rto_keeps_known_state(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    refs = [RtoRef("TN", "SOMEWHERE - TN99", 0.0, 0.0)]  # a point in the ocean
    monkeypatch.setattr(store, "bulk_resolve_districts", lambda _s, _p: [(None, None)])
    placement = resolve_rto_districts(session=None, refs=refs)  # type: ignore[arg-type]
    # district lost, but TN -> 33 survives from the RTO's own code
    assert placement[("TN", "SOMEWHERE - TN99")] == (None, 33)


def test_rto_without_coordinates_is_unplaced_not_queried(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    refs = [RtoRef("KL", "NO COORDS - KL00", None, None)]
    # the coordinate-less RTO must never reach the point-in-polygon query
    monkeypatch.setattr(
        store,
        "bulk_resolve_districts",
        lambda _s, points: ([] if not points else pytest_fail_unexpected()),
    )
    placement = resolve_rto_districts(session=None, refs=refs)  # type: ignore[arg-type]
    assert placement[("KL", "NO COORDS - KL00")] == (None, 32)


def pytest_fail_unexpected() -> list[tuple[int, int]]:
    raise AssertionError("coordinate-less RTO should not be sent to point-in-polygon")
