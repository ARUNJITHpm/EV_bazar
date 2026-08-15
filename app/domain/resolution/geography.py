"""Point -> district. PART 1.4.

The single most load-bearing lookup in the product: the district decides the
tariff, the tariff decides the margin, the margin decides the verdict. A pin
attributed to the wrong district produces a report that is wrong in every
number and looks completely normal.

So the rules here are about **saying how sure we are**, and refusing when the
honest answer is "ask someone":

    contained      the point is inside exactly one district. Normal.
    nearest        inside none - a coastline sliver, a boundary gap in the
                   source polygons - resolved to the nearest within 5 km.
    pin_override   the supplied PIN says somewhere else, and PLAN 1.4 says
                   trust the PIN. Confidence drops.
    overlapping    inside TWO districts. Refused: the source polygons are
                   wrong and papering over it hides a data bug that would
                   silently misattribute everything in the overlap.
    rejected       nothing within 5 km. Not in India, or not on land.

The module is split so that every *decision* is a pure function of query
results (``classify``) and the database work is a thin shell (``resolve``).
The decisions are where the subtle mistakes live, and they are tested without
a database.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

#: Metres. Beyond this the point is not plausibly in any district and we say
#: so rather than attributing it to whatever happens to be closest.
DEFAULT_MAX_FALLBACK_M = 5000
#: Metres. Another district this close means two tariff regimes are in play.
DEFAULT_AMBIGUOUS_M = 500


class Method(enum.StrEnum):
    CONTAINED = "contained"
    NEAREST = "nearest"
    PIN_OVERRIDE = "pin_override"
    OVERLAPPING = "overlapping"
    REJECTED = "rejected"


class Confidence(enum.StrEnum):
    """A label, deliberately not a number.

    A 0.83 would imply a calibration nobody has done. Three levels can be
    explained to a customer and mapped by the report to a warning or a
    footnote; a fabricated decimal cannot.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class DistrictHit:
    lgd_district_code: int
    lgd_state_code: int
    name: str
    state_name: str
    #: 0.0 when the point is inside the polygon.
    distance_m: float = 0.0


@dataclass(frozen=True)
class Resolution:
    """The answer, plus everything needed to explain it in a report."""

    method: Method
    confidence: Confidence
    district: DistrictHit | None

    #: Another district within the ambiguity radius: two tariff regimes.
    boundary_ambiguous: bool = False
    neighbour: DistrictHit | None = None

    #: PIN polygons covering the point, and the PIN the caller supplied.
    pincode_at_point: tuple[str, ...] = ()
    expected_pincode: str | None = None
    pin_conflict: bool = False

    #: On a ``pin_override``, the district the coordinates themselves landed in.
    #: Without it a caller can see which district won but not which one lost,
    #: and any explanation of the decision has to guess at half of it.
    overridden_district: DistrictHit | None = None

    #: Human-readable, in the order they were decided. These go straight into
    #: the report's assumption ledger (PLAN 5) - an unexplained downgrade is
    #: as useless as no downgrade.
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def resolved(self) -> bool:
        return self.district is not None

    @property
    def lgd_district_code(self) -> int | None:
        return self.district.lgd_district_code if self.district else None


