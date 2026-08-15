"""Lookup - one point, every step, and the table each answer came from. PART C.

Three read-only panels whose job is to make the system *legible*:

* ``/lookup/point``    - resolve a coordinate and show the working. Which
                         question was asked, which table answered it, and which
                         answer was decisive. This is the panel to open when a
                         site is attributed to a district somebody disputes.
* ``/lookup/tables``   - every table, its row count, and what it is **for**, in
                         one screen. An empty table is not a bug here; it is a
                         Part that has not shipped, and it says which one.
* ``/lookup/coverage`` - what we actually know per state, and the tier that
                         honestly follows from it.

⚠️ ``/lookup/coverage`` is a **live view, not PLAN 1.6's gate.** 1.6 persists a
``data_coverage`` row per district and stamps ``sites.data_tier`` from it. This
computes the same judgement from what is loaded right now, so the tier can be
read before 1.6 exists - and so that when 1.6 lands, the two can be compared.

Guarded: mounted on the ``guarded`` router in ``api/internal/__init__.py``.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.resolution.geography import (
    DEFAULT_AMBIGUOUS_M,
    DEFAULT_MAX_FALLBACK_M,
    Method,
    Resolution,
    resolve,
)
from app.models.reference import District, Pincode, ReferenceLayer, State

router = APIRouter()


# ---------------------------------------------------------------------------
# /lookup/point - the working, not just the answer
# ---------------------------------------------------------------------------


class Step(BaseModel):
    """One question the resolver asked, and where it went for the answer."""

    n: int
    question: str
    #: The table consulted, with its size - or "nothing" when the step is a
    #: decision rather than a lookup.
    looked_in: str
    #: The mechanism, named plainly enough to be checked by hand.
    using: str
    answer: str
    #: True for the step that actually determined the outcome.
    decisive: bool = False


class FieldSource(BaseModel):
    """Where one field on the answer physically came from."""

    field: str
    value: str
    #: ``table.column``, or the module that computed it.
    source: str
    note: str


class NeighbourOut(BaseModel):
    name: str
    state_name: str
    lgd_district_code: int
    distance_m: float


class LayerOut(BaseModel):
    """Provenance of the map data itself - PLAN C.5's data-vintage row."""

    name: str
    feature_count: int
    licence: str
    source_url: str
    downloaded_at: dt.datetime


class PointOut(BaseModel):
    lat: float
    lng: float
    supplied_pincode: str | None

    resolved: bool
    district: str | None
    lgd_district_code: int | None
    state_name: str | None
    lgd_state_code: int | None
    #: 0.0 when the point is inside the polygon; > 0 means nearest-fallback.
    distance_m: float

    method: str
    confidence: str
    boundary_ambiguous: bool
    neighbour: NeighbourOut | None
    pincode_at_point: list[str]
    pin_conflict: bool
    #: On a pin_override, the district the coordinates landed in before the
    #: supplied PIN moved the answer somewhere else.
    overridden_district: str | None
    reasons: list[str]

    steps: list[Step]
    fields: list[FieldSource]
    layers: list[LayerOut]


def _fmt(n: int) -> str:
    return f"{n:,}"


