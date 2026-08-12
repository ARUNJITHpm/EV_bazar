"""Shared test fixtures.

The one shim worth explaining: ``charger_status_events`` and
``poll_raw_payloads`` are RANGE-partitioned on Postgres, and Postgres requires
the partition key in the primary key - so both carry a composite
``(id, observed_at)`` PK. SQLite only autoincrements an ``INTEGER PRIMARY KEY``
that stands alone, so inserts that rely on the database to allocate ``id``
fail there.

Rather than reshape the schema to suit the test database - which would mean
testing something we do not ship - ids are allocated in Python when, and only
when, the connection is SQLite. Postgres keeps using IDENTITY.
"""

from __future__ import annotations

import itertools
from typing import Any

import pytest
from sqlalchemy import event

from app.models.charger_status import ChargerStatusEvent, PollRawPayload

_ids = itertools.count(1)


def _assign_sqlite_id(mapper: Any, connection: Any, target: Any) -> None:
    if connection.dialect.name == "sqlite" and target.id is None:
        target.id = next(_ids)


for model in (ChargerStatusEvent, PollRawPayload):
    event.listen(model, "before_insert", _assign_sqlite_id, propagate=True)


@pytest.fixture(autouse=True)
def _isolate_settings_cache() -> None:
    """Settings are ``lru_cache``d; a test that constructs its own must not
    leak into the next one."""
    from app.config import get_settings

    get_settings.cache_clear()
