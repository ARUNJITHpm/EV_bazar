"""PART 1.4 - point-in-polygon decision rules.

Every test here drives ``classify``, the pure half. The PostGIS half is a
handful of queries verified against the live database by
``scripts/resolve_point.py``; the interesting failures are not in the SQL, they
are in what we decide when the SQL comes back ambiguous.

The rule these all serve: a district attributed wrongly produces a report that
is wrong in every number and looks entirely normal. So the tests are mostly
about downgrading and refusing.
"""

from __future__ import annotations

from app.domain.resolution.geography import (
    Confidence,
    DistrictHit,
    Method,
    classify,
)

ERNAKULAM = DistrictHit(555, 32, "Ernakulam", "KERALA")
THRISSUR = DistrictHit(566, 32, "Thrissur", "KERALA", distance_m=310.0)
COIMBATORE = DistrictHit(569, 33, "Coimbatore", "TAMIL NADU", distance_m=180.0)


def resolve(**over: object):
    """classify() with the boring arguments filled in."""
    kwargs: dict = {
        "containing": [ERNAKULAM],
        "nearest": None,
        "neighbours": [],
        "pincode_at_point": [],
        "expected_pincode": None,
        "pin_district": None,
    }
    kwargs.update(over)
    return classify(**kwargs)  # type: ignore[arg-type]


# --- the normal case --------------------------------------------------------


def test_a_point_inside_one_district_resolves_confidently() -> None:
    out = resolve()
    assert (out.method, out.confidence) == (Method.CONTAINED, Confidence.HIGH)
    assert out.lgd_district_code == 555
    assert out.boundary_ambiguous is False


# --- two districts claim it: refuse ----------------------------------------


def test_overlapping_polygons_are_refused_not_arbitrated() -> None:
    """PLAN 1.4: fix the source shapefile, don't paper over.

    Choosing one would be right for half the overlap and silently wrong for
    the other half, with nothing downstream able to tell the difference.
    """
    out = resolve(containing=[ERNAKULAM, DistrictHit(566, 32, "Thrissur", "KERALA")])
    assert out.method is Method.OVERLAPPING
    assert out.district is None
    assert out.resolved is False
    assert "overlap" in out.reasons[0]
    assert "Ernakulam (555)" in out.reasons[0] and "Thrissur (566)" in out.reasons[0]


# --- inside nothing: the 5 km fallback --------------------------------------


def test_a_point_just_outside_a_polygon_falls_back_to_the_nearest() -> None:
    """Coastlines and small gaps between published polygons. Metres, not km."""
    out = resolve(containing=[], nearest=DistrictHit(555, 32, "Ernakulam", "KERALA", 40.0))
    assert out.method is Method.NEAREST
    assert out.lgd_district_code == 555
    assert out.confidence is Confidence.MEDIUM
    assert "40 m away" in out.reasons[0]


def test_a_point_kilometres_out_is_resolved_but_not_trusted() -> None:
    out = resolve(containing=[], nearest=DistrictHit(555, 32, "Ernakulam", "KERALA", 3200.0))
    assert out.method is Method.NEAREST
    assert out.confidence is Confidence.LOW


def test_a_point_beyond_five_kilometres_is_rejected() -> None:
    """Not in India, or the geocoder invented somewhere."""
    out = resolve(containing=[], nearest=DistrictHit(555, 32, "Ernakulam", "KERALA", 242_000.0))
    assert out.method is Method.REJECTED
    assert out.district is None
    assert "beyond the 5 km limit" in out.reasons[0]


def test_the_fallback_limit_is_configurable_and_applied() -> None:
    near = DistrictHit(555, 32, "Ernakulam", "KERALA", 3000.0)
    assert resolve(containing=[], nearest=near, max_fallback_m=5000).resolved
    assert not resolve(containing=[], nearest=near, max_fallback_m=1000).resolved


def test_no_districts_loaded_at_all_is_rejected_not_crashed() -> None:
    out = resolve(containing=[], nearest=None)
    assert out.method is Method.REJECTED
    assert "no district polygons are loaded" in out.reasons[0]


# --- near a district line ---------------------------------------------------