def build_steps(res: Resolution, *, districts: int, pincodes: int) -> list[Step]:
    """Narrate the resolution. Pure - a function of the answer, nothing else.

    Deliberately reconstructed from ``Resolution`` rather than instrumented
    into ``resolve()``: a trace that can drift from the decision is worse than
    no trace, and ``Resolution`` already carries every fact the decision used.
    """
    steps: list[Step] = []
    fell_through = res.method in (Method.NEAREST, Method.REJECTED)

    # 1 - containment. Careful: after a pin_override `res.district` is the PIN's
    # district, not the one the coordinates landed in, so this reads the
    # overridden district instead - reporting the winner here would describe a
    # query that never returned it.
    landed_in = res.overridden_district if res.method is Method.PIN_OVERRIDE else res.district
    if res.method is Method.OVERLAPPING:
        answer = "inside MORE THAN ONE district - refused, because the source polygons overlap"
    elif fell_through:
        answer = "inside no district polygon"
    elif landed_in is not None:
        answer = f"yes - {landed_in.name} ({landed_in.lgd_district_code})"
    else:
        answer = "no district"
    steps.append(
        Step(
            n=1,
            question="Is the point inside exactly one district polygon?",
            looked_in=f"districts - {_fmt(districts)} polygons",
            using="ST_Contains(geom, point)",
            answer=answer,
            decisive=res.method in (Method.CONTAINED, Method.OVERLAPPING),
        )
    )

    # 2 - nearest, only asked when containment found nothing
    if fell_through:
        if res.method is Method.REJECTED:
            near = res.reasons[0] if res.reasons else "nothing close enough - rejected"
        elif res.district is not None:
            near = f"{res.district.name} at {res.district.distance_m:.0f} m"
        else:
            near = "nothing"
        steps.append(
            Step(
                n=len(steps) + 1,
                question=(
                    f"Then which district is nearest, within {DEFAULT_MAX_FALLBACK_M // 1000} km?"
                ),
                looked_in=f"districts - {_fmt(districts)} polygons",
                using="ORDER BY geom <-> point LIMIT 5, then exact geodesic distance",
                answer=near,
                decisive=True,
            )
        )

    # 3 - a second district close enough to matter
    steps.append(
        Step(
            n=len(steps) + 1,
            question=f"Is another district within {DEFAULT_AMBIGUOUS_M} m?",
            looked_in="districts",
            using="ST_DWithin(geom::geography, point, 500)",
            answer=(
                f"{res.neighbour.name} ({res.neighbour.state_name}) at "
                f"{res.neighbour.distance_m:.0f} m - two tariff regimes in play"
                if res.neighbour is not None
                else "no - the point is comfortably inside one district"
            ),
        )
    )

    # 4 - PIN polygons at the point
    steps.append(
        Step(
            n=len(steps) + 1,
            question="Which PIN polygons cover the point?",
            looked_in=f"pincodes - {_fmt(pincodes)} polygons",
            using="ST_Contains(geom, point)",
            answer=", ".join(res.pincode_at_point) if res.pincode_at_point else "none",
        )
    )

    # 5 - the customer's PIN, only when they gave one
    if res.expected_pincode:
        if res.method is Method.PIN_OVERRIDE:
            pin_answer = (
                f"no - PIN {res.expected_pincode} sits mostly elsewhere, so the PIN wins "
                "and the district was changed"
            )
        elif res.pin_conflict:
            pin_answer = (
                f"no - PIN {res.expected_pincode} does not cover the point, but it does not "
                "point at a different district either. Recorded, not overridden."
            )
        else:
            pin_answer = f"yes - PIN {res.expected_pincode} covers the point"
        steps.append(
            Step(
                n=len(steps) + 1,
                question="Does the PIN the customer supplied agree?",
                looked_in="pincodes",
                using="ST_Union of that PIN's polygons, then largest overlapping district",
                answer=pin_answer,
                decisive=res.method is Method.PIN_OVERRIDE,
            )
        )

    # 6 - the judgement itself
    steps.append(
        Step(
            n=len(steps) + 1,
            question="So how sure are we?",
            looked_in="nothing - this step reads no table",
            using="classify() in app/domain/resolution/geography.py, a pure function",
            answer=f"method {res.method}, confidence {res.confidence}",
            decisive=True,
        )
    )
    return steps


def build_fields(res: Resolution) -> list[FieldSource]:
    """Field-by-field provenance: the table and column behind each value."""
    out: list[FieldSource] = []
    if res.district is not None:
        d = res.district
        out += [
            FieldSource(
                field="district",
                value=d.name,
                source="districts.name",
                note="the polygon's own name, as published in the boundary layer",
            ),
            FieldSource(
                field="lgd_district_code",
                value=str(d.lgd_district_code),
                source="districts.lgd_district_code",
                note=(
                    "carried natively on the polygon - never matched by name, which is "
                    "why 'Vizag' vs 'Visakhapatanam' cannot break it"
                ),
            ),
            FieldSource(
                field="state",
                value=d.state_name,
                source="districts.state_name",
                note="denormalised onto the district row so a state needs no second query",
            ),
            FieldSource(
                field="lgd_state_code",
                value=str(d.lgd_state_code),
                source="districts.lgd_state_code -> states.lgd_state_code",
                note="the join key for state-level data: tariffs, EV policy, VAHAN",
            ),
        ]
    if res.pincode_at_point:
        out.append(
            FieldSource(
                field="pincode_at_point",
                value=", ".join(res.pincode_at_point),
                source="pincodes.pincode",
                note="India Post delivery polygons - a cross-check, not authoritative geography",
            )
        )
    out += [
        FieldSource(
            field="method",
            value=str(res.method),
            source="computed - geography.classify()",
            note="not stored anywhere; recomputed from the query results every time",
        ),
        FieldSource(
            field="confidence",
            value=str(res.confidence),
            source="computed - geography.classify()",
            note="a label, never a number: one downgrade per doubt, and it never recovers",
        ),
    ]
    return out


