"""Reviewed inputs: never infer connector exposure, ownership matches or LGD joins."""

from __future__ import annotations

import calendar
import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VERSIONS = {
    "model_version": "owner_mixed_v1",
    "economics_version": "not_applicable",
    "schema_version": "usage_aggregate_v1",
    "archetype_version": "not_applicable:public_aggregate",
    "tariff_effective_date": "not_applicable:no_financial_output",
    "renderer_version": "usage_csv_v1",
}


class Station(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    public_id: str = Field(min_length=1)
    site_id: uuid.UUID
    owner_station_id: int | None = None
    lgd_code: int = Field(gt=0)
    state: str = Field(min_length=1)
    connectors_ac: int = Field(ge=0)
    connectors_dc: int = Field(ge=0)
    mean_power_kw: float = Field(gt=0, allow_inf_nan=False)
    opened_month: dt.date | None
    road_class: Literal["national_highway", "state_highway", "urban", "rural"]
    highway_distance_km: float = Field(ge=0, allow_inf_nan=False)
    ev_registrations: int = Field(ge=0)
    consent: bool = False
    meter_type: Literal["separate", "shared", "unsure"] = "unsure"
    reviewed: Literal[True]

    @model_validator(mode="after")
    def exposure(self) -> Station:
        if self.connectors_ac + self.connectors_dc == 0:
            raise ValueError("Reviewed physical connector counts are required")
        if self.opened_month and self.opened_month.day != 1:
            raise ValueError("Opening month must start on day one")
        return self

    @property
    def connectors(self) -> int:
        return self.connectors_ac + self.connectors_dc


class Bill(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    station_id: int
    month: dt.date
    kwh: float = Field(ge=0, allow_inf_nan=False)
    confirmed_at: dt.datetime
    confirmed: bool
    full_calendar_month_verified: bool
    correction_id: int = Field(ge=0)

    @model_validator(mode="after")
    def period(self) -> Bill:
        if self.month.day != 1 or self.confirmed_at.tzinfo is None:
            raise ValueError("Require calendar month and timezone-aware confirmation")
        return self


def latest_bills(stations: list[Station], bills: list[Bill]) -> dict[tuple[int, dt.date], Bill]:
    # Latest confirmed correction wins before eligibility is applied. A correction
    # that invalidates exposure must not resurrect an earlier eligible reading.
    latest: dict[tuple[int, dt.date], Bill] = {}
    for bill in bills:
        if not bill.confirmed:
            continue
        key = (bill.station_id, bill.month)
        old = latest.get(key)
        if old is None or (bill.confirmed_at, bill.correction_id) > (
            old.confirmed_at,
            old.correction_id,
        ):
            latest[key] = bill
    eligible = {
        station.owner_station_id
        for station in stations
        if station.consent and station.meter_type == "separate"
    }
    return {
        key: bill
        for key, bill in latest.items()
        if key[0] in eligible and bill.full_calendar_month_verified
    }


def connector_days(station: Station, month: dt.date) -> int:
    return station.connectors * calendar.monthrange(month.year, month.month)[1]


def check_inventory(stations: list[Station]) -> None:
    for values in (
        [station.public_id for station in stations],
        [station.site_id for station in stations],
        [station.owner_station_id for station in stations if station.owner_station_id is not None],
    ):
        if len(values) != len(set(values)):
            raise ValueError("Physical station mappings must be one-to-one")
    if any(
        station.opened_month is not None and station.opened_month > dt.date.today()
        for station in stations
    ):
        raise ValueError("Opening month cannot be in the future")
