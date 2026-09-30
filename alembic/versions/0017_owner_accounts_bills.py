"""Owner accounts, registered stations, bills and forecasts.

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-30

The initial stage's only station data source is what owners upload. An account
is a phone number (stored in full, shown to the browser masked). Stations and
connectors are what the owner registered. A bill keeps the confirmed fields and
points at the original image, which is kept permanently. A forecast is stored
as it was made, so the track record never compares against a recalculation.

Everything except ``owner_accounts`` (``last_login_at`` moves) is insert-only in
the database, not by convention (AGENTS.md rule 3): a corrected bill is a new
row and the latest one for a month is the one in force.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INSERT_ONLY = (
    "owner_stations",
    "owner_connectors",
    "owner_bill_images",
    "owner_bills",
    "owner_forecasts",
)


def upgrade() -> None:
    now = sa.text("now()")
    op.create_table(
        "owner_accounts",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("phone", sa.String(16), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "owner_stations",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("owner_accounts.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("address", sa.Text()),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("state_name", sa.String(64)),
        sa.Column("district_name", sa.String(64)),
        sa.Column("went_live", sa.Date(), nullable=False),
        sa.Column("meter_type", sa.String(16), nullable=False),
        sa.Column("consent_aggregate", sa.Boolean(), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.CheckConstraint("consent_aggregate", name="ck_owner_station_consent"),
        sa.CheckConstraint(
            "meter_type IN ('separate','shared','unsure')", name="ck_owner_station_meter"
        ),
    )
    op.create_index("ix_owner_stations_account", "owner_stations", ["account_id"])
    op.create_table(
        "owner_connectors",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("owner_stations.id"), nullable=False),
        sa.Column("standard", sa.String(24), nullable=False),
        sa.Column("power_kw", sa.Float(), nullable=False),
        sa.CheckConstraint("power_kw > 0", name="ck_owner_connector_power"),
    )
    op.create_index("ix_owner_connectors_station", "owner_connectors", ["station_id"])
    op.create_table(
        "owner_bill_images",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("owner_accounts.id"), nullable=False),
        sa.Column("content_type", sa.String(48), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_table(
        "owner_bills",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("owner_stations.id"), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("kwh", sa.Float(), nullable=False),
        sa.Column("history", JSONB(none_as_null=True)),
        sa.Column("tariff_category", sa.String(80)),
        sa.Column("contract_demand", sa.Float()),
        sa.Column("recorded_demand", sa.Float()),
        sa.Column("demand_unit", sa.String(3)),
        sa.Column("power_factor", sa.Float()),
        sa.Column("pf_effect", sa.String(9)),
        sa.Column("pf_amount_paise", sa.BigInteger()),
        sa.Column("tod_peak_kwh", sa.Float()),
        sa.Column("tod_normal_kwh", sa.Float()),
        sa.Column("tod_offpeak_kwh", sa.Float()),
        sa.Column("board", sa.String(64)),
        sa.Column("consumer_last4", sa.String(4)),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("image_id", sa.Uuid(), sa.ForeignKey("owner_bill_images.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.CheckConstraint("kwh > 0", name="ck_owner_bill_kwh"),
        sa.CheckConstraint("source IN ('image','typed')", name="ck_owner_bill_source"),
    )
    op.create_index("ix_owner_bills_station_period", "owner_bills", ["station_id", "period"])
    op.create_table(
        "owner_forecasts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("owner_stations.id"), nullable=False),
        sa.Column("made_from", sa.Date(), nullable=False),
        sa.Column("target_month", sa.Date(), nullable=False),
        sa.Column("p10_kwh", sa.Float(), nullable=False),
        sa.Column("p50_kwh", sa.Float(), nullable=False),
        sa.Column("p90_kwh", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("readings_used", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index(
        "ix_owner_forecasts_station_target", "owner_forecasts", ["station_id", "target_month"]
    )
    for table in _INSERT_ONLY:
        op.execute(
            f"CREATE RULE {table}_no_update AS ON UPDATE TO {table} DO INSTEAD NOTHING;"
            f"CREATE RULE {table}_no_delete AS ON DELETE TO {table} DO INSTEAD NOTHING;"
        )
    op.execute(
        """
        INSERT INTO schema_version (version, note)
        VALUES (17, 'Owner accounts (phone), registered stations, bills, forecasts')
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM schema_version WHERE version = 17")
    for table in ("owner_forecasts", "owner_bills", "owner_bill_images", "owner_connectors"):
        op.drop_table(table)
    op.drop_table("owner_stations")
    op.drop_table("owner_accounts")