@router.get("/lookup/point", response_model=PointOut)
def lookup_point(
    session: Session = Depends(get_session),
    lat: float = Query(ge=6.0, le=37.5, description="India's bounding box, roughly"),
    lng: float = Query(ge=68.0, le=97.5),
    pincode: str | None = Query(default=None, min_length=6, max_length=6),
) -> PointOut:
    """Resolve one coordinate and show the working.

    The bounds are not decoration: a transposed lat/lng is the commonest way a
    hand-entered point goes wrong, and (76.2, 9.9) is a coordinate in Kazakhstan
    that would otherwise be rejected 5 km later with no explanation of why.
    """
    res = resolve(session, lat, lng, expected_pincode=pincode)

    districts = session.execute(select(func.count()).select_from(District)).scalar_one()
    pincodes = session.execute(select(func.count()).select_from(Pincode)).scalar_one()

    layers = session.execute(select(ReferenceLayer).order_by(ReferenceLayer.name)).scalars().all()

    return PointOut(
        lat=lat,
        lng=lng,
        supplied_pincode=pincode,
        resolved=res.resolved,
        district=res.district.name if res.district else None,
        lgd_district_code=res.lgd_district_code,
        state_name=res.district.state_name if res.district else None,
        lgd_state_code=res.district.lgd_state_code if res.district else None,
        distance_m=res.district.distance_m if res.district else 0.0,
        method=str(res.method),
        confidence=str(res.confidence),
        boundary_ambiguous=res.boundary_ambiguous,
        neighbour=(
            NeighbourOut(
                name=res.neighbour.name,
                state_name=res.neighbour.state_name,
                lgd_district_code=res.neighbour.lgd_district_code,
                distance_m=res.neighbour.distance_m,
            )
            if res.neighbour
            else None
        ),
        pincode_at_point=list(res.pincode_at_point),
        pin_conflict=res.pin_conflict,
        overridden_district=(
            res.overridden_district.name if res.overridden_district is not None else None
        ),
        reasons=list(res.reasons),
        steps=build_steps(res, districts=int(districts), pincodes=int(pincodes)),
        fields=build_fields(res),
        layers=[
            LayerOut(
                name=layer.name,
                feature_count=layer.feature_count,
                licence=layer.licence,
                source_url=layer.source_url,
                downloaded_at=layer.downloaded_at,
            )
            for layer in layers
        ],
    )


# ---------------------------------------------------------------------------
# /lookup/tables - what is in the database, in English
# ---------------------------------------------------------------------------


class TableOut(BaseModel):
    table: str
    group: str
    rows: int
    what: str
    filled_by: str
    #: Why it is empty, when it is. Empty is usually a Part, not a fault.
    empty_means: str | None = None


class TablesOut(BaseModel):
    checked_at: dt.datetime
    tables: list[TableOut]
    #: Tables that exist in the database but have no entry above. Should always
    #: be empty - it is how "every table is on this screen" stays true when
    #: somebody adds one and forgets to describe it.
    undocumented: list[str]
    #: Owned by the PostGIS extension rather than by us.
    extension_tables: list[str]


