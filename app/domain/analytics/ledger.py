"""Commit each predicted band before simulations can be consumed by analytics."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

import numpy as np
from sqlalchemy.orm import Session

from app.domain.analytics.inputs import VERSIONS, Station
from app.models.predictions import Prediction


class PredictionLedger:
    def __init__(self, session: Session, run_id: uuid.UUID, *, is_demo: bool) -> None:
        self.session, self.run_id, self.is_demo = session, run_id, is_demo

    def record(
        self, station: Station, month: dt.date, draws: np.ndarray, phase: Literal["loo", "forecast"]
    ) -> int:
        if len(draws) < 1000 or not np.isfinite(draws).all() or (draws < 0).any():
            raise ValueError("Require at least 1000 finite non-negative connector-day draws")
        p10, p50, p90 = np.quantile(draws, [0.1, 0.5, 0.9])
        row = Prediction(
            site_id=station.site_id,
            model_version=VERSIONS["model_version"],
            economics_version=VERSIONS["economics_version"],
            predicted_p10=float(p10),
            predicted_p50=float(p50),
            predicted_p90=float(p90),
            actual_kwh=None,
            is_demo=self.is_demo,
            analytics_context={
                **VERSIONS,
                "run_id": str(self.run_id),
                "month": month.isoformat(),
                "phase": phase,
                "public_id": station.public_id,
                "unit": "kwh_per_connector_day",
            },
        )
        self.session.add(row)
        # A separate offline session is required: no request transaction is shared.
        self.session.commit()
        return row.id
