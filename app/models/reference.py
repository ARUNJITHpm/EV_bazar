"""Reference geography - PART 1.2.

Downloaded once, rarely changed, and underneath almost every number the
product will ever produce. A site resolves to a district; the district decides
the tariff; the tariff decides the verdict. Get this layer wrong and every
downstream figure is wrong in a way that no test downstream can detect.

Four tables:

  states, districts   LGD-coded administrative polygons. ``lgd_district_code``
                      is the join key the whole system agrees on (OVERVIEW).
  pincodes            PIN polygons, used to cross-check a geocode against the
                      district it landed in (PLAN 1.4).
  district_name_crosswalk
                      shapefile/VAHAN/tariff-sheet spellings -> LGD code.
                      ⚠️ Rows are NOT trusted until a human sets
                      ``verified_by``. A fuzzy match is a suggestion.

  reference_layers    provenance and vintage per layer: where it came from,
                      its checksum, when it was fetched. Feeds the "data
                      vintage per layer" row in the console (PLAN C.5), and
                      answers "which polygons produced last March's report".
"""

from __future__ import annotations

import datetime as dt

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

#: WGS84 everywhere. Every source is reprojected to it on the way in, because
#: a mixed-SRID database produces silently wrong distances rather than errors.
SRID = 4326


def _geometry() -> Geometry:
    """A polygon column whose index we declare ourselves.

    ``spatial_index=False`` matters: GeoAlchemy2 otherwise emits its own
    ``idx_<table>_geom`` alongside the ``ix_<table>_geom`` declared below, so
    every table would carry two identical GIST indexes and ``alembic check``
    would report permanent drift against the migration.
    """
    return Geometry("MULTIPOLYGON", srid=SRID, spatial_index=False)


class ReferenceLayer(Base):
    """One downloaded layer, with the provenance to reproduce it.

    Rule 1 (version everything) applied to reference data: a report generated
    last March used a particular set of district boundaries, and "the current
    ones" is not an answer when a district was split in between.
    """

    __tablename__ = "reference_layers"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    #: Of the downloaded file. Two runs producing different data must be
    #: distinguishable without eyeballing row counts.
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    licence: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    downloaded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    loaded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    note: Mapped[str | None] = mapped_column(Text)


class State(Base):
    __tablename__ = "states"

    lgd_state_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    #: Census 2011 state code. Kept because half of India's open data - VAHAN,
    #: SHRUG, most shapefiles - is keyed on census codes, not LGD ones.
    census_2011_code: Mapped[str | None] = mapped_column(String(8))

    geom: Mapped[object] = mapped_column(_geometry(), nullable=False)

    __table_args__ = (Index("ix_states_geom", "geom", postgresql_using="gist"),)


class District(Base):
    """~780 of these. Load them all, not just the Tier 1 ones (PLAN 1.2).

    A district we have not loaded is a lead we cannot even waitlist, and the
    waitlist is the expansion roadmap (OVERVIEW section 4).
    """

    __tablename__ = "districts"

    lgd_district_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    lgd_state_code: Mapped[int] = mapped_column(
        Integer, ForeignKey("states.lgd_state_code"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    state_name: Mapped[str] = mapped_column(String(128), nullable=False)

    census_2011_code: Mapped[str | None] = mapped_column(String(8))
    #: Which census/update vintage this boundary came from. India's district
    #: count has moved a lot since 2011 (Telangana 2014, Ladakh 2019, repeated
    #: UP/AP/Assam splits) and a boundary's age is part of reading it.
    boundary_vintage: Mapped[str | None] = mapped_column(String(16))

    geom: Mapped[object] = mapped_column(_geometry(), nullable=False)

    __table_args__ = (
        # The point-in-polygon lookup in PLAN 1.4 lives or dies on this index.
        Index("ix_districts_geom", "geom", postgresql_using="gist"),
        Index("ix_districts_state", "lgd_state_code"),
    )


class Pincode(Base):
    """PIN polygons.

    Not authoritative geography - India Post defines delivery rounds, not
    areas - but good enough to catch a geocode that landed in the wrong
    district, which is the job PLAN 1.4 gives it. A PIN can legitimately
    straddle a district line, so there is no unique constraint on the code.
    """

    __tablename__ = "pincodes"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    office_name: Mapped[str | None] = mapped_column(String(255))
    #: India Post's own hierarchy, stored under its own names rather than
    #: mapped onto state/district. A postal circle mostly coincides with a
    #: state and sometimes does not, and quietly calling it ``state_name``
    #: would invite exactly the wrong join.
    postal_circle: Mapped[str | None] = mapped_column(String(128))
    postal_region: Mapped[str | None] = mapped_column(String(128))
    postal_division: Mapped[str | None] = mapped_column(String(128))

    geom: Mapped[object] = mapped_column(_geometry(), nullable=False)

    __table_args__ = (
        Index("ix_pincodes_geom", "geom", postgresql_using="gist"),
        Index("ix_pincodes_pincode", "pincode"),
    )


class DistrictNameCrosswalk(Base):
    """Foreign spellings -> LGD code. PLAN 1.2's hand-verified table.

    ⚠️ ``verified_by`` NULL means nobody has checked this row. A fuzzy match
    is a suggestion, and an unverified suggestion misattributing a district
    is exactly the silent failure PLAN 1.2 warns about - so the column exists
    to be queried, not decorated. Consumers must filter on it.
    """

    __tablename__ = "district_name_crosswalk"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    #: The name as the foreign source spells it, verbatim.
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_state: Mapped[str] = mapped_column(String(128), nullable=False)
    #: Which dataset this spelling came from - census shapefile, VAHAN, a
    #: tariff order. The same string can mean different districts in
    #: different datasets, so provenance is part of the key.
    source_dataset: Mapped[str] = mapped_column(String(64), nullable=False)

    lgd_district_code: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("districts.lgd_district_code")
    )

    #: exact | alias | fuzzy | manual | unresolved
    match_method: Mapped[str] = mapped_column(String(16), nullable=False)
    #: 0-100 similarity for fuzzy matches; 100 for exact/alias.
    match_score: Mapped[int | None] = mapped_column(Integer)

    #: Who checked it. NULL = nobody. Never fill this in from code.
    verified_by: Mapped[str | None] = mapped_column(String(64))
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "source_dataset", "source_state", "source_name", name="uq_crosswalk_source"
        ),
        Index("ix_crosswalk_unverified", "match_method", "verified_by"),
    )
