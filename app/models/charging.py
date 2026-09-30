"""The charging network: who runs it, where it is, what is on it, and where we saw it.

    cpos ──< cpo_aliases            a company, and every spelling of its name
    data_sources                    the apps and feeds we read
    stations ──< chargers ──< connectors     the physical hierarchy
    stations ──< station_listings   each source's own id for a station
    chargers ──< charger_listings   each source's own id for a charger
    scraped_records                 what a source returned, verbatim

**Three levels, one meaning each.** A *station* is a place (a forecourt, a mall
basement). A *charger* is one box on it (an EVSE - it can serve one vehicle at a
time). A *connector* is one plug on that box. OCPI's Location / EVSE /
Connector, so a roaming id maps onto it without translation.

**Chargers are sometimes inferred.** Most scraped sources say "2 x CCS2 at 60 kW"
and never name the boxes. For those the loader writes one charger per connector
group with ``inferred = true``; real data replaces it later. The flag is what
lets a count of *chargers* be told apart from a count of *guesses*.

**One charger, many apps.** A station or charger can be listed in several apps
(OCPI roaming), each under its own id. That lives in the ``*_listings`` tables,
unique on ``(source, source_key)``, so the same physical thing seen from two
apps is one row with two listings - not two rows.

**Mutable current state, not a ledger.** Stations, chargers, connectors and CPOs
are the latest belief about the world, so they carry ``created_at`` and
``updated_at`` (kept honest by a database trigger, not only by the ORM). A
dedupe never deletes: it sets ``stations.merged_into_id``. What each source said,
and when, is ``scraped_records`` - insert-only in the database, like the poller's
raw pages.

**Not here:** live availability and occupancy. That is the poller's
(``charger_status_events`` / ``connector_state``), keyed today by the source's
own strings; a listing is how those strings reach a ``connectors`` row.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column

from app.models.base import Base

SRID = 4326
JsonColumn = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


def _created() -> MappedColumn[dt.datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _updated() -> MappedColumn[dt.datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DataSource(Base):
    """An app or feed we read. Not the same thing as a CPO: Pulse lists chargers
    that other companies run, so "listed in Pulse" must never read as "run by
    Pulse"."""

    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: Stable machine key: "goec", "zeon", "pulse", "tata_power", "open_charge_map".
    key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _updated()

    __table_args__ = (
        CheckConstraint(
            "kind IN ('emsp_app','aggregator','cpo_direct','open_data')",
            name="ck_data_source_kind",
        ),
    )


class Cpo(Base):
    """A charge point operator, canonical. Growing this table is a human step:
    there is no fuzzy matching, because nothing reviews an operator name and a
    near-miss would silently merge two networks (see ``domain/cpo/identity.py``)."""

    __tablename__ = "cpos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="cpo")
    website: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _updated()

    __table_args__ = (
        CheckConstraint("kind IN ('cpo','utility','oem','other')", name="ck_cpo_kind"),
    )


class CpoAlias(Base):
    """One spelling of an operator's name and what a human decided it means.

    ``confirmed``      this spelling IS ``cpo_id``
    ``pending``        seen, nobody has decided; reports say "unknown", never zero
    ``not_a_network``  a real arrangement that is not an operator ("Self-operate")
    """

    __tablename__ = "cpo_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: Lower-cased, punctuation-stripped - the lookup key. Unique.
    alias_norm: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    #: The spelling exactly as the source wrote it.
    alias_raw: Mapped[str] = mapped_column(String(128), nullable=False)
    cpo_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cpos.id"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    first_seen_source_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("data_sources.id"))
    confirmed_by: Mapped[str | None] = mapped_column(String(64))
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _updated()

    __table_args__ = (
        CheckConstraint(
            "status IN ('confirmed','pending','not_a_network')", name="ck_cpo_alias_status"
        ),
        CheckConstraint("status <> 'confirmed' OR cpo_id IS NOT NULL", name="ck_cpo_alias_cpo"),
        Index("ix_cpo_aliases_cpo", "cpo_id"),
    )


class Station(Base):
    """A place with chargers on it."""

    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: NULL until the operator name is resolved. ``operator_raw`` keeps what the
    #: source said, so an unresolved station still says who it thinks runs it.
    cpo_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cpos.id"))
    operator_raw: Mapped[str | None] = mapped_column(String(128))

    name: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    town: Mapped[str | None] = mapped_column(String(128))
    postcode: Mapped[str | None] = mapped_column(String(12))

    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[object | None] = mapped_column(
        Geometry("POINT", srid=SRID, spatial_index=False),
        Computed(f"ST_SetSRID(ST_MakePoint(lng, lat), {SRID})", persisted=True),
        nullable=True,
    )
    #: Resolved once on ingest (PLAN 1.4). NULL = the point could not be placed.
    lgd_district_code: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("districts.lgd_district_code")
    )
    lgd_state_code: Mapped[int | None] = mapped_column(Integer, ForeignKey("states.lgd_state_code"))

    #: public | private | membership | restricted
    access: Mapped[str | None] = mapped_column(String(16))
    #: A data-quality flag from the source, NOT occupancy.
    is_operational: Mapped[bool | None] = mapped_column(Boolean)

    #: Set when a dedupe decides this is the same place as another row. Rows are
    #: never deleted; queries that want one row per place filter on NULL.
    merged_into_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("stations.id"))

    #: The ``competitor_stations.id`` this row was backfilled from. A plain
    #: integer, not a foreign key, so that table can be retired. It is how an old
    #: ``owner_submissions.competitor_station_id`` finds its station, and what
    #: makes the backfill safe to run twice.
    legacy_competitor_station_id: Mapped[int | None] = mapped_column(Integer, unique=True)

    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _updated()

    __table_args__ = (
        CheckConstraint("merged_into_id IS NULL OR merged_into_id <> id", name="ck_station_merge"),
        CheckConstraint(
            "lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180", name="ck_station_xy"
        ),
        Index("ix_stations_geom", "geom", postgresql_using="gist"),
        Index("ix_stations_district", "lgd_district_code"),
        Index("ix_stations_cpo", "cpo_id"),
    )


