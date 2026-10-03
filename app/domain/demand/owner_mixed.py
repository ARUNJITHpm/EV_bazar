"""Offline hierarchical energy model. No unrecorded prediction interface exists."""

from __future__ import annotations

import datetime as dt
import warnings
from typing import Literal

import numpy as np
import pandas as pd
from statsmodels.regression.mixed_linear_model import MixedLM

from app.domain.analytics.inputs import Bill, Station, connector_days, latest_bills
from app.domain.analytics.ledger import PredictionLedger

FEATURES = [
    "dc_share",
    "power_class",
    "log_age",
    "highway",
    "urban",
    "rural",
    "log_distance",
    "log_ev",
]


def age(station: Station, month: dt.date) -> float | None:
    if station.opened_month is None:
        return None
    months = (
        (month.year - station.opened_month.year) * 12 + month.month - station.opened_month.month
    )
    if months < 0:
        raise ValueError("Inventory is not active in the target month")
    return float(months)


def feature_row(station: Station, month: dt.date, age_months: float) -> dict[str, object]:
    return {
        "state": station.state,
        "district": str(station.lgd_code),
        "dc_share": station.connectors_dc / station.connectors,
        "power_class": 0 if station.mean_power_kw < 22 else 1 if station.mean_power_kw < 60 else 2,
        "log_age": np.log1p(age_months),
        "highway": float(station.road_class == "national_highway"),
        "urban": float(station.road_class == "urban"),
        "rural": float(station.road_class == "rural"),
        "log_distance": np.log1p(station.highway_distance_km),
        "log_ev": np.log1p(station.ev_registrations),
    }


def safe_covariance(covariance: np.ndarray) -> np.ndarray:
    covariance = (covariance + covariance.T) / 2
    if not np.isfinite(covariance).all():
        raise ValueError("Model covariance is not finite")
    values, vectors = np.linalg.eigh(covariance)
    if values.min() < -1e-6:
        raise ValueError("Model covariance is not positive semidefinite")
    return vectors @ np.diag(np.maximum(values, 0)) @ vectors.T


class OwnerMixedModel:
    def __init__(
        self, stations: list[Station], bills: list[Bill], *, draws: int = 1000, seed: int = 0
    ) -> None:
        if draws < 1000:
            raise ValueError("At least 1000 simulations are required")
        self.draw_count, self.rng = draws, np.random.default_rng(seed)
        self.stations = stations
        by_owner = {station.owner_station_id: station for station in stations}
        if len(latest_bills(stations, bills)) != len(bills):
            raise ValueError("Only latest eligible full-month observations may train the model")
        if (
            len({bill.station_id for bill in bills}) < 30
            or len({by_owner[bill.station_id].state for bill in bills}) < 2
        ):
            raise ValueError("Require at least 30 distinct eligible stations in two states to fit")
        rows = []
        for bill in bills:
            station = by_owner[bill.station_id]
            months = age(station, bill.month)
            if months is None:
                raise ValueError("Training station opening month must be verified")
            rows.append(
                {
                    **feature_row(station, bill.month, months),
                    "outcome": np.log1p(bill.kwh / connector_days(station, bill.month)),
                }
            )
        frame = pd.DataFrame(rows)
        # Remove zero-variance features explicitly, recording the selected design.
        self.features = [name for name in FEATURES if frame[name].nunique() > 1]
        formula = "outcome ~ " + " + ".join(self.features) if self.features else "outcome ~ 1"
        with warnings.catch_warnings(record=True):
            fitted = MixedLM.from_formula(
                formula,
                frame,
                groups="state",
                re_formula="1",
                vc_formula={"district": "0 + C(district)"},
                eval_env=-1,
            ).fit(reml=True, method=["lbfgs", "bfgs"], maxiter=500, disp=False)
        if not fitted.converged or not np.isfinite(fitted.fe_params).all():
            raise ValueError("Hierarchical fit did not converge")
        if list(fitted.fe_params.index) != ["Intercept", *self.features]:
            raise ValueError("Unexpected model design order")
        self.fitted = fitted
        # Conditional GLS covariance for the declared fixed-variance simulation.
        # The joint Hessian can be indefinite at a variance-component boundary;
        # do not turn that Hessian into a repaired or invented uncertainty band.
        information = np.zeros((len(self.features) + 1, len(self.features) + 1))
        for state in frame.state.unique():
            block = frame[frame.state == state]
            design = np.column_stack([np.ones(len(block)), block[self.features].to_numpy()])
            district = block.district.to_numpy()
            covariance = (
                np.eye(len(block)) * float(fitted.scale)
                + np.ones((len(block), len(block))) * float(fitted.cov_re.iloc[0, 0])
                + (district[:, None] == district[None, :]) * float(fitted.vcomp[0])
            )
            information += design.T @ np.linalg.solve(covariance, design)
        self.beta = self.rng.multivariate_normal(
            fitted.fe_params.to_numpy(), safe_covariance(np.linalg.inv(information)), draws
        )
        self.random_draws: dict[str, dict[str, np.ndarray]] = {}
        for state, effects in fitted.random_effects.items():
            simulations = self.rng.multivariate_normal(
                effects.to_numpy(),
                safe_covariance(fitted.random_effects_cov[state].to_numpy()),
                draws,
            )
            self.random_draws[state] = {
                name: simulations[:, index] for index, name in enumerate(effects.index)
            }
        self.unknown_states: dict[str, np.ndarray] = {}
        self.unknown_districts: dict[int, np.ndarray] = {}

    def predict(
        self,
        station: Station,
        month: dt.date,
        ledger: PredictionLedger,
        phase: Literal["loo", "forecast"],
    ) -> np.ndarray:
        months = age(station, month)
        if months is None:
            ages = [
                age(peer, month)
                for peer in self.stations
                if peer.state == station.state
                and peer.opened_month is not None
                and peer.opened_month <= month
            ]
            if not ages:
                raise ValueError("No state opening-age distribution available for imputation")
            ages_drawn = self.rng.choice(ages, self.draw_count)
        else:
            ages_drawn = np.full(self.draw_count, months)
        rows = pd.DataFrame([feature_row(station, month, float(value)) for value in ages_drawn])
        design = np.column_stack([np.ones(self.draw_count), rows[self.features].to_numpy()])
        log_energy = np.sum(design * self.beta, axis=1)
        effects = self.random_draws.get(station.state)
        district_key = f"district[C(district)[{station.lgd_code}]]"
        if effects is not None:
            log_energy += next(
                value for name, value in effects.items() if not name.startswith("district[")
            )
        else:
            if station.state not in self.unknown_states:
                self.unknown_states[station.state] = self.rng.normal(
                    0, np.sqrt(max(float(self.fitted.cov_re.iloc[0, 0]), 0)), self.draw_count
                )
            log_energy += self.unknown_states[station.state]
        if effects is not None and district_key in effects:
            log_energy += effects[district_key]
        else:
            if station.lgd_code not in self.unknown_districts:
                self.unknown_districts[station.lgd_code] = self.rng.normal(
                    0, np.sqrt(max(float(self.fitted.vcomp[0]), 0)), self.draw_count
                )
            log_energy += self.unknown_districts[station.lgd_code]
        noise = np.sqrt(max(float(self.fitted.scale), 0))
        log_energy += self.rng.normal(0, noise * (1.25 if months is None else 1), self.draw_count)
        with np.errstate(over="raise", invalid="raise"):
            draws = np.maximum(np.expm1(log_energy), 0)
        ledger.record(station, month, draws, phase)
        return draws