def classify(
    *,
    containing: Sequence[DistrictHit],
    nearest: DistrictHit | None,
    neighbours: Sequence[DistrictHit],
    pincode_at_point: Sequence[str],
    expected_pincode: str | None,
    pin_district: DistrictHit | None,
    max_fallback_m: int = DEFAULT_MAX_FALLBACK_M,
    ambiguous_m: int = DEFAULT_AMBIGUOUS_M,
) -> Resolution:
    """Turn query results into an answer. Pure - no database, no clock.

    ``neighbours`` excludes the resolved district and is already filtered to
    within ``ambiguous_m``. ``pin_district`` is the district covering most of
    the *supplied* PIN's area, and is only consulted when the PIN disagrees.
    """
    reasons: list[str] = []
    pins = tuple(dict.fromkeys(pincode_at_point))

    # --- the source data is wrong: refuse rather than pick -----------------
    if len(containing) > 1:
        names = ", ".join(f"{d.name} ({d.lgd_district_code})" for d in containing)
        return Resolution(
            method=Method.OVERLAPPING,
            confidence=Confidence.LOW,
            district=None,
            pincode_at_point=pins,
            expected_pincode=expected_pincode,
            reasons=(
                f"point falls inside {len(containing)} districts: {names}. The source "
                "polygons overlap - fix them rather than choosing one, because whichever "
                "is chosen would be wrong for half the sites in the overlap.",
            ),
        )

    # --- normal, and the fallback ------------------------------------------
    if containing:
        district = containing[0]
        method = Method.CONTAINED
    elif nearest is None:
        return Resolution(
            method=Method.REJECTED,
            confidence=Confidence.LOW,
            district=None,
            pincode_at_point=pins,
            expected_pincode=expected_pincode,
            reasons=("no district polygons are loaded",),
        )
    elif nearest.distance_m > max_fallback_m:
        return Resolution(
            method=Method.REJECTED,
            confidence=Confidence.LOW,
            district=None,
            pincode_at_point=pins,
            expected_pincode=expected_pincode,
            reasons=(
                f"nearest district is {nearest.name} at {nearest.distance_m / 1000:.1f} km, "
                f"beyond the {max_fallback_m / 1000:.0f} km limit. The point is not in India, "
                "or the geocode is wrong.",
            ),
        )
    else:
        district = nearest
        method = Method.NEAREST
        reasons.append(
            f"inside no district polygon; resolved to the nearest, {nearest.name}, "
            f"{nearest.distance_m:.0f} m away"
        )

    # --- near a district line: two tariff regimes --------------------------
    neighbour = neighbours[0] if neighbours else None
    boundary_ambiguous = neighbour is not None
    if neighbour is not None:
        across_a_state_line = neighbour.lgd_state_code != district.lgd_state_code
        reasons.append(
            f"within {neighbour.distance_m:.0f} m of {neighbour.name}"
            + (
                f" in {neighbour.state_name} - a different state, so a different tariff "
                "regime entirely"
                if across_a_state_line
                else " - close enough to a district line to be worth stating"
            )
        )

    # --- the PIN disagrees: PLAN 1.4 says trust the PIN --------------------
    pin_conflict = bool(expected_pincode) and expected_pincode not in pins
    if pin_conflict:
        if pin_district is not None and pin_district.lgd_district_code != (
            district.lgd_district_code
        ):
            reasons.append(
                f"supplied PIN {expected_pincode} sits mostly in {pin_district.name}, not "
                f"{district.name} where the coordinates landed. Trusting the PIN (PLAN 1.4): "
                "a PIN comes from the customer, the coordinates come from a geocoder."
            )
            return Resolution(
                method=Method.PIN_OVERRIDE,
                confidence=Confidence.LOW,
                district=pin_district,
                boundary_ambiguous=boundary_ambiguous,
                neighbour=neighbour,
                pincode_at_point=pins,
                expected_pincode=expected_pincode,
                pin_conflict=True,
                overridden_district=district,
                reasons=tuple(reasons),
            )
        # The PIN is unknown to us, or agrees on the district by another
        # route. Worth recording, not worth overriding.
        reasons.append(
            f"supplied PIN {expected_pincode} does not cover the coordinates"
            + (
                ""
                if pin_district is None
                else f", but points at the same district ({pin_district.name})"
            )
        )

    confidence = _confidence(method, district, boundary_ambiguous, pin_conflict, ambiguous_m)
    return Resolution(
        method=method,
        confidence=confidence,
        district=district,
        boundary_ambiguous=boundary_ambiguous,
        neighbour=neighbour,
        pincode_at_point=pins,
        expected_pincode=expected_pincode,
        pin_conflict=pin_conflict,
        reasons=tuple(reasons),
    )


def _confidence(
    method: Method,
    district: DistrictHit,
    boundary_ambiguous: bool,
    pin_conflict: bool,
    ambiguous_m: int,
) -> Confidence:
    """One downgrade per doubt, and never back up again."""
    if method is Method.NEAREST:
        # A few metres outside a polygon is a rounding artefact on a coastline.
        # Kilometres outside is a geocode nobody should build a report on.
        return Confidence.MEDIUM if district.distance_m <= ambiguous_m else Confidence.LOW
    if pin_conflict:
        return Confidence.LOW
    if boundary_ambiguous:
        return Confidence.MEDIUM
    return Confidence.HIGH


# ---------------------------------------------------------------------------
# The database shell. Thin on purpose - all judgement is above.
# ---------------------------------------------------------------------------

#: Degrees of latitude per metre, near enough. Used only to build a bounding
#: box that the GIST index can use before the exact geography distance runs;
#: it is padded generously because longitude degrees shrink toward the poles
#: and an under-sized box would silently miss a neighbour.
_DEG_PER_M = 1.0 / 111_320.0

_POINT = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)"

_CONTAINING = text(f"""
    SELECT lgd_district_code, lgd_state_code, name, state_name
    FROM districts
    WHERE ST_Contains(geom, {_POINT})
    ORDER BY lgd_district_code
""")

# LIMIT 5 then re-sort by true distance: the `<->` operator orders by planar
# distance in degrees, which near a boundary can disagree with the geodesic
# answer. Cheap insurance.
_NEAREST = text(f"""
    SELECT lgd_district_code, lgd_state_code, name, state_name,
           ST_Distance(geom::geography, {_POINT}::geography) AS distance_m
    FROM districts
    ORDER BY geom <-> {_POINT}
    LIMIT 5
""")