class Charger(Base):
    """One box on a station: an EVSE, serving one vehicle at a time."""

    __tablename__ = "chargers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(Integer, ForeignKey("stations.id"), nullable=False)
    #: The operator's own id for the box (OCPI ``evse_uid``), when there is one.
    evse_uid: Mapped[str | None] = mapped_column(String(64))
    label: Mapped[str | None] = mapped_column(String(128))
    #: AC | DC
    current_type: Mapped[str | None] = mapped_column(String(2))
    #: What the box can deliver in total. Connectors on one box usually share it.
    rated_power_kw: Mapped[float | None] = mapped_column(Float)
    make: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(64))
    commissioned_on: Mapped[dt.date | None] = mapped_column(Date)
    #: True when the loader made this row up from a count ("2 x CCS2") because
    #: the source never named the box. See the module docstring.
    inferred: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _updated()

    __table_args__ = (
        CheckConstraint("current_type IN ('AC','DC')", name="ck_charger_current"),
        CheckConstraint("rated_power_kw IS NULL OR rated_power_kw > 0", name="ck_charger_power"),
        CheckConstraint("status IN ('active','retired','unknown')", name="ck_charger_status"),
        UniqueConstraint("station_id", "evse_uid", name="uq_charger_evse"),
        Index("ix_chargers_station", "station_id"),
    )


class Connector(Base):
    """One plug on a charger."""

    __tablename__ = "connectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    charger_id: Mapped[int] = mapped_column(Integer, ForeignKey("chargers.id"), nullable=False)
    #: The connector standard as the source names it ("CCS2", "Type 2 (Tethered
    #: Connector)", "15A"). NULL = the source did not say.
    standard: Mapped[str | None] = mapped_column(String(48))
    #: socket | cable
    format: Mapped[str | None] = mapped_column(String(8))
    max_power_kw: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _updated()

    __table_args__ = (
        CheckConstraint("format IN ('socket','cable')", name="ck_connector_format"),
        CheckConstraint("max_power_kw IS NULL OR max_power_kw > 0", name="ck_connector_power"),
        Index("ix_connectors_charger", "charger_id"),
    )


class ScrapedRecord(Base):
    """What a source returned for one station or charger, verbatim.

    Insert-only in the database (rules, not convention). A record is stored once
    per distinct payload: a re-scrape that returns the same bytes is not a new
    row - ``station_listings.last_seen_at`` records that we saw it again. Parsing
    is a later step and never edits this table; it writes stations, chargers,
    connectors and listings, and points ``last_scrape_id`` back here.

    Writers: the update/delete rules make Postgres refuse ``INSERT ... ON
    CONFLICT`` on this table, so skip a payload already stored by checking for
    ``(source_id, source_key, content_hash)`` first - a plain INSERT of a
    duplicate fails on ``uq_scraped_payload``.
    """

    __tablename__ = "scraped_records"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_sources.id"), nullable=False)
    #: The source's own id for the thing described (may be longer than 64 chars).
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    #: One scrape pass; every record of a pass shares it.
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(), nullable=False)
    scraped_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    url: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[Any] = mapped_column(JsonColumn, nullable=False)
    #: sha256 of the canonical payload; makes an unchanged re-scrape a no-op.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("source_id", "source_key", "content_hash", name="uq_scraped_payload"),
        Index("ix_scraped_records_run", "run_id"),
        Index("ix_scraped_records_key", "source_id", "source_key", "scraped_at"),
    )


class StationListing(Base):
    """A source's own id for a station: the same place, seen from one app."""

    __tablename__ = "station_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(Integer, ForeignKey("stations.id"), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_sources.id"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    #: How that app names it, and whom it says runs it - before any resolution.
    source_name: Mapped[str | None] = mapped_column(Text)
    source_operator: Mapped[str | None] = mapped_column(String(128))
    first_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    #: The newest scraped record this listing was built from.
    last_scrape_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("scraped_records.id"))
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _updated()

    __table_args__ = (
        UniqueConstraint("source_id", "source_key", name="uq_station_listing"),
        Index("ix_station_listings_station", "station_id"),
    )


class ChargerListing(Base):
    """A source's own id for a charger - only where the source really has one."""

    __tablename__ = "charger_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    charger_id: Mapped[int] = mapped_column(Integer, ForeignKey("chargers.id"), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_sources.id"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    first_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_scrape_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("scraped_records.id"))
    created_at: Mapped[dt.datetime] = _created()
    updated_at: Mapped[dt.datetime] = _updated()

    __table_args__ = (
        UniqueConstraint("source_id", "source_key", name="uq_charger_listing"),
        Index("ix_charger_listings_charger", "charger_id"),
    )
