"""Part 13: compatibility, nulls, provenance and isolated public observations."""

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.internal import reports
from app.domain.public_reference import PublicReference
from app.domain.report.payload import ReportPayload, SiteFact
from app.domain.report.public_context import (
    NEAREST_POWER_SQL,
    enrich_public_context,
    load_report_reference,
    nearest_power,
)
from app.domain.report.public_coverage import public_context_gaps
from tests.test_report_pipeline import _assemble

pytest_plugins = ("tests.test_report_pipeline",)


def reference(*, active=True, rows=None):
    return PublicReference(
        {
            "datasets": {
                "osm_power": {
                    "rows": rows
                    if rows is not None
                    else [
                        {
                            "osm_id": "node/13",
                            "kind": "transformer",
                            "voltage": None,
                            "lat": 8.567,
                            "lon": 76.873,
                            "lgd_code": None,
                            "extract_date": "2026-09-30",
                            "point_derivation": "node",
                        }
                    ],
                    "metadata": {
                        "source_name": "OSM / Geofabrik",
                        "source_url": "https://download.geofabrik.de/",
                        "time_coverage": "regional snapshot 2026-09-30",
                        "retrieved_on": "2026-10-01",
                        "source_sha256": "b" * 64,
                        "transformation_version": "first_vertex_v1",
                        "licence": "ODbL-1.0",
                        "licence_url": "https://www.openstreetmap.org/copyright",
                        "notes": "Incomplete mapping; district joins unresolved",
                    },
                }
            }
            if active
            else {}
        },
        "a" * 64,
    )


class GeographySession:
    def __init__(self, row=None):
        self.row = row
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((statement, params))
        return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: self.row))


def near(**updates):
    return dict(
        osm_id="way/23",
        kind="substation",
        voltage="11000;33000",
        point_derivation="representative_point",
        extract_date="2026-09-30",
        distance_m=140.4,
        **updates,
    )


def test_no_reference_leaves_the_existing_payload_unchanged(session):
    payload = _assemble(session)
    assert enrich_public_context(session, payload, None) is payload
    old = payload.model_dump(exclude={"public_context"})
    assert ReportPayload.model_validate(old).public_context is None
    assert public_context_gaps(old) == ("public context absent from this stored report",)


@pytest.mark.parametrize(
    "active, row, expected",
    [
        (False, None, "not assessed"),
        (True, None, "none mapped nearby within 2 km"),
        (True, near(), "nearest mapped: 140 m (substation"),
    ],
)
def test_available_missing_and_pending_are_distinct(session, active, row, expected):
    payload = _assemble(session)
    original = payload.model_dump()
    db = GeographySession(row)
    enriched = enrich_public_context(db, payload, reference(active=active))
    fact = next(item for item in enriched.site_facts if item.label == "Transformer distance")
    assert fact.value.startswith(expected)
    assert fact.unverified
    assert enriched.financials == payload.financials
    assert enriched.predicted == payload.predicted
    assert enriched.verdict == payload.verdict
    assert payload.model_dump() == original
    assert all(
        item.label in {r.item for r in enriched.ledger}
        for item in enriched.site_facts
        if item.unverified
    )
    assert len(enriched.public_context.grid_conditions) == 1
    assert "kVA" in enriched.public_context.grid_conditions[0]
    assert len(public_context_gaps(enriched.model_dump())) >= 4
    assert all(
        item.value == "not assessed"
        for item in enriched.site_facts
        if item.label in ("DISCOM performance", "EVs per public charger, district")
    )
    if not active:
        assert db.calls == []
    else:
        assert "ODbL-1.0" in fact.source
    if row:
        assert "first mapped perimeter vertex" in fact.value
        assert "voltage tag 11000;33000 V, unverified" in fact.value


def test_query_uses_geography_radius_and_transformer_preference_without_lgd_inference():
    db = GeographySession()
    assert nearest_power(db, reference(), lat=8.567, lng=76.873) is None
    sql, params = db.calls[0]
    assert sql is NEAREST_POWER_SQL
    sql = str(sql)
    assert "::geography" in sql and "ST_DWithin" in sql and "2000" in sql
    assert "CASE WHEN kind = 'transformer' THEN 0 ELSE 1 END" in sql
    assert "distance_m, osm_id" in sql
    assert json.loads(params["observations"])[0]["lgd_code"] is None
    assert params["lng"] == 76.873


