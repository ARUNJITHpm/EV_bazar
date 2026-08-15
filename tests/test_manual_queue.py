"""PART 1.3 L6 - the manual queue.

The queue is what makes refusing affordable: every level above is allowed to
say "I don't know" only because there is somewhere for that answer to go. So
the tests here are mostly about the queue not quietly losing work, or quietly
re-creating work already done.

The load-bearing one is ``test_resolving_writes_the_point_back_into_the_cache``.
Without the write-back the next lookup of that address misses again and
re-queues it, and the operator's twenty seconds buy nothing.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.resolution import GeocodeResult, GeocodeStatus, geocode, manual, normalise_address
from app.models import Base
from app.models.geocode import GeocodeCache
from app.models.manual_queue import GeocodeManualQueue, QueueStatus

ADDRESS = "behind the old tyre shop, Perumbavoor"


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[GeocodeCache.__table__, GeocodeManualQueue.__table__])
    with Session(engine) as s:
        yield s


class _Fake:
    source = "nominatim"

    def __init__(self, result: GeocodeResult | None) -> None:
        self.result = result

    def search(self, client: object, query: str, *, pincode: str | None = None):  # noqa: ANN201
        return self.result


def _miss(session: Session, address: str = ADDRESS):  # noqa: ANN202
    return geocode(
        session, address, geocoders=[_Fake(None)], client=httpx.Client(), use_cache=False
    )


def test_only_a_miss_is_queued(session: Session) -> None:
    hit = geocode(
        session,
        "MG Road Kochi",
        geocoders=[_Fake(GeocodeResult(9.93, 76.26, "nominatim"))],
        client=httpx.Client(),
        use_cache=False,
    )
    assert hit.status is GeocodeStatus.HIT
    assert manual.enqueue(session, hit) is None


def test_the_reason_the_cascade_gave_up_is_kept(session: Session) -> None:
    """'Unresolved' tells the operator nothing; 'Google and Nominatim disagree
    by 40 km' tells them where to look."""
    job = manual.enqueue(session, _miss(session))
    assert job is not None
    assert job.reason and "manual queue" in job.reason
    assert job.raw_input == ADDRESS


def test_the_same_address_asked_twice_is_one_job_with_two_hits(session: Session) -> None:
    """A queue sorted by hits spends the twenty seconds where they buy most."""
    manual.enqueue(session, _miss(session))
    job = manual.enqueue(session, _miss(session))

    assert job is not None and job.hits == 2
    assert len(manual.open_jobs(session)) == 1


def test_resolving_writes_the_point_back_into_the_cache(session: Session) -> None:
    job = manual.enqueue(session, _miss(session))
    assert job is not None

    manual.resolve(session, job.id, lat=10.1073, lng=76.4750, operator="arun", note="gate 2")

    assert job.status == QueueStatus.RESOLVED.value
    row = session.get(GeocodeCache, normalise_address(ADDRESS).cache_key)
    assert row is not None
    assert (row.lat, row.lng) == (10.1073, 76.4750)
    assert row.source == manual.MANUAL_SOURCE
    assert row.confidence == "high"


def test_a_resolved_address_is_a_cache_hit_and_never_reaches_a_geocoder(
    session: Session,
) -> None:
    job = manual.enqueue(session, _miss(session))
    assert job is not None
    manual.resolve(session, job.id, lat=10.1073, lng=76.4750, operator="arun")

    class _Explode:
        source = "nominatim"

        def search(self, *a: object, **k: object) -> None:
            raise AssertionError("the cascade re-asked an address a human already placed")

    out = geocode(session, ADDRESS, geocoders=[_Explode()], client=httpx.Client())
    assert out.status is GeocodeStatus.CACHED
    assert out.source == manual.MANUAL_SOURCE


def test_rejecting_records_the_verdict_and_invents_no_coordinates(session: Session) -> None:
    """A human who could not place it must not leave a point behind."""
    job = manual.enqueue(session, _miss(session))
    assert job is not None

    manual.reject(session, job.id, operator="arun", note="address does not describe a place")

    assert job.status == QueueStatus.REJECTED.value
    assert job.lat is None
    assert manual.open_jobs(session) == []
    row = session.get(GeocodeCache, normalise_address(ADDRESS).cache_key)
    assert row is None or not row.is_hit


def test_a_resolved_job_that_misses_again_reopens_rather_than_duplicating(
    session: Session,
) -> None:
    job = manual.enqueue(session, _miss(session))
    assert job is not None
    manual.resolve(session, job.id, lat=10.1, lng=76.4, operator="arun")

    again = manual.enqueue(session, _miss(session))

    assert again is not None and again.id == job.id
    assert again.status == QueueStatus.OPEN.value
    assert again.resolved_by is None


def test_an_unknown_job_is_a_lookup_error_not_a_silent_no_op(session: Session) -> None:
    with pytest.raises(LookupError):
        manual.resolve(session, 9999, lat=10.0, lng=76.0, operator="arun")