_NEIGHBOURS = text(f"""
    SELECT lgd_district_code, lgd_state_code, name, state_name,
           ST_Distance(geom::geography, {_POINT}::geography) AS distance_m
    FROM districts
    WHERE lgd_district_code <> :code
      -- Index-friendly bounding box first, exact geodesic distance second.
      AND geom && ST_Expand({_POINT}, :box_deg)
      AND ST_DWithin(geom::geography, {_POINT}::geography, :radius_m)
    ORDER BY distance_m
    LIMIT 3
""")

_PINS_AT_POINT = text(f"""
    SELECT DISTINCT pincode
    FROM pincodes
    WHERE ST_Contains(geom, {_POINT})
    LIMIT 5
""")

# A PIN can be delivered by several offices and straddle a district line, so
# the polygons are unioned and the district holding the largest share wins.
_PIN_DISTRICT = text("""
    WITH pin AS (SELECT ST_Union(geom) AS geom FROM pincodes WHERE pincode = :pincode)
    SELECT d.lgd_district_code, d.lgd_state_code, d.name, d.state_name,
           ST_Area(ST_Intersection(d.geom, pin.geom)::geography) AS overlap_m2
    FROM districts d, pin
    WHERE pin.geom IS NOT NULL AND ST_Intersects(d.geom, pin.geom)
    ORDER BY overlap_m2 DESC
    LIMIT 1
""")


def _hit(row: Row[Any], *, with_distance: bool = False) -> DistrictHit:
    """Every district query selects code, state code, name, state name, [distance]."""
    return DistrictHit(
        lgd_district_code=int(row[0]),
        lgd_state_code=int(row[1]),
        name=str(row[2]),
        state_name=str(row[3]),
        distance_m=float(row[4]) if with_distance else 0.0,
    )


def resolve(
    session: Session,
    lat: float,
    lng: float,
    *,
    expected_pincode: str | None = None,
    max_fallback_m: int = DEFAULT_MAX_FALLBACK_M,
    ambiguous_m: int = DEFAULT_AMBIGUOUS_M,
) -> Resolution:
    """Resolve one coordinate to a district. Runs the queries, then classifies."""
    point = {"lat": lat, "lng": lng}

    containing = [_hit(r) for r in session.execute(_CONTAINING, point).all()]

    nearest: DistrictHit | None = None
    if not containing:
        candidates = [_hit(r, with_distance=True) for r in session.execute(_NEAREST, point).all()]
        nearest = min(candidates, key=lambda d: d.distance_m) if candidates else None

    resolved_code = containing[0].lgd_district_code if containing else None
    if resolved_code is None and nearest is not None:
        resolved_code = nearest.lgd_district_code

    neighbours: list[DistrictHit] = []
    if resolved_code is not None:
        neighbours = [
            _hit(r, with_distance=True)
            for r in session.execute(
                _NEIGHBOURS,
                {
                    **point,
                    "code": resolved_code,
                    "radius_m": ambiguous_m,
                    # Padded: one degree of longitude is shorter than one of
                    # latitude everywhere but the equator.
                    "box_deg": ambiguous_m * _DEG_PER_M * 2.0,
                },
            ).all()
        ]

    pins = [str(r[0]) for r in session.execute(_PINS_AT_POINT, point).all()]

    pin_district: DistrictHit | None = None
    if expected_pincode and expected_pincode not in pins:
        row = session.execute(_PIN_DISTRICT, {"pincode": expected_pincode}).first()
        if row is not None:
            pin_district = _hit(row, with_distance=False)

    return classify(
        containing=containing,
        nearest=nearest,
        neighbours=neighbours,
        pincode_at_point=pins,
        expected_pincode=expected_pincode,
        pin_district=pin_district,
        max_fallback_m=max_fallback_m,
        ambiguous_m=ambiguous_m,
    )


def find_overlapping_districts(session: Session) -> list[tuple[int, str, int, str, float]]:
    """Districts whose polygons overlap - the data bug ``classify`` refuses on.

    Run after every reference reload. An overlap is not a lookup problem to be
    worked around; it means two districts both claim the same ground, and every
    site in that ground is attributed by coin toss.

    Shared *edges* are normal and expected, so this measures the area of the
    intersection and ignores slivers below a square metre.
    """
    rows = session.execute(
        text("""
            SELECT a.lgd_district_code, a.name, b.lgd_district_code, b.name,
                   ST_Area(ST_Intersection(a.geom, b.geom)::geography) AS overlap_m2
            FROM districts a
            JOIN districts b
              ON a.lgd_district_code < b.lgd_district_code
             AND a.geom && b.geom
             AND ST_Overlaps(a.geom, b.geom)
            WHERE ST_Area(ST_Intersection(a.geom, b.geom)::geography) > 1.0
            ORDER BY overlap_m2 DESC
        """)
    ).all()
    return [(int(r[0]), str(r[1]), int(r[2]), str(r[3]), float(r[4])) for r in rows]
