"""synthetic_v0 - the labelled stand-in demand model. PURE, so tested hard.

The properties that make a stopgap honest rather than invented: deterministic,
ordered (P10 < P50 < P90), monotone in the signals it claims to use, WIDER
when inputs are missing, capped by physics, and stamped with its version.
"""

from __future__ import annotations

import pytest

from app.domain.demand.synthetic import (
    SyntheticInputs,
    SyntheticWeights,
    load_weights,
    predict,
)


@pytest.fixture(scope="module")
def weights() -> SyntheticWeights:
    return load_weights()


def _inputs(**overrides: object) -> SyntheticInputs:
    base: dict[str, object] = {
        "archetype": "urban_office_arterial",
        "rated_kw_per_connector": 60.0,
        "district_ev_total": 17895,
        "district_growth": 0.335,
        "competitors_within_3km": 8,
        "dc_fast_within_3km": 3,
        "dwell_anchor_score": 5.5,
        "on_major_road": True,
    }
    base.update(overrides)
    return SyntheticInputs(**base)  # type: ignore[arg-type]


def test_same_inputs_same_band(weights: SyntheticWeights) -> None:
    """Deterministic: a report must regenerate identically (Rule 1)."""
    assert predict(_inputs(), weights) == predict(_inputs(), weights)


def test_band_is_ordered(weights: SyntheticWeights) -> None:
    p = predict(_inputs(), weights)
    assert p.kwh_per_connector_day_p10 < p.kwh_per_connector_day_p50
    assert p.kwh_per_connector_day_p50 < p.kwh_per_connector_day_p90


def test_version_stamp_propagates(weights: SyntheticWeights) -> None:
    assert predict(_inputs(), weights).model_version == "synthetic_v0"


def test_more_competition_means_less_demand(weights: SyntheticWeights) -> None:
    crowded = predict(_inputs(competitors_within_3km=8), weights)
    empty = predict(_inputs(competitors_within_3km=0, dc_fast_within_3km=0), weights)
    assert crowded.kwh_per_connector_day_p50 < empty.kwh_per_connector_day_p50


def test_growth_lifts_demand(weights: SyntheticWeights) -> None:
    fast = predict(_inputs(district_growth=0.5), weights)
    flat = predict(_inputs(district_growth=0.0), weights)
    assert fast.kwh_per_connector_day_p50 > flat.kwh_per_connector_day_p50


def test_missing_inputs_widen_the_band_not_narrow_it(weights: SyntheticWeights) -> None:
    """The null-handling rule applied to uncertainty itself: ignorance must
    show up as a wider band, never as false precision."""
    full = predict(_inputs(), weights)
    blind = predict(
        _inputs(
            district_ev_total=None,
            district_growth=None,
            competitors_within_3km=None,
            dwell_anchor_score=None,
            on_major_road=None,
        ),
        weights,
    )
    assert blind.unknown_inputs == 5
    full_spread = full.kwh_per_connector_day_p90 / full.kwh_per_connector_day_p10
    blind_spread = blind.kwh_per_connector_day_p90 / blind.kwh_per_connector_day_p10
    assert blind_spread > full_spread


def test_every_percentile_respects_the_physical_ceiling(weights: SyntheticWeights) -> None:
    """A 7 kW AC connector cannot deliver a DC-fast day of energy."""
    p = predict(_inputs(archetype="urban_fleet_depot", rated_kw_per_connector=7.0), weights)
    ceiling = 7.0 * 24.0
    assert p.kwh_per_connector_day_p90 <= ceiling


def test_unknown_archetype_falls_back_to_default(weights: SyntheticWeights) -> None:
    named = predict(_inputs(archetype="no_such_cluster"), weights)
    assert named.kwh_per_connector_day_p50 > 0


def test_ramp_rises_to_steady_state(weights: SyntheticWeights) -> None:
    """PLAN 4.2: output a ramp, because a flat rate makes good sites look bad
    and bad sites look survivable."""
    p = predict(_inputs(), weights)
    ramp = p.kwh_year_ramp_p50
    assert list(ramp) == sorted(ramp)
    assert ramp[-1] == pytest.approx(p.kwh_per_connector_day_p50 * 365, rel=0.01)


def test_nonpositive_rating_is_refused(weights: SyntheticWeights) -> None:
    with pytest.raises(ValueError):
        predict(_inputs(rated_kw_per_connector=0.0), weights)
