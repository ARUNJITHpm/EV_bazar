"""Part 13: observed public context, isolated from demand and economics.

Only OSM power is integrated in this checkpoint. Other sources stay deferred,
even if later activated, until their separate report review gates are implemented.
"""

from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.public_reference import EXPANSION_DATASETS, PublicReference
from app.domain.report.payload import (
    LedgerRow,
    ProvenanceRow,
    PublicContextPayload,
    PublicSourceContext,
    ReportPayload,
    SiteFact,
)

NEAREST_POWER_SQL = text("""
    WITH mapped AS (
        SELECT osm_id, kind, voltage, point_derivation, extract_date,
               ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography AS geog
        FROM jsonb_to_recordset(CAST(:observations AS jsonb)) AS p(
            osm_id text, kind text, voltage text, lat double precision,
            lon double precision, point_derivation text, extract_date text)
    ), nearby AS (
        SELECT *, ST_Distance(geog,
            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS distance_m
        FROM mapped
        WHERE ST_DWithin(geog,
            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, 2000)
    )
    SELECT osm_id, kind, voltage, point_derivation, extract_date, distance_m
    FROM nearby
    ORDER BY CASE WHEN kind = 'transformer' THEN 0 ELSE 1 END,
             distance_m, osm_id
    LIMIT 1
""")


@lru_cache(maxsize=4)
def _load(snapshot: str, root: str, digest: str) -> PublicReference:
    return PublicReference.load(Path(snapshot), Path(root), expected_sha256=digest)


def load_report_reference() -> PublicReference | None:
    """Optional release configuration; partial configuration fails closed."""
    values = tuple(
        os.environ.get(name)
        for name in (
            "REPORT_PUBLIC_REFERENCE_SNAPSHOT",
            "REPORT_PUBLIC_REFERENCE_ROOT",
            "REPORT_PUBLIC_REFERENCE_SHA256",
        )
    )
    if not any(values):
        return None
    if not all(values):
        raise ValueError("All three REPORT_PUBLIC_REFERENCE settings are required")
    snapshot, root, digest = values
    assert snapshot is not None and root is not None and digest is not None
    return _load(snapshot, root, digest)


def nearest_power(
    session: Session, reference: PublicReference, *, lat: float, lng: float
) -> dict[str, Any] | None:
    """Geodesic proximity, without inventing an LGD or serving-utility join.

    An in-memory validated rowset is queried by PostGIS; no persistent table,
    migration, external call or independent source import is involved.
    """
    if (
        not math.isfinite(lat)
        or not math.isfinite(lng)
        or not (-90 <= lat <= 90 and -180 <= lng <= 180)
    ):
        raise ValueError("Invalid EPSG:4326 site point")
    result = reference.lookup("osm_power")
    if not result.rows:
        return None
    row = (
        session.execute(
            NEAREST_POWER_SQL,
            {
                "observations": json.dumps(result.rows),
                "lat": lat,
                "lng": lng,
            },
        )
        .mappings()
        .first()
    )
    return None if row is None else dict(row)


