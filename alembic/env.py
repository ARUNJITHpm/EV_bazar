"""Alembic environment.

Reads the database URL from app.config so there is one source of truth, and
hides two classes of table from autogenerate that are real but are not ours to
migrate:

* **PostGIS's own** - otherwise every migration tries to drop ``spatial_ref_sys``.
* **Partition children** - ``scripts/ensure_partitions.py`` creates one
  ``charger_status_events_YYYY_MM`` per month, and autogenerate sees a table
  with no model and proposes dropping it. Left unfiltered, ``alembic check``
  goes red the first time partitions are created and redder every month, which
  trains everyone to stop reading it - and the one month it reports a *real*
  drift, nobody looks.
"""

import re
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.config import get_settings
from app.models import Base  # imports every model module - keep it that way

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# PostGIS creates and manages these. They are not ours to migrate.
POSTGIS_MANAGED = {
    "spatial_ref_sys",
    "geography_columns",
    "geometry_columns",
    "raster_columns",
    "raster_overviews",
}


#: A child of a declaratively partitioned table: ``<parent>_2026_08``, or the
#: ``<parent>_default`` backstop. Anchored to the parents we actually partition
#: so an unrelated table that happens to end in a year-month is still compared.
PARTITIONED = ("charger_status_events", "poll_raw_payloads")
_PARTITION_CHILD = re.compile(r"^(?:" + "|".join(PARTITIONED) + r")_(?:\d{4}_\d{2}|default)$")


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table":
        return not (name in POSTGIS_MANAGED or _PARTITION_CHILD.match(name))
    # An index belonging to a partition child is skipped with its table.
    if type_ == "index" and obj.table is not None:
        return not _PARTITION_CHILD.match(obj.table.name)
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
