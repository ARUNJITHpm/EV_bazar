"""Charging network: CPOs, stations, chargers, connectors, listings, scraped records.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-30

Additive only: ``competitor_stations`` and everything that references it are
untouched, so nothing reads or writes the new tables until code is pointed at
them. The mutable tables carry ``created_at`` / ``updated_at`` and a trigger that
keeps ``updated_at`` honest for any writer, not only the ORM. ``scraped_records``
is insert-only in the database (AGENTS.md rule 3's pattern), like the poller's
raw pages: what a source said is evidence and is never edited.

``data_sources`` is seeded with the five feeds already in ``competitor_stations``
so the backfill has something to point at.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Tables whose ``updated_at`` the trigger maintains.
MUTABLE = (
    "data_sources",
    "cpos",
    "cpo_aliases",
    "stations",
    "chargers",
    "connectors",
    "station_listings",
    "charger_listings",
)


def _created() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )


def _updated() -> sa.Column:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )


def _seen(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("base_url", sa.Text()),
        sa.Column("notes", sa.Text()),
        _created(),
        _updated(),
        sa.CheckConstraint(
            "kind IN ('emsp_app','aggregator','cpo_direct','open_data')",
            name="ck_data_source_kind",
        ),
    )

    op.create_table(
        "cpos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="cpo"),
        sa.Column("website", sa.Text()),
        sa.Column("notes", sa.Text()),
        _created(),
        _updated(),
        sa.CheckConstraint("kind IN ('cpo','utility','oem','other')", name="ck_cpo_kind"),
    )

    op.create_table(
        "cpo_aliases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alias_norm", sa.String(128), nullable=False, unique=True),
        sa.Column("alias_raw", sa.String(128), nullable=False),
        sa.Column("cpo_id", sa.Integer(), sa.ForeignKey("cpos.id")),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("first_seen_source_id", sa.Integer(), sa.ForeignKey("data_sources.id")),
        sa.Column("confirmed_by", sa.String(64)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        _created(),
        _updated(),
        sa.CheckConstraint(
            "status IN ('confirmed','pending','not_a_network')", name="ck_cpo_alias_status"
        ),
        sa.CheckConstraint("status <> 'confirmed' OR cpo_id IS NOT NULL", name="ck_cpo_alias_cpo"),
    )
    op.create_index("ix_cpo_aliases_cpo", "cpo_aliases", ["cpo_id"])

    op.create_table(
        "stations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cpo_id", sa.Integer(), sa.ForeignKey("cpos.id")),
        sa.Column("operator_raw", sa.String(128)),
        sa.Column("name", sa.Text()),
        sa.Column("address", sa.Text()),
        sa.Column("town", sa.String(128)),
        sa.Column("postcode", sa.String(12)),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column(
            "geom",
            Geometry("POINT", srid=4326, spatial_index=False),
            sa.Computed("ST_SetSRID(ST_MakePoint(lng, lat), 4326)", persisted=True),
            nullable=True,
        ),
        sa.Column("lgd_district_code", sa.Integer(), sa.ForeignKey("districts.lgd_district_code")),
        sa.Column("lgd_state_code", sa.Integer(), sa.ForeignKey("states.lgd_state_code")),
        sa.Column("access", sa.String(16)),
        sa.Column("is_operational", sa.Boolean()),
        sa.Column("merged_into_id", sa.Integer(), sa.ForeignKey("stations.id")),
        sa.Column("legacy_competitor_station_id", sa.Integer(), unique=True),
        _created(),
        _updated(),
        sa.CheckConstraint(
            "merged_into_id IS NULL OR merged_into_id <> id", name="ck_station_merge"
        ),
        sa.CheckConstraint(
            "lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180", name="ck_station_xy"
        ),
    )
    op.create_index("ix_stations_geom", "stations", ["geom"], postgresql_using="gist")
    op.create_index("ix_stations_district", "stations", ["lgd_district_code"])
    op.create_index("ix_stations_cpo", "stations", ["cpo_id"])

    op.create_table(
        "chargers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("evse_uid", sa.String(64)),
        sa.Column("label", sa.String(128)),
        sa.Column("current_type", sa.String(2)),
        sa.Column("rated_power_kw", sa.Float()),
        sa.Column("make", sa.String(64)),
        sa.Column("model", sa.String(64)),
        sa.Column("commissioned_on", sa.Date()),
        sa.Column("inferred", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        _created(),
        _updated(),
        sa.CheckConstraint("current_type IN ('AC','DC')", name="ck_charger_current"),
        sa.CheckConstraint("rated_power_kw IS NULL OR rated_power_kw > 0", name="ck_charger_power"),
        sa.CheckConstraint("status IN ('active','retired','unknown')", name="ck_charger_status"),
        sa.UniqueConstraint("station_id", "evse_uid", name="uq_charger_evse"),
    )
    op.create_index("ix_chargers_station", "chargers", ["station_id"])

    op.create_table(
        "connectors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("charger_id", sa.Integer(), sa.ForeignKey("chargers.id"), nullable=False),
        sa.Column("standard", sa.String(48)),
        sa.Column("format", sa.String(8)),
        sa.Column("max_power_kw", sa.Float()),
        _created(),
        _updated(),
        sa.CheckConstraint("format IN ('socket','cable')", name="ck_connector_format"),
        sa.CheckConstraint("max_power_kw IS NULL OR max_power_kw > 0", name="ck_connector_power"),
    )
    op.create_index("ix_connectors_charger", "connectors", ["charger_id"])

    op.create_table(
        "scraped_records",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        _seen("scraped_at"),
        sa.Column("url", sa.Text()),
        sa.Column("payload", JSONB(none_as_null=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("source_id", "source_key", "content_hash", name="uq_scraped_payload"),
    )
    op.create_index("ix_scraped_records_run", "scraped_records", ["run_id"])
    op.create_index(
        "ix_scraped_records_key", "scraped_records", ["source_id", "source_key", "scraped_at"]
    )

    op.create_table(
        "station_listings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("source_name", sa.Text()),
        sa.Column("source_operator", sa.String(128)),
        _seen("first_seen_at"),
        _seen("last_seen_at"),
        sa.Column("last_scrape_id", sa.BigInteger(), sa.ForeignKey("scraped_records.id")),
        _created(),
        _updated(),
        sa.UniqueConstraint("source_id", "source_key", name="uq_station_listing"),
    )
    op.create_index("ix_station_listings_station", "station_listings", ["station_id"])

    op.create_table(
        "charger_listings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("charger_id", sa.Integer(), sa.ForeignKey("chargers.id"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=False),
        _seen("first_seen_at"),
        _seen("last_seen_at"),
        sa.Column("last_scrape_id", sa.BigInteger(), sa.ForeignKey("scraped_records.id")),
        _created(),
        _updated(),
        sa.UniqueConstraint("source_id", "source_key", name="uq_charger_listing"),
    )
    op.create_index("ix_charger_listings_charger", "charger_listings", ["charger_id"])

    # updated_at is maintained by the database, so a raw UPDATE, a script and the
    # ORM all leave the same trail.
    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in MUTABLE:
        op.execute(
            f"CREATE TRIGGER {table}_set_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )

    op.execute(
        """
        CREATE RULE scraped_records_no_update AS
            ON UPDATE TO scraped_records DO INSTEAD NOTHING;
        CREATE RULE scraped_records_no_delete AS
            ON DELETE TO scraped_records DO INSTEAD NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO data_sources (key, name, kind) VALUES
            ('open_charge_map', 'Open Charge Map', 'open_data'),
            ('goec', 'GO EC', 'emsp_app'),
            ('zeon', 'Zeon Charging', 'cpo_direct'),
            ('pulse', 'Pulse Energy', 'emsp_app'),
            ('tata_power', 'Tata Power EZ Charge', 'cpo_direct')
        """
    )

    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (15, 'Charging network: cpos, stations, chargers, connectors, listings, scraped_records')
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM schema_version WHERE version = 15")
    # Dropping the table drops its rules and triggers with it.
    for table in (
        "charger_listings",
        "station_listings",
        "scraped_records",
        "connectors",
        "chargers",
        "stations",
        "cpo_aliases",
        "cpos",
        "data_sources",
    ):
        op.drop_table(table)
    op.execute("DROP FUNCTION set_updated_at()")
