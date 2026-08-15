"""The Lookup console panel - PART C.

Only the pure parts are tested here, and deliberately so: ``lookup_point``
itself is three PostGIS queries and a dataclass copy, while ``build_steps`` is
prose *about* a decision, which is exactly the kind of thing that drifts away
from the decision it describes without anyone noticing.

The pin-override case below is not hypothetical - the first version of the
panel reported the overriding district in step 1, so the trace claimed a
containment query had returned a district it never saw.
"""

from __future__ import annotations

from app.api.internal.lookup import build_fields, build_steps, tier_for
from app.domain.resolution.geography import Confidence, DistrictHit, Method, Resolution

ERNAKULAM = DistrictHit(
    lgd_district_code=555, lgd_state_code=32, name="Ernakulam", state_name="KERALA"
)
THRISSUR = DistrictHit(
    lgd_district_code=566, lgd_state_code=32, name="Thrissur", state_name="KERALA"
)
COIMBATORE = DistrictHit(
    lgd_district_code=571,
    lgd_state_code=33,
    name="Coimbatore",
    state_name="TAMIL NADU",
    distance_m=87.0,
)


def _steps(res: Resolution) -> list[str]:
    return [s.answer for s in build_steps(res, districts=783, pincodes=19312)]


def test_the_containment_step_names_the_district_the_point_is_in() -> None:
    res = Resolution(method=Method.CONTAINED, confidence=Confidence.HIGH, district=ERNAKULAM)
    assert "Ernakulam (555)" in _steps(res)[0]


def test_a_pin_override_step_1_names_where_the_coordinates_landed() -> None:
    """The regression. Step 1 describes the containment query, which returned
    Ernakulam; Thrissur is what the PIN did to that answer afterwards."""
    res = Resolution(
        method=Method.PIN_OVERRIDE,
        confidence=Confidence.LOW,
        district=THRISSUR,
        overridden_district=ERNAKULAM,
        pincode_at_point=("682005",),
        expected_pincode="680001",
        pin_conflict=True,
    )
    steps = _steps(res)
    assert "Ernakulam" in steps[0]
    assert "Thrissur" not in steps[0]


def test_the_decisive_step_is_the_one_that_settled_it() -> None:
    res = Resolution(
        method=Method.PIN_OVERRIDE,
        confidence=Confidence.LOW,
        district=THRISSUR,
        overridden_district=ERNAKULAM,
        expected_pincode="680001",
        pin_conflict=True,
    )
    decisive = [s.question for s in build_steps(res, districts=783, pincodes=1) if s.decisive]
    assert any("PIN" in q for q in decisive)


def test_a_refusal_is_narrated_rather_than_left_blank() -> None:
    res = Resolution(
        method=Method.REJECTED,
        confidence=Confidence.LOW,
        district=None,
        reasons=("nearest district is Junagadh at 180.4 km, beyond the 5 km limit.",),
    )
    steps = _steps(res)
    assert "inside no district polygon" in steps[0]
    assert "180.4 km" in steps[1]


def test_a_neighbour_across_a_state_line_is_called_out() -> None:
    res = Resolution(
        method=Method.CONTAINED,
        confidence=Confidence.MEDIUM,
        district=DistrictHit(
            lgd_district_code=563, lgd_state_code=32, name="Palakkad", state_name="KERALA"
        ),
        boundary_ambiguous=True,
        neighbour=COIMBATORE,
    )
    assert any("Coimbatore" in s and "87 m" in s for s in _steps(res))


def test_every_step_says_where_it_looked() -> None:
    """A step with no source is the kind of line that reads as authority
    without being checkable."""
    res = Resolution(method=Method.CONTAINED, confidence=Confidence.HIGH, district=ERNAKULAM)
    assert all(s.looked_in and s.using for s in build_steps(res, districts=783, pincodes=1))


def test_provenance_never_claims_a_column_for_a_computed_value() -> None:
    res = Resolution(method=Method.CONTAINED, confidence=Confidence.HIGH, district=ERNAKULAM)
    by_field = {f.field: f for f in build_fields(res)}
    assert by_field["lgd_district_code"].source == "districts.lgd_district_code"
    assert "computed" in by_field["confidence"].source


# --- the tier gate ---------------------------------------------------------


def test_no_tariff_is_tier_3_however_much_else_we_have() -> None:
    """Occupancy and vehicle counts are worth nothing without a price per unit."""
    tier, why = tier_for(tariff=False, poll=True, vahan=True, osm=True)
    assert tier == 3
    assert "tariff" in why


def test_tariffs_alone_earn_tier_2() -> None:
    """PLAN 3's exit criterion: the breakeven number is sellable with no demand
    model at all."""
    tier, why = tier_for(tariff=True, poll=False, vahan=False, osm=False)
    assert tier == 2
    assert "occupancy" in why


def test_tier_1_needs_the_evidence_a_full_report_rests_on() -> None:
    assert tier_for(tariff=True, poll=True, vahan=True, osm=False)[0] == 1


def test_today_is_tier_3_everywhere() -> None:
    """Stated rather than worked around: no tariffs, no polling, no VAHAN."""
    assert tier_for(tariff=False, poll=False, vahan=False, osm=False)[0] == 3
