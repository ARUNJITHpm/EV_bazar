"""Create upcoming monthly partitions - PART 0.1 maintenance.

    uv run python -m scripts.ensure_partitions [months_ahead]

Run monthly (cron, or the poller's own scheduler). Idempotent.

Covers both partitioned tables: the raw archive and the derived transition
log. Forgetting the archive would be the worse of the two - it is the table
that cannot be rebuilt.

The DEFAULT partition means a missed run never rejects an insert, so this
script falling behind degrades performance rather than losing data. Check
``rows in default`` in the output: anything above zero means partitions were
late and those rows should be moved into a proper partition eventually.
"""

from __future__ import annotations

import sys

from sqlalchemy import text

from app.db import engine

#: Every RANGE-partitioned table the poller writes to.
PARTITIONED_TABLES = ("poll_raw_payloads", "charger_status_events")


def _create_month_sql(table: str, offset: int) -> str:
    """DDL for one month's partition of one table.

    The offset and table name are interpolated rather than bound: a
    ``DO $$ ... $$`` body is a dollar-quoted string literal, and psycopg binds
    server-side, so a placeholder inside it is never substituted. ``offset``
    is an int from ``range()`` and the table names are module constants, so
    there is nothing to inject.
    """
    return f"""
DO $$
DECLARE
    start_at DATE := (date_trunc('month', now()) + INTERVAL '{offset} month')::date;
    end_at   DATE := (date_trunc('month', now()) + INTERVAL '{offset + 1} month')::date;
    part     TEXT := '{table}_' || to_char(start_at, 'YYYY_MM');
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF {table} '
        'FOR VALUES FROM (%L) TO (%L)', part, start_at, end_at
    );
END $$;
"""


def main(months_ahead: int = 6) -> int:
    late = False

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for table in PARTITIONED_TABLES:
            for offset in range(months_ahead):
                conn.execute(text(_create_month_sql(table, offset)))

            partitions = (
                conn.execute(
                    text(
                        """
                    SELECT c.relname
                    FROM pg_inherits i
                    JOIN pg_class c ON c.oid = i.inhrelid
                    JOIN pg_class p ON p.oid = i.inhparent
                    WHERE p.relname = :table
                    ORDER BY c.relname
                    """
                    ),
                    {"table": table},
                )
                .scalars()
                .all()
            )

            in_default = conn.execute(
                text(f"SELECT count(*) FROM {table}_default")  # noqa: S608 - module constant
            ).scalar_one()

            print(f"{table} - {len(partitions)} partitions:")
            for name in partitions:
                print("  ", name)
            print(f"  rows in default partition: {in_default}")
            if in_default:
                late = True
                print("  ^ partitions were late. Those rows belong in a monthly partition.")

    return 1 if late else 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 6))
