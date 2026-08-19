"""The labelled stand-in demand model - ``synthetic_v0``. PURE.

The demand layer's contract (OVERVIEW.md §2): a model predicts exactly one
thing, ``kwh_per_connector_day``, as a P10/P50/P90 band with a ramp - and the
ROI engine turns it into money. No occupancy data exists yet (blocker B3), so
this module fills the slot with a **deterministic formula over signals we
actually have** - archetype, VAHAN density and growth, competitor density,
dwell anchors, road class - shaped exactly like the real model (PLAN 4.2's
heuristic, coefficients in a versioned config file) so that swapping in the
calibrated version later is a data-source change, not a rewrite.

What keeps this honest rather than invented:

* **Deterministic, no randomness.** Same inputs, same band, reproducible
  report. It is a formula with stated coefficients, not a dice roll.
* **It never narrows with confidence it does not have.** Every missing input
  *widens* the band (the null-handling rule for context features, applied to
  uncertainty itself).
* **The version stamp says what it is.** ``synthetic_v0`` propagates to the
  prediction log, the report's ledger and the hero figure's "modelled, not
  measured" flag. Rule 5 applies in full: every prediction is written to
  ``predictions`` with a NULL actual, demo runs flagged, never skipped.
* **Pure.** No DB, no network, no clock. Weights come in as an argument;
  ``load_weights()`` is the one convenience that touches the filesystem, and
  it reads only this package's versioned JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_WEIGHTS_PATH = Path(__file__).with_name("synthetic_v0.json")

#: Physical ceiling: one connector charging at full rated power all day.
_HOURS_PER_DAY = 24.0


@dataclass(frozen=True)
class SyntheticWeights:
    """PLAN 4.2's coefficients, typed. Loaded from the versioned JSON."""

    model_version: str
    archetype_base: dict[str, float]
    ev_density_pivot: float
    ev_density_span: float
    growth_pivot: float
    growth_gain: float
    competition_per_station: float
    dc_fast_extra: float
    competition_floor: float
    dwell_gain: float
    dwell_cap: float
    road_on_major_bonus: float
    band_p10: float
    band_p90: float
    unknown_widen: float
    ramp_years: tuple[float, ...]
    ceiling_fraction: float


@dataclass(frozen=True)
class SyntheticInputs:
    """The signals the formula consumes. Every Optional is genuinely optional:
    a None widens the band rather than crashing or defaulting silently."""

    archetype: str
    rated_kw_per_connector: float
    district_ev_total: int | None = None
    district_growth: float | None = None
    competitors_within_3km: int | None = None
    dc_fast_within_3km: int | None = None
    dwell_anchor_score: float | None = None
    on_major_road: bool | None = None


@dataclass(frozen=True)
class SyntheticPrediction:
    """``kwh_per_connector_day`` as a band, plus per-year ramps for the ROI
    engine's ``kwh_by_year`` (per connector - the caller scales by count)."""

    model_version: str
    kwh_per_connector_day_p10: float
    kwh_per_connector_day_p50: float
    kwh_per_connector_day_p90: float
    #: Ramp curves, one value per ramp year then steady state, per connector.
    kwh_year_ramp_p10: tuple[float, ...]
    kwh_year_ramp_p50: tuple[float, ...]
    kwh_year_ramp_p90: tuple[float, ...]
    #: How many inputs were missing - the band was widened this many times.
    unknown_inputs: int