def test_a_neighbouring_district_within_the_radius_downgrades_and_is_named() -> None:
    out = resolve(neighbours=[THRISSUR])
    assert out.boundary_ambiguous is True
    assert out.confidence is Confidence.MEDIUM
    assert out.neighbour is not None and out.neighbour.name == "Thrissur"
    assert "310 m of Thrissur" in out.reasons[0]


def test_a_neighbour_across_a_state_line_says_so_explicitly() -> None:
    """The expensive version of the ambiguity: an entirely different SERC."""
    out = resolve(neighbours=[COIMBATORE])
    assert out.boundary_ambiguous is True
    assert "different state" in out.reasons[0]
    assert "tariff regime" in out.reasons[0]


def test_no_neighbour_means_no_ambiguity_flag() -> None:
    assert resolve(neighbours=[]).boundary_ambiguous is False


# --- the PIN check ----------------------------------------------------------


def test_a_matching_pin_leaves_confidence_alone() -> None:
    out = resolve(pincode_at_point=["682005"], expected_pincode="682005")
    assert out.pin_conflict is False
    assert out.confidence is Confidence.HIGH


def test_a_conflicting_pin_overrides_the_coordinates() -> None:
    """PLAN 1.4: trust the PIN.

    A PIN is something the customer typed about their own site. Coordinates
    are something a geocoder guessed from a string.
    """
    out = resolve(
        pincode_at_point=["682005"],
        expected_pincode="680001",
        pin_district=THRISSUR,
    )
    assert out.method is Method.PIN_OVERRIDE
    assert out.lgd_district_code == 566
    assert out.confidence is Confidence.LOW
    assert out.pin_conflict is True
    assert "Trusting the PIN" in out.reasons[-1]


def test_an_unknown_pin_is_recorded_but_does_not_override() -> None:
    """We cannot override towards a district we cannot identify."""
    out = resolve(pincode_at_point=["682005"], expected_pincode="999999", pin_district=None)
    assert out.method is Method.CONTAINED
    assert out.pin_conflict is True
    assert out.confidence is Confidence.LOW
    assert "does not cover the coordinates" in out.reasons[-1]


def test_a_pin_that_disagrees_but_points_at_the_same_district_does_not_override() -> None:
    """Common near a PIN boundary, and not a problem worth downgrading a verdict for.

    Still recorded: the geocode landed outside the PIN it was given, which is
    worth knowing even when the district survives.
    """
    out = resolve(
        pincode_at_point=["682005"],
        expected_pincode="682030",
        pin_district=DistrictHit(555, 32, "Ernakulam", "KERALA"),
    )
    assert out.method is Method.CONTAINED
    assert out.lgd_district_code == 555
    assert out.pin_conflict is True
    assert "same district" in out.reasons[-1]


def test_no_supplied_pin_is_not_a_conflict() -> None:
    out = resolve(pincode_at_point=["682005"], expected_pincode=None)
    assert out.pin_conflict is False
    assert out.confidence is Confidence.HIGH


def test_duplicate_pins_at_a_point_are_deduplicated() -> None:
    out = resolve(pincode_at_point=["682005", "682005", "682024"])
    assert out.pincode_at_point == ("682005", "682024")


# --- confidence never silently recovers -------------------------------------


def test_the_worst_doubt_wins() -> None:
    """Ambiguous boundary AND a conflicting PIN must not average out to medium."""
    out = resolve(
        neighbours=[THRISSUR],
        pincode_at_point=["682005"],
        expected_pincode="999999",
        pin_district=None,
    )
    assert out.confidence is Confidence.LOW


def test_every_downgrade_carries_a_reason() -> None:
    """An unexplained downgrade is as useless to a report as no downgrade."""
    for out in (
        resolve(neighbours=[THRISSUR]),
        resolve(containing=[], nearest=DistrictHit(555, 32, "Ernakulam", "KERALA", 900.0)),
        resolve(pincode_at_point=["682005"], expected_pincode="680001", pin_district=THRISSUR),
        resolve(containing=[ERNAKULAM, THRISSUR]),
    ):
        assert out.confidence is not Confidence.HIGH
        assert out.reasons, f"{out.method} downgraded with no reason given"