#: table, group, plain-English purpose, what fills it, what empty means.
#: Names are ours, never user input - they are interpolated into SQL below.
_TABLES: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "states",
        "Reference geography",
        "State and UT outlines, with the government's official LGD state code.",
        "PLAN 1.2 - scripts/load_reference.py",
        "",
    ),
    (
        "districts",
        "Reference geography",
        "District outlines. THE join key of the whole product: a pin resolves to a "
        "district, the district picks the tariff, the tariff decides the verdict.",
        "PLAN 1.2 - scripts/load_reference.py",
        "",
    ),
    (
        "pincodes",
        "Reference geography",
        "India Post PIN delivery areas as polygons. Used to catch a geocode that "
        "landed in the wrong district.",
        "PLAN 1.2 - scripts/load_reference.py",
        "",
    ),
    (
        "district_name_crosswalk",
        "Reference geography",
        "Other people's spellings of a district ('Vizag') mapped to our LGD code. "
        "A row is NOT trusted until a human signs it (verified_by).",
        "PLAN 1.2 - scripts/build_crosswalk.py",
        "",
    ),
    (
        "reference_layers",
        "Reference geography",
        "Where each map layer came from: URL, checksum, licence, date. Lets an old "
        "report say which boundaries produced it.",
        "PLAN 1.2 - scripts/fetch_reference.py",
        "",
    ),
    (
        "geocode_cache",
        "Resolution",
        "Every address ever geocoded, and what it resolved to. Misses are cached "
        "too, so a bad address is never paid for twice.",
        "PLAN 1.3 - the cascade, on every lookup",
        "No address has been geocoded yet.",
    ),
    (
        "geocode_manual_queue",
        "Resolution",
        "Addresses the cascade refused to guess at. A human places the pin once and "
        "it is never asked again.",
        "PLAN 1.3 L6 - automatically, on a refusal",
        "Nothing has been refused yet, because nothing has been geocoded.",
    ),
    (
        "sites",
        "Resolution",
        "One row per distinct place a customer asked about, with its district "
        "verdict and a counter of how many times it was requested.",
        "PLAN 1.5 - scripts/resolve_site.py, and the report flow later",
        "No customer request has been recorded yet.",
    ),
    (
        "competitor_stations",
        "Competitors",
        "Every charging station we know about that is not a customer's site: who "
        "runs it, where, how powerful, how public. The denominator for 'how much "
        "competition is near this site'. A cache, upserted by source - NOT the "
        "poller's occupancy log.",
        "PLAN 2.3 - scripts/fetch_competitors.py (Open Charge Map)",
        "No competitor fetch has run yet.",
    ),
    (
        "vahan_ev_registrations",
        "Demand",
        "How many EVs are registered in each district, split by vehicle class and "
        "fuel, read from the government's VAHAN dashboard. A time series (one snapshot "
        "per scrape, never overwritten) so the 12-month GROWTH is computable - which "
        "PLAN 4.1 weights above the absolute count.",
        "PLAN 4.1 - scripts/scrape_vahan.py then scripts/ingest_vahan.py",
        "No VAHAN scrape ingested yet - every state's vehicle-count flag is false on "
        "the Data panel until one is.",
    ),
    (
        "poll_runs",
        "Poller",
        "One row per sweep per source: when it ran, whether it worked, what it saw. "
        "This is the ledger the dead-man's switch reads.",
        "PLAN 0.1 - workers/poller.py, every cycle",
        "The poller has never run against an authorised source (FINDINGS B3).",
    ),
    (
        "poll_raw_payloads",
        "Poller",
        "The lossless archive: exactly what each app returned, untouched. The one "
        "table that cannot be rebuilt if lost. Partitioned by month, like the change log.",
        "PLAN 0.1 - workers/poller.py, before anything is interpreted",
        "Nothing has been polled yet.",
    ),
    (
        "charger_status_events",
        "Poller",
        "The change log: one row when a connector's status changes, not one per "
        "observation. Zero rows on a quiet network is healthy. Split into one child "
        "table per month, so an old month can be detached without touching the rest.",
        "PLAN 0.1 - derived from the archive above",
        "Nothing has been polled yet.",
    ),
    (
        "connector_state",
        "Poller",
        "Latest known status per connector. A cache, updated in place - it is the "
        "only table here that is allowed to forget.",
        "PLAN 0.1 - workers/poller.py",
        "Nothing has been polled yet.",
    ),
    (
        "api_usage_events",
        "Money",
        "Every metered external call, with what it cost in paise. Append-only. "
        "Written BEFORE the response is used, including errors and cache hits.",
        "PLAN C.1 - meter(), around every paid provider",
        "No paid call has been made yet.",
    ),
    (
        "provider_price_cards",
        "Money",
        "What each provider charges, with dates. Never overwritten - a new price "
        "is a new row, so an old cost still recomputes at the old price.",
        "PLAN C.1 - scripts/seed_price_cards.py",
        "",
    ),
    (
        "electricity_tariffs",
        "Tariffs & subsidies",
        "What each DISCOM charges, per state and consumer category, with dates. "
        "Never overwritten - a new SERC order is a new row, so an old report still "
        "recomputes under the old tariff. Typed by hand from the order PDF.",
        "PLAN 3.1 - human data entry (0.2), one state per evening",
        "No tariff typed in yet - this is what keeps every state at Tier 3.",
    ),
    (
        "subsidy_rules",
        "Tariffs & subsidies",
        "Capital subsidies and incentives (PM E-DRIVE, state EV policies), same "
        "effective-dating. Subsidies change amortised capex enough to flip a "
        "Build/Don't verdict, which is why they are a table and not a footnote.",
        "PLAN 3.1 - human data entry",
        "No schemes recorded yet.",
    ),
    (
        "schema_version",
        "Housekeeping",
        "Which schema revision the data was written under, so an old report can say "
        "what shape the database had when it was generated.",
        "Alembic migrations",
        "",
    ),
    (
        "alembic_version",
        "Housekeeping",
        "The single row Alembic itself keeps, naming the migration this database has "
        "been brought up to.",
        "Alembic, on every `alembic upgrade`",
        "",
    ),
)

