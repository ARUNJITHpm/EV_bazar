"""Dated public area context, separate from owner grid fields and models."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.domain.owner.grid import OWNER_GRID_VERSIONS, _station
from app.domain.public_reference import PublicReference
from app.domain.report.public_context import load_report_reference


class AreaItem(BaseModel):
    key: str
    label: str
    value: str | None = None
    source_name: str
    source_url: str | None = None
    retrieved_on: str | None = None
    reporting_period: str | None = None
    scope: str | None = None
    note: str


class OwnerAreaOut(BaseModel):
    version: Literal["owner_area_v1"] = "owner_area_v1"
    versions: dict[str, str] = Field(
        default_factory=lambda: {
            **OWNER_GRID_VERSIONS,
            "schema_version": "owner_area_v1",
            "model_version": "not_applicable:observed_public_data",
            "renderer_version": "owner_area_ui_v1",
        }
    )
    state: str | None
    district: str | None
    snapshot_sha256: str | None
    items: list[AreaItem]


def area_context(
    session: Session,
    account_id: int,
    station_id: int,
    reference: PublicReference | None = None,
) -> OwnerAreaOut:
    station = _station(session, account_id, station_id)
    reference = reference if reference is not None else load_report_reference()
    items = [
        AreaItem(
            key="ev_registrations",
            label="EV registrations · last 12 months",
            source_name="VAHAN · reviewed monthly source pending",
            note="Complete district coverage must be reviewed before counts are shown.",
        ),
        AreaItem(
            key="ev_growth",
            label="EV registration growth",
            source_name="VAHAN · reviewed monthly source pending",
            note="A comparable prior-year period is required; missing months are not zero.",
        ),
        AreaItem(
            key="ev_per_charger",
            label="EVs per public charger · district and state",
            source_name="VAHAN and public charger inventory · pending",
            note="Compatible EV counts and a deduplicated charger denominator are required.",
        ),
        AreaItem(
            key="ev_tariff",
            label="EV tariff and time-of-day bands",
            source_name="Verified electricity order and serving utility · pending",
            note=(
                "A state or electricity-board name does not verify your serving DISCOM "
                "or tariff category."
            ),
        ),
        AreaItem(
            key="supply_hours",
            label="Average supply hours for your area",
            source_name="CEA/NPP · reviewed supply source pending",
            note="Area averages describe supply, not this feeder or your station's outage hours.",
        ),
        AreaItem(
            key="ev_policies",
            label="Charging-station policies in force",
            source_name="Human-verified notified policy register · pending",
            note="Notification, amendments, validity and charging eligibility must be reviewed.",
        ),
    ]
    digest = None
    if reference is not None:
        # No state means no meaningful area filter; never display national rows.
        result = reference.lookup("supply_hours", state=station.state_name)
        digest = result.snapshot_sha256
        if result.provenance is not None:
            meta = result.provenance
            items[4] = items[4].model_copy(
                update={
                    "source_name": str(meta["source_name"]),
                    "source_url": meta["source_url"],
                    "retrieved_on": meta["retrieved_on"],
                    "reporting_period": meta["time_coverage"],
                }
            )
        if station.state_name:
            # Stations currently have state/district names, not a reviewed LGD/
            # utility identity. Only genuinely statewide rows are eligible.
            eligible = [
                row
                for row in result.rows
                if row.get("lgd_code") is None
                and row.get("discom_id") is None
                and str(row["period_end"]) <= dt.datetime.now(dt.UTC).date().isoformat()
            ]
            if eligible:
                latest = max(str(row["period_end"]) for row in eligible)
                selected = [row for row in eligible if row["period_end"] == latest]
                # Multiple rows for the same area type require source review;
                # do not silently pick an edition or aggregate incompatible rows.
                kinds = [str(row["area_type"]) for row in selected]
                if len(kinds) == len(set(kinds)):
                    value = "; ".join(
                        f"{row['area_type']}: {row['avg_supply_hours_per_day']:g} h/day · "
                        f"{row['published_period_label']} · {row['supply_definition']}"
                        for row in selected
                    )
                    items[4] = items[4].model_copy(
                        update={
                            "value": value,
                            "scope": f"{station.state_name} state area average",
                        }
                    )
    return OwnerAreaOut(
        state=station.state_name,
        district=station.district_name,
        snapshot_sha256=digest,
        items=items,
    )