def test_unknown_voltage_is_not_zero_or_a_capacity_claim(session):
    row = near()
    row.update(kind="transformer", voltage=None, point_derivation="node")
    p = enrich_public_context(GeographySession(row), _assemble(session), reference())
    fact = next(f for f in p.site_facts if f.label == "Transformer distance")
    assert "voltage" not in fact.value and "perimeter" not in fact.value
    assert "spare capacity" not in fact.value
    assert "confirms transformer spare capacity" in p.public_context.grid_conditions[0]


def test_verified_capacity_does_not_request_the_same_confirmation(session):
    p = _assemble(session)
    p.site_facts = [f for f in p.site_facts if f.label != "Transformer spare capacity"]
    p.site_facts.append(
        SiteFact(
            label="Transformer spare capacity",
            value="survey record",
            source="verified DISCOM record",
            unverified=False,
        )
    )
    result = enrich_public_context(GeographySession(), p, reference())
    assert result.public_context.grid_conditions == []


def test_snapshot_source_dates_and_six_report_stamps_are_carried(session):
    p = enrich_public_context(GeographySession(near()), _assemble(session), reference())
    stamps = {r.label: r.value for r in p.provenance}
    assert stamps["schema_version"] == "0013_public_context_v1"
    assert all(
        name in stamps
        for name in (
            "model_version",
            "economics_version",
            "schema_version",
            "archetype_version",
            "tariff_effective_date",
            "renderer_version",
        )
    )
    assert stamps["public reference snapshot SHA256"] == "a" * 64
    assert stamps["OSM power source SHA256"] == "b" * 64
    assert "ODbL-1.0" in stamps["OSM power licence"]
    source = p.public_context.sources[-1]
    assert source.retrieved_on == "2026-10-01"
    assert source.transformation_version == "first_vertex_v1"


def test_old_and_new_reports_are_served_verbatim_without_context_recomputation(
    session, monkeypatch
):
    p = _assemble(session)
    old = p.model_dump(exclude={"public_context"})
    new = enrich_public_context(GeographySession(near()), p, reference()).model_dump()
    app = FastAPI()
    app.include_router(reports.router)
    app.dependency_overrides[reports.get_session] = lambda: session
    with TestClient(app) as client:
        for stored in (old, new):
            monkeypatch.setattr(reports, "get_payload", lambda *args, result=stored: result)
            assert client.get("/reports/test").json() == stored


def test_partial_release_configuration_fails_closed(monkeypatch):
    for name in ("SNAPSHOT", "ROOT", "SHA256"):
        monkeypatch.delenv("REPORT_PUBLIC_REFERENCE_" + name, raising=False)
    assert load_report_reference() is None
    monkeypatch.setenv("REPORT_PUBLIC_REFERENCE_SNAPSHOT", "missing.json")
    with pytest.raises(ValueError, match="All three"):
        load_report_reference()


def test_assembler_carries_context_without_changing_demand_or_economics(session, monkeypatch):
    from app.domain.report import public_context

    baseline = _assemble(session)
    monkeypatch.setattr(public_context, "nearest_power", lambda *args, **kwargs: near())
    enriched = _assemble(session, public_reference=reference())
    assert enriched.public_context.snapshot_sha256 == "a" * 64
    assert enriched.financials == baseline.financials
    assert enriched.predicted == baseline.predicted
    assert enriched.verdict == baseline.verdict


@pytest.mark.parametrize("lat,lng", [(91, 0), (0, 181), (float("nan"), 0)])
def test_invalid_site_points_refused_before_a_query(lat, lng):
    db = GeographySession()
    with pytest.raises(ValueError, match="EPSG"):
        nearest_power(db, reference(), lat=lat, lng=lng)
    assert db.calls == []


@pytest.mark.parametrize("metadata_value", [None, False, 42, {"url": "unexpected"}])
def test_nullable_source_metadata_is_preserved_or_refused(session, metadata_value):
    public_reference = reference()
    public_reference._snapshot["datasets"]["osm_power"]["metadata"]["licence_url"] = metadata_value
    db = GeographySession()
    payload = _assemble(session)
    if metadata_value is None:
        enriched = enrich_public_context(db, payload, public_reference)
        assert enriched.public_context.sources[-1].licence_url is None
    else:
        with pytest.raises(ValueError, match="metadata must be text or null"):
            enrich_public_context(db, payload, public_reference)
        assert db.calls == []