def enrich_public_context(
    session: Session, payload: ReportPayload, reference: PublicReference | None
) -> ReportPayload:
    """Enrich a newly assembled payload only; never enrich a stored report."""
    if reference is None:
        return payload
    sources: list[PublicSourceContext] = []
    for dataset in EXPANSION_DATASETS:
        result = reference.lookup(dataset)
        meta = result.provenance or {}
        status = (
            result.status
            if dataset == "osm_power" or result.status == "pending"
            else "not_integrated"
        )
        sources.append(
            PublicSourceContext(
                dataset=dataset,
                status=status,
                source_name=str(meta.get("source_name", "source pending")),
                retrieved_on=meta.get("retrieved_on"),
                source_url=meta.get("source_url"),
                source_sha256=meta.get("source_sha256"),
                transformation_version=meta.get("transformation_version"),
                time_coverage=meta.get("time_coverage"),
                licence=meta.get("licence"),
                licence_url=meta.get("licence_url"),
            )
        )

    osm = reference.lookup("osm_power")
    if osm.status == "pending":
        value = "not assessed"
        source = "OSM power source pending"
    else:
        nearest = nearest_power(session, reference, lat=payload.site.lat, lng=payload.site.lng)
        source = (
            f"{osm.provenance['source_name']} · {osm.provenance['time_coverage']} · "
            f"retrieved {osm.provenance['retrieved_on']}"
        )
        if nearest is None:
            value = "none mapped nearby within 2 km in this regional extract; coverage incomplete"
            sources[-1] = sources[-1].model_copy(update={"status": "no_matching_observations"})
        else:
            value = f"nearest mapped: {round(nearest['distance_m'])} m ({nearest['kind']}"
            if nearest["voltage"] is not None:
                value += f", voltage tag {nearest['voltage']} V, unverified"
            value += f") · {nearest['osm_id']}"
            if nearest["point_derivation"] == "representative_point":
                value += " · distance to first mapped perimeter vertex, not equipment centre"
            source += f" · extract {nearest['extract_date']}"
        source += " · © OpenStreetMap contributors, ODbL-1.0; Geofabrik · site survey confirms"

    fact = SiteFact.model_validate(
        {
            "label": "Transformer distance",
            "value": value,
            "source": source,
            "unverified": True,
            "group": "Power and tariff",
            "direction": "neutral",
            "means": (
                "Mapped proximity does not confirm spare capacity, access "
                "or connection feasibility."
            ),
        }
    )
    facts = list(payload.site_facts)
    index = next((i for i, item in enumerate(facts) if item.label == fact.label), None)
    if index is None:
        facts.append(fact)
    else:
        facts[index] = fact
    # Deferred checks are always visible, and never treated as measured zeros.
    for label, group, source_pending in (
        ("Grid outage hours", "Power and tariff", "reviewed area supply source pending"),
        ("State subsidy applicability", "Power and tariff", "verified policy register pending"),
        ("Announced stations", "Competition", "current dated EV-charging evidence pending"),
        (
            "DISCOM performance",
            "Power and tariff",
            "PFC permission and verified serving DISCOM pending",
        ),
        (
            "EVs per public charger, district",
            "Demand",
            "reviewed monthly registrations and public charger inventory pending",
        ),
    ):
        if not any(item.label == label for item in facts):
            facts.append(
                SiteFact.model_validate(
                    {
                        "label": label,
                        "value": "not assessed",
                        "source": source_pending,
                        "unverified": True,
                        "group": group,
                        "direction": "neutral",
                    }
                )
            )
    ledger = list(payload.ledger)
    for item in facts:
        if item.unverified and item.label not in {row.item for row in ledger}:
            ledger.append(
                LedgerRow(item=item.label, value=item.value, source=item.source, unverified=True)
            )
        elif item.label == "Transformer distance":
            ledger = [
                row
                if row.item != item.label
                else LedgerRow(
                    item=item.label,
                    value=item.value,
                    source=item.source,
                    unverified=True,
                )
                for row in ledger
            ]

    conditions = []
    spare = next((item for item in facts if item.label == "Transformer spare capacity"), None)
    if spare is None or spare.unverified:
        conditions.append(
            "DISCOM confirms transformer spare capacity of at least "
            f"{payload.financials.sanctioned_load.recommended_kva:g} kVA "
            "for the advised managed peak; "
            "connection feasibility remains unverified."
        )
    provenance = [
        row
        if row.label != "schema_version"
        else ProvenanceRow(label="schema_version", value="0013_public_context_v1")
        for row in payload.provenance
    ]
    provenance.append(
        ProvenanceRow(label="public reference snapshot SHA256", value=osm.snapshot_sha256)
    )
    for item in sources:
        provenance.append(
            ProvenanceRow(
                label=f"public source: {item.dataset}",
                value=(
                    f"{item.status} · {item.source_name} · "
                    f"{item.time_coverage or 'period pending'} · "
                    f"retrieved {item.retrieved_on or 'pending'} · "
                    f"transformation {item.transformation_version or 'pending'} · "
                    f"{item.source_url or 'source URL pending'}"
                ),
                unverified=True,
            )
        )
    if osm.provenance:
        provenance.extend(
            [
                ProvenanceRow(
                    label="OSM power source SHA256", value=str(osm.provenance["source_sha256"])
                ),
                ProvenanceRow(
                    label="OSM power licence",
                    value=(
                        "© OpenStreetMap contributors · ODbL-1.0 · Geofabrik · "
                        f"{osm.provenance['licence_url']}"
                    ),
                ),
                ProvenanceRow(
                    label="OSM power limitations",
                    value=str(osm.provenance["notes"]),
                    unverified=True,
                ),
            ]
        )
    return payload.model_copy(
        update={
            "site_facts": facts,
            "ledger": ledger,
            "provenance": provenance,
            "public_context": PublicContextPayload(
                snapshot_sha256=osm.snapshot_sha256,
                sources=sources,
                grid_conditions=conditions,
            ),
        }
    )