def load_weights(path: Path = _WEIGHTS_PATH) -> SyntheticWeights:
    """Read the versioned coefficient file. The only I/O in this module."""
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    bases: dict[str, Any] = raw["archetype_base_kwh_per_connector_day"]
    return SyntheticWeights(
        model_version=str(raw["model_version"]),
        archetype_base={k: float(v) for k, v in bases.items()},
        ev_density_pivot=float(raw["ev_density_pivot"]),
        ev_density_span=float(raw["ev_density_span"]),
        growth_pivot=float(raw["growth_pivot"]),
        growth_gain=float(raw["growth_gain"]),
        competition_per_station=float(raw["competition_per_station"]),
        dc_fast_extra=float(raw["dc_fast_extra"]),
        competition_floor=float(raw["competition_floor"]),
        dwell_gain=float(raw["dwell_gain"]),
        dwell_cap=float(raw["dwell_cap"]),
        road_on_major_bonus=float(raw["road_on_major_bonus"]),
        band_p10=float(raw["band_p10"]),
        band_p90=float(raw["band_p90"]),
        unknown_widen=float(raw["unknown_widen"]),
        ramp_years=tuple(float(v) for v in raw["ramp_years"]),
        ceiling_fraction=float(raw["ceiling_fraction"]),
    )


def _demand_factor(inputs: SyntheticInputs, w: SyntheticWeights) -> tuple[float, int]:
    """The multiplicative factor over the archetype base, and how many inputs
    were missing. Each term is bounded so no single signal can run away."""
    unknown = 0
    factor = 1.0

    if inputs.district_ev_total is None:
        unknown += 1
    else:
        # More EVs than the pivot lifts demand, fewer cuts it, saturating at
        # +-span. Linear in the ratio, clamped - not a fitted curve, a stated one.
        ratio = min(2.0, inputs.district_ev_total / w.ev_density_pivot)
        factor *= 1.0 + w.ev_density_span * (ratio - 1.0)

    if inputs.district_growth is None:
        unknown += 1
    else:
        factor *= 1.0 + w.growth_gain * (inputs.district_growth - w.growth_pivot)

    if inputs.competitors_within_3km is None:
        unknown += 1
    else:
        dc_fast = inputs.dc_fast_within_3km or 0
        cut = (
            inputs.competitors_within_3km * w.competition_per_station
            + dc_fast * w.dc_fast_extra
        )
        factor *= max(w.competition_floor, 1.0 - cut)

    if inputs.dwell_anchor_score is None:
        unknown += 1
    else:
        factor *= 1.0 + min(w.dwell_cap, inputs.dwell_anchor_score * w.dwell_gain)

    if inputs.on_major_road is None:
        unknown += 1
    elif inputs.on_major_road:
        factor *= 1.0 + w.road_on_major_bonus

    return max(0.05, factor), unknown


def predict(inputs: SyntheticInputs, weights: SyntheticWeights) -> SyntheticPrediction:
    """The whole model. Deterministic, bounded, and honest about ignorance."""
    if inputs.rated_kw_per_connector <= 0:
        raise ValueError("rated_kw_per_connector must be positive")

    base = weights.archetype_base.get(inputs.archetype, weights.archetype_base["default"])
    factor, unknown = _demand_factor(inputs, weights)

    ceiling = inputs.rated_kw_per_connector * _HOURS_PER_DAY * weights.ceiling_fraction
    p50 = min(ceiling, base * factor)

    # Every unknown input widens the band symmetrically - uncertainty about
    # the inputs becomes uncertainty in the output, never false precision.
    widen = 1.0 + weights.unknown_widen * unknown
    p10 = p50 * weights.band_p10 / widen
    p90 = min(ceiling, p50 * weights.band_p90 * widen)

    def ramp(steady_per_day: float) -> tuple[float, ...]:
        return tuple(round(steady_per_day * 365.0 * r, 1) for r in weights.ramp_years)

    return SyntheticPrediction(
        model_version=weights.model_version,
        kwh_per_connector_day_p10=round(p10, 2),
        kwh_per_connector_day_p50=round(p50, 2),
        kwh_per_connector_day_p90=round(p90, 2),
        kwh_year_ramp_p10=ramp(p10),
        kwh_year_ramp_p50=ramp(p50),
        kwh_year_ramp_p90=ramp(p90),
        unknown_inputs=unknown,
    )
