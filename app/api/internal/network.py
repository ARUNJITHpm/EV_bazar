"""Charging network - the console read side over stations, chargers, connectors.

Read-only views over the tables from migration 0015: how big the network is, a
paged and filterable station list, and one station's chargers, connectors and
the source listings behind it. Filters are state and district (LGD codes),
operator and free text.

Guarded: mounted on the ``guarded`` router in ``api/internal/__init__.py``.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.charging import (
    Charger,
    Connector,
    Cpo,
    DataSource,
    Station,
    StationListing,
)
from app.models.reference import District, State

router = APIRouter(prefix="/network")

#: At or above this a connector is "DC fast" - the same line competitors.py draws.
_DC_FAST_KW = 50.0


class Counts(BaseModel):
    stations: int
    chargers: int
    connectors: int
    operators: int
    #: Stations no CPO has been attributed to yet.
    unattributed: int
    #: Stations no district polygon contained.
    unplaced: int
    #: Connectors with no rated power - not usable in a forecast.
    connectors_without_power: int


class StateFacet(BaseModel):
    lgd_state_code: int
    state: str
    stations: int


class DistrictFacet(BaseModel):
    lgd_district_code: int
    lgd_state_code: int
    district: str
    stations: int


class OperatorFacet(BaseModel):
    id: int
    name: str
    stations: int


class FacetsOut(BaseModel):
    checked_at: dt.datetime
    counts: Counts
    states: list[StateFacet]
    #: Districts that hold at least one station; the UI narrows by state.
    districts: list[DistrictFacet]
    operators: list[OperatorFacet]


@router.get("/facets", response_model=FacetsOut)
def facets(session: Session = Depends(get_session)) -> FacetsOut:
    live = Station.merged_into_id.is_(None)
    stations = session.scalar(select(func.count()).select_from(Station).where(live)) or 0
    chargers = session.scalar(select(func.count()).select_from(Charger)) or 0
    connectors = session.scalar(select(func.count()).select_from(Connector)) or 0
    no_power = (
        session.scalar(
            select(func.count()).select_from(Connector).where(Connector.max_power_kw.is_(None))
        )
        or 0
    )
    unattributed = (
        session.scalar(
            select(func.count()).select_from(Station).where(live, Station.cpo_id.is_(None))
        )
        or 0
    )
    unplaced = (
        session.scalar(
            select(func.count())
            .select_from(Station)
            .where(live, Station.lgd_district_code.is_(None))
        )
        or 0
    )
    operators = session.scalar(select(func.count()).select_from(Cpo)) or 0

    n = func.count(Station.id)
    states = [
        StateFacet(lgd_state_code=int(code), state=str(name), stations=int(c))
        for code, name, c in session.execute(
            select(State.lgd_state_code, State.name, n)
            .join(Station, Station.lgd_state_code == State.lgd_state_code)
            .where(live)
            .group_by(State.lgd_state_code, State.name)
            .order_by(State.name)
        ).all()
    ]
    districts = [
        DistrictFacet(
            lgd_district_code=int(code),
            lgd_state_code=int(scode),
            district=str(name),
            stations=int(c),
        )
        for code, scode, name, c in session.execute(
            select(District.lgd_district_code, District.lgd_state_code, District.name, n)
            .join(Station, Station.lgd_district_code == District.lgd_district_code)
            .where(live)
            .group_by(District.lgd_district_code, District.lgd_state_code, District.name)
            .order_by(District.name)
        ).all()
    ]
    ops = [
        OperatorFacet(id=int(cid), name=str(name), stations=int(c))
        for cid, name, c in session.execute(
            select(Cpo.id, Cpo.name, n)
            .join(Station, Station.cpo_id == Cpo.id)
            .where(live)
            .group_by(Cpo.id, Cpo.name)
            .order_by(n.desc(), Cpo.name)
        ).all()
    ]
    return FacetsOut(
        checked_at=dt.datetime.now(dt.UTC),
        counts=Counts(
            stations=int(stations),
            chargers=int(chargers),
            connectors=int(connectors),
            operators=int(operators),
            unattributed=int(unattributed),
            unplaced=int(unplaced),
            connectors_without_power=int(no_power),
        ),
        states=states,
        districts=districts,
        operators=ops,
    )


class StationRow(BaseModel):
    id: int
    name: str | None
    operator: str | None
    #: True when the operator is a canonical CPO, False when it is the raw text.
    operator_confirmed: bool
    town: str | None
    district: str | None
    state: str | None
    lat: float
    lng: float
    chargers: int
    connectors: int
    max_power_kw: float | None
    dc_fast: bool
    listings: int
    updated_at: dt.datetime


class StationsOut(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    stations: list[StationRow]


SortKey = Literal["name", "connectors", "power", "updated"]


def _filtered(
    stmt: Select,  # type: ignore[type-arg]
    state: int | None,
    district: int | None,
    operator: int | None,
    q: str,
) -> Select:  # type: ignore[type-arg]
    stmt = stmt.where(Station.merged_into_id.is_(None))
    if state is not None:
        stmt = stmt.where(Station.lgd_state_code == state)
    if district is not None:
        stmt = stmt.where(Station.lgd_district_code == district)
    if operator is not None:
        # 0 asks for the stations nobody has been attributed to.
        stmt = stmt.where(Station.cpo_id.is_(None) if operator == 0 else Station.cpo_id == operator)
    term = q.strip()
    if term:
        like = f"%{term}%"
        stmt = stmt.where(
            or_(
                Station.name.ilike(like),
                Station.town.ilike(like),
                Station.address.ilike(like),
                Station.operator_raw.ilike(like),
                Cpo.name.ilike(like),
            )
        )
    return stmt


@router.get("/stations", response_model=StationsOut)
def list_stations(
    state: int | None = Query(None, description="LGD state code"),
    district: int | None = Query(None, description="LGD district code"),
    operator: int | None = Query(None, ge=0, description="CPO id; 0 = unattributed"),
    q: str = Query("", max_length=80),
    sort: SortKey = "name",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> StationsOut:
    base = select(Station.id).outerjoin(Cpo, Cpo.id == Station.cpo_id)
    total = (
        session.scalar(
            select(func.count()).select_from(
                _filtered(base, state, district, operator, q).subquery()
            )
        )
        or 0
    )

    chargers = (
        select(
            Charger.station_id.label("sid"),
            func.count(func.distinct(Charger.id)).label("chargers"),
            func.count(Connector.id).label("connectors"),
            func.max(Connector.max_power_kw).label("kw"),
        )
        .join(Connector, Connector.charger_id == Charger.id, isouter=True)
        .where(Charger.status != "retired")
        .group_by(Charger.station_id)
        .subquery()
    )
    listings = (
        select(StationListing.station_id.label("sid"), func.count().label("n"))
        .group_by(StationListing.station_id)
        .subquery()
    )
    order = {
        "name": (Station.name.asc().nulls_last(), Station.id),
        "connectors": (func.coalesce(chargers.c.connectors, 0).desc(), Station.id),
        "power": (chargers.c.kw.desc().nulls_last(), Station.id),
        "updated": (Station.updated_at.desc(), Station.id),
    }[sort]
    stmt = (
        select(
            Station,
            Cpo.name,
            District.name,
            State.name,
            func.coalesce(chargers.c.chargers, 0),
            func.coalesce(chargers.c.connectors, 0),
            chargers.c.kw,
            func.coalesce(listings.c.n, 0),
        )
        .outerjoin(Cpo, Cpo.id == Station.cpo_id)
        .outerjoin(District, District.lgd_district_code == Station.lgd_district_code)
        .outerjoin(State, State.lgd_state_code == Station.lgd_state_code)
        .outerjoin(chargers, chargers.c.sid == Station.id)
        .outerjoin(listings, listings.c.sid == Station.id)
    )
    stmt = _filtered(stmt, state, district, operator, q)
    rows = session.execute(
        stmt.order_by(*order).limit(page_size).offset((page - 1) * page_size)
    ).all()
    return StationsOut(
        total=int(total),
        page=page,
        page_size=page_size,
        pages=max(1, -(-int(total) // page_size)),
        stations=[
            StationRow(
                id=st.id,
                name=st.name,
                operator=cpo_name or st.operator_raw,
                operator_confirmed=cpo_name is not None,
                town=st.town,
                district=district_name,
                state=state_name,
                lat=st.lat,
                lng=st.lng,
                chargers=int(n_chargers),
                connectors=int(n_connectors),
                max_power_kw=None if kw is None else float(kw),
                dc_fast=kw is not None and float(kw) >= _DC_FAST_KW,
                listings=int(n_listings),
                updated_at=st.updated_at,
            )
            for (
                st,
                cpo_name,
                district_name,
                state_name,
                n_chargers,
                n_connectors,
                kw,
                n_listings,
            ) in rows
        ],
    )


class ConnectorOut(BaseModel):
    id: int
    standard: str | None
    format: str | None
    max_power_kw: float | None


class ChargerOut(BaseModel):
    id: int
    label: str | None
    current_type: str | None
    rated_power_kw: float | None
    #: True when we guessed the point from the connector list rather than saw it.
    inferred: bool
    status: str
    connectors: list[ConnectorOut]


class ListingOut(BaseModel):
    source: str
    source_key: str
    source_name: str | None
    source_operator: str | None
    first_seen_at: dt.datetime
    last_seen_at: dt.datetime


class StationDetail(BaseModel):
    station: StationRow
    address: str | None
    postcode: str | None
    access: str | None
    is_operational: bool | None
    created_at: dt.datetime
    chargers: list[ChargerOut]
    listings: list[ListingOut]


@router.get("/stations/{station_id}", response_model=StationDetail)
def station_detail(station_id: int, session: Session = Depends(get_session)) -> StationDetail:
    st = session.get(Station, station_id)
    if st is None:
        raise HTTPException(404, "Unknown station.")
    cpo_name = session.scalar(select(Cpo.name).where(Cpo.id == st.cpo_id))
    district_name = session.scalar(
        select(District.name).where(District.lgd_district_code == st.lgd_district_code)
    )
    state_name = session.scalar(select(State.name).where(State.lgd_state_code == st.lgd_state_code))

    conns: dict[int, list[ConnectorOut]] = {}
    for c in session.scalars(
        select(Connector)
        .join(Charger, Charger.id == Connector.charger_id)
        .where(Charger.station_id == st.id)
        .order_by(Connector.id)
    ):
        conns.setdefault(c.charger_id, []).append(
            ConnectorOut(id=c.id, standard=c.standard, format=c.format, max_power_kw=c.max_power_kw)
        )
    chargers = [
        ChargerOut(
            id=ch.id,
            label=ch.label,
            current_type=ch.current_type,
            rated_power_kw=ch.rated_power_kw,
            inferred=ch.inferred,
            status=ch.status,
            connectors=conns.get(ch.id, []),
        )
        for ch in session.scalars(
            select(Charger).where(Charger.station_id == st.id).order_by(Charger.id)
        )
    ]
    listings = [
        ListingOut(
            source=key,
            source_key=sl.source_key,
            source_name=sl.source_name,
            source_operator=sl.source_operator,
            first_seen_at=sl.first_seen_at,
            last_seen_at=sl.last_seen_at,
        )
        for sl, key in session.execute(
            select(StationListing, DataSource.key)
            .join(DataSource, DataSource.id == StationListing.source_id)
            .where(StationListing.station_id == st.id)
            .order_by(DataSource.key)
        ).all()
    ]
    powers = [c.max_power_kw for cs in conns.values() for c in cs if c.max_power_kw is not None]
    top = max(powers) if powers else None
    return StationDetail(
        station=StationRow(
            id=st.id,
            name=st.name,
            operator=cpo_name or st.operator_raw,
            operator_confirmed=cpo_name is not None,
            town=st.town,
            district=district_name,
            state=state_name,
            lat=st.lat,
            lng=st.lng,
            chargers=len(chargers),
            connectors=sum(len(cs) for cs in conns.values()),
            max_power_kw=top,
            dc_fast=top is not None and top >= _DC_FAST_KW,
            listings=len(listings),
            updated_at=st.updated_at,
        ),
        address=st.address,
        postcode=st.postcode,
        access=st.access,
        is_operational=st.is_operational,
        created_at=st.created_at,
        chargers=chargers,
        listings=listings,
    )