#: Owned by the PostGIS extension, not by us. Listed in the panel so that
#: "every table" is literally true and nobody goes hunting for the missing ones.
_POSTGIS_TABLES = ("spatial_ref_sys", "geometry_columns", "geography_columns")


@router.get("/lookup/tables", response_model=TablesOut)
def lookup_tables(session: Session = Depends(get_session)) -> TablesOut:
    """Row counts for every table that carries meaning, with what it is for.

    One round trip rather than fifteen: the counts are unioned into a single
    statement, which matters when the database is a hop away.
    """
    union = " UNION ALL ".join(
        f"SELECT '{name}' AS t, count(*) AS n FROM {name}" for name, *_ in _TABLES
    )
    counts = {str(row[0]): int(row[1]) for row in session.execute(text(union)).all()}

    # Anything real that is not described above. Partition children are excluded
    # by asking only for tables with no parent - a monthly child is not a table
    # a reader needs to know about, it is an implementation detail of its parent.
    present = {
        str(row[0])
        for row in session.execute(
            text("""
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                LEFT JOIN pg_inherits i ON i.inhrelid = c.oid
                WHERE n.nspname = 'public'
                  AND c.relkind IN ('r', 'p')
                  AND i.inhparent IS NULL
            """)
        ).all()
    }
    described = {name for name, *_ in _TABLES}

    return TablesOut(
        checked_at=dt.datetime.now(dt.UTC),
        undocumented=sorted(present - described - set(_POSTGIS_TABLES)),
        extension_tables=sorted(present & set(_POSTGIS_TABLES)),
        tables=[
            TableOut(
                table=name,
                group=group,
                rows=counts.get(name, 0),
                what=what,
                filled_by=filled_by,
                empty_means=(empty or None) if counts.get(name, 0) == 0 else None,
            )
            for name, group, what, filled_by, empty in _TABLES
        ],
    )


# ---------------------------------------------------------------------------
# /lookup/coverage - the tier that honestly follows from what we know
# ---------------------------------------------------------------------------


class StateCoverageOut(BaseModel):
    lgd_state_code: int
    state: str
    #: PLAN Part 1's first markets - Kerala and Tamil Nadu. All human effort
    #: (tariffs, addresses, polling) goes here first, so these two are the
    #: states expected to reach Tier 1 first. Sorted to the top of the table.
    focus: bool
    districts: int
    has_tariff_data: bool
    has_competitor_poll: bool
    has_vahan_data: bool
    has_osm_road_quality: bool
    tier: int = Field(description="1 = full report · 2 = tariff audit only · 3 = waitlist")
    why: str


class CoverageOut(BaseModel):
    checked_at: dt.datetime
    rule: str
    note: str
    states: list[StateCoverageOut]


_TIER_RULE = (
    "A tier measures how much WE know about a state - it is our data coverage, not "
    "the size or importance of its cities. Tier 1 = we hold tariffs AND competitor "
    "occupancy AND vehicle counts, so a full report is honest. Tier 2 = tariffs "
    "alone - enough for a breakeven number and a tariff audit, the first sellable "
    "product. Tier 3 = we know too little; log the pin, waitlist the customer, and "
    "count the district as demand. A state moves UP by us loading data for it, "
    "starting with the focus states."
)

