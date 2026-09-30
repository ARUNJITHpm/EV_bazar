"""Charging-network schema: the shape the migration and the loader rely on.

The tables carry a PostGIS column SQLite cannot create, so this checks the
declared metadata rather than a live database; migration 0015 itself was run
against Postgres in a rolled-back transaction when it was written.
"""

from __future__ import annotations

import pytest

from app.models import Base

NEW = (
    "data_sources",
    "cpos",
    "cpo_aliases",
    "stations",
    "chargers",
    "connectors",
    "scraped_records",
    "station_listings",
    "charger_listings",
)
MUTABLE = tuple(t for t in NEW if t != "scraped_records")


def _table(name: str):  # noqa: ANN202
    return Base.metadata.tables[name]


@pytest.mark.parametrize("name", NEW)
def test_every_new_table_is_registered(name: str) -> None:
    assert name in Base.metadata.tables


@pytest.mark.parametrize("name", MUTABLE)
def test_mutable_tables_carry_created_and_updated_times(name: str) -> None:
    cols = _table(name).c
    for col in ("created_at", "updated_at"):
        assert not cols[col].nullable
        assert cols[col].server_default is not None


def test_scraped_records_is_insert_only_so_it_has_no_updated_at() -> None:
    assert "updated_at" not in _table("scraped_records").c
    assert not _table("scraped_records").c.scraped_at.nullable


def _unique(name: str) -> set[frozenset[str]]:
    t = _table(name)
    out = {frozenset(c.name for c in u.columns) for u in t.constraints if hasattr(u, "columns")}
    return {u for u in out if len(u) > 0}


def test_one_source_key_is_one_listing() -> None:
    assert frozenset({"source_id", "source_key"}) in _unique("station_listings")
    assert frozenset({"source_id", "source_key"}) in _unique("charger_listings")


def test_an_unchanged_rescrape_is_not_a_new_record() -> None:
    assert frozenset({"source_id", "source_key", "content_hash"}) in _unique("scraped_records")


def test_the_hierarchy_points_the_right_way() -> None:
    def fk(table: str, col: str) -> str:
        (key,) = _table(table).c[col].foreign_keys
        return key.column.table.name

    assert fk("chargers", "station_id") == "stations"
    assert fk("connectors", "charger_id") == "chargers"
    assert fk("stations", "cpo_id") == "cpos"
    assert fk("station_listings", "last_scrape_id") == "scraped_records"


def test_a_charger_can_be_marked_inferred() -> None:
    col = _table("chargers").c.inferred
    assert not col.nullable
    assert col.server_default is not None


def test_a_station_can_be_merged_but_never_needs_deleting() -> None:
    assert _table("stations").c.merged_into_id.nullable