#: LGD state codes of PLAN Part 1's first markets: Kerala (32), Tamil Nadu (33).
FOCUS_STATES = frozenset({32, 33})


def tier_for(*, tariff: bool, poll: bool, vahan: bool, osm: bool) -> tuple[int, str]:
    """The gate, as a pure function. PLAN 1.6 will persist this per district."""
    if tariff and poll and vahan:
        return 1, "tariffs, occupancy and vehicle counts are all present"
    if tariff:
        missing = [
            label
            for label, present in (
                ("competitor occupancy", poll),
                ("VAHAN vehicle counts", vahan),
                ("road quality", osm),
            )
            if not present
        ]
        return 2, "tariffs are loaded, so a breakeven number is honest; still missing " + ", ".join(
            missing
        )
    return 3, "no tariff data for this state, so no number here would be trustworthy"


@router.get("/lookup/coverage", response_model=CoverageOut)
def lookup_coverage(session: Session = Depends(get_session)) -> CoverageOut:
    """Per state: what evidence exists, and the tier that follows from it.

    ⚠️ Every evidence flag below is currently derived from a table that either
    does not exist yet or is empty, so the honest answer is Tier 3 everywhere.
    That is the correct answer and it is stated rather than worked around - the
    alternative, hardcoding "Kerala and Tamil Nadu are Tier 1", would make the
    console agree with the plan instead of with the database.
    """
    rows = session.execute(
        select(State.lgd_state_code, State.name, func.count(District.lgd_district_code))
        .join(District, District.lgd_state_code == State.lgd_state_code, isouter=True)
        .group_by(State.lgd_state_code, State.name)
        .order_by(State.name)
    ).all()

    # Tariffs are per state, read from the 3.1 table: a state has tariff data
    # when a currently-effective row exists for it. VAHAN (4.1) is now live per
    # state from its table; OSM roads (2.1) still has no table, so that one stays
    # structurally false until its Part lands - and then the tier moves on its own.
    tariff_states = {
        int(row[0])
        for row in session.execute(
            text(
                "SELECT DISTINCT lgd_state_code FROM electricity_tariffs "
                "WHERE effective_to IS NULL OR effective_to > CURRENT_DATE"
            )
        ).all()
    }
    vahan_states = {
        int(row[0])
        for row in session.execute(
            text(
                "SELECT DISTINCT lgd_state_code FROM vahan_ev_registrations "
                "WHERE lgd_state_code IS NOT NULL"
            )
        ).all()
    }
    has_osm = False
    polled = session.execute(text("SELECT count(*) FROM poll_runs")).scalar_one()
    has_poll = bool(polled)

    states: list[StateCoverageOut] = []
    for code, name, district_count in rows:
        has_tariff = int(code) in tariff_states
        has_vahan = int(code) in vahan_states
        tier, why = tier_for(tariff=has_tariff, poll=has_poll, vahan=has_vahan, osm=has_osm)
        states.append(
            StateCoverageOut(
                lgd_state_code=int(code),
                state=str(name),
                focus=int(code) in FOCUS_STATES,
                districts=int(district_count),
                has_tariff_data=has_tariff,
                has_competitor_poll=has_poll,
                has_vahan_data=has_vahan,
                has_osm_road_quality=has_osm,
                tier=tier,
                why=why,
            )
        )

    return CoverageOut(
        checked_at=dt.datetime.now(dt.UTC),
        rule=_TIER_RULE,
        note=(
            "Tariff flags are live per state from the electricity_tariffs table - type "
            "in a state's SERC order and it turns Tier 2 here on its own. VAHAN (4.1) is "
            "now live per state from vahan_ev_registrations - scrape a state and its "
            "vehicle-count flag turns true. OSM roads (2.1) has no table yet, so that "
            "flag is false everywhere by construction. Competitor occupancy is read from "
            "poll_runs and is national, not per state, until a poll can be attributed to "
            "a district (needs FINDINGS B3). This view is computed live; PLAN 1.6 will "
            "persist the same judgement per district."
        ),
        # Focus states first, then alphabetical - the two rows a reader acts on
        # should not be buried under A-for-Andaman.
        states=sorted(states, key=lambda s: (not s.focus, s.state)),
    )
