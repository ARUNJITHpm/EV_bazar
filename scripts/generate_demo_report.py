"""Generate the demonstration report - Kazhakkoottam-Technopark, NH-66.

    uv run python -m scripts.generate_demo_report            # dry: assemble + print
    uv run python -m scripts.generate_demo_report --write    # persist to the DB
    uv run python -m scripts.generate_demo_report --write --offline  # skip Overpass

The one report that exists before the assess pipeline does, so the report
surface can be seen working end to end on real inputs: live VAHAN and
competitor rows, the seeded KSERC tariff, roads and POIs fetched from
Overpass at generation time (degrading to "pending" facts offline), the
synthetic_v0 demand band, and every financial number from the real ROI
engine.

What --write persists, in order:

* the demo ``sites`` row (insert-only - sites are append-only; an existing
  row is reused, never updated);
* a ``predictions`` row flagged ``is_demo`` (AGENTS.md rule 5: demo runs are
  flagged, never skipped);
* the ``reports`` row - the stored JSONB payload the frontend serves. The
  demo id may be regenerated in place; that exception is stated in the
  reports model.
"""

from __future__ import annotations

import argparse
import sys
import uuid

import httpx

from app.db import SessionLocal
from app.domain.context.overpass import OverpassClient
from app.domain.context.poi import PoiGravity, fetch_poi_gravity
from app.domain.context.roads import RoadFeatures, fetch_road_features
from app.domain.demand.synthetic import load_weights
from app.domain.report.assemble import CpoOption, ReportSpec, assemble_report
from app.domain.report.store import save_report
from app.domain.roi.engine import Capex, CpoTerms
from app.models.predictions import Prediction
from app.models.site import Site

REPORT_ID = "KL-TVM-DEMO-001"
LAT, LNG = 8.567, 76.873
DISTRICT_CODE, STATE_CODE = 565, 32  # Thiruvananthapuram, Kerala

SPEC = ReportSpec(
    report_id=REPORT_ID,
    demo=True,
    name="Kazhakkoottam–Technopark stretch",
    line="NH-66 · Thiruvananthapuram, Kerala",
    district_name="Thiruvananthapuram",
    lgd_district_code=DISTRICT_CODE,
    lgd_state_code=STATE_CODE,
    lat=LAT,
    lng=LNG,
    archetype="urban_office_arterial",
    archetype_hand_assigned=True,
    connectors=2,
    rated_kw_each=60.0,
    selling_paise_per_kwh=2200,
    capex=Capex(
        hardware_paise=120_000_000,
        civil_paise=30_000_000,
        transformer_paise=20_000_000,
        discom_connection_paise=10_000_000,
        signage_canopy_paise=2_000_000,
    ),
    rent_paise_per_month=4_000_000,
    anchor_kwh_year=200_000.0,
    anchor_paise_per_kwh=1800,
    # Terms are PLACEHOLDERS until cpo_terms lands (Part 6) - the payload's
    # ledger says so. Our own network under the same rules as everyone else.
    cpo_options=(
        CpoOption("chargeMOD", True, CpoTerms(0.10, 0, 100_000), True),
        CpoOption("GO EC", False, CpoTerms(0.12, 0, 150_000), True),
        CpoOption("Statiq", False, CpoTerms(0.15, 0, 200_000), True),
        CpoOption("Self-operate", False, CpoTerms(), False),
    ),
)


def _ensure_demo_site(session: object) -> uuid.UUID:
    """The demo's ``sites`` row. Insert-only: sites are append-only."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    assert isinstance(session, Session)
    normalised = "demo:kazhakkoottam-technopark-nh66"
    existing = session.execute(
        select(Site).where(Site.normalised_input == normalised)
    ).scalar_one_or_none()
    if existing is not None:
        return existing.site_id

    site = Site(
        raw_input="Kazhakkoottam–Technopark stretch, NH-66, Thiruvananthapuram (demo)",
        normalised_input=normalised,
        lat=LAT,
        lng=LNG,
        lgd_state_code=STATE_CODE,
        lgd_district_code=DISTRICT_CODE,
        geocode_source="manual",
        geocode_confidence="high",
        district_method="contained",
        reasons="demo pin, placed by hand; district by construction",
        data_tier=1,
    )
    session.add(site)
    session.flush()
    return site.site_id


def main() -> int:
    # OSM names arrive in Malayalam; a cp1252 Windows console must not crash
    # the run over a road name.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="persist site/prediction/report")
    parser.add_argument("--offline", action="store_true", help="skip the Overpass fetches")
    args = parser.parse_args()

    roads: RoadFeatures | None = None
    pois: PoiGravity | None = None
    if not args.offline:
        client = OverpassClient()
        try:
            roads = fetch_road_features(client, LAT, LNG)
            pois = fetch_poi_gravity(client, LAT, LNG)
        except (httpx.HTTPError, ValueError) as exc:
            print(f"overpass unavailable ({exc}) - road/POI facts will read 'pending'")

    weights = load_weights()
    with SessionLocal() as session:
        assembled = assemble_report(session, SPEC, weights, roads=roads, pois=pois)
        p = assembled.payload
        band = assembled.prediction

        print(f"report        {p.report_id} (demo)")
        print(f"verdict       {p.verdict.value}  ({p.margin_of_safety_pp:+.1f} pp at P10)")
        print(
            f"breakeven     {p.breakeven.utilisation:.1%}  "
            f"predicted {p.predicted.p10:.1%}–{p.predicted.p90:.1%} ({band.model_version})"
        )
        print(f"competitors   {p.competitors.within_3km} within 3 km")
        if roads is not None and roads.nearest_ref:
            print(f"road          {roads.nearest_ref} at {roads.distance_m} m")
        if pois is not None:
            print(f"dwell         score {pois.dwell_anchor_score}: {', '.join(pois.dwell_anchors)}")

        if not args.write:
            print("dry run - rerun with --write to persist")
            return 0

        site_id = _ensure_demo_site(session)
        session.add(
            Prediction(
                site_id=site_id,
                model_version=band.model_version,
                economics_version=p.provenance[0].value,
                predicted_p10=band.kwh_per_connector_day_p10,
                predicted_p50=band.kwh_per_connector_day_p50,
                predicted_p90=band.kwh_per_connector_day_p90,
                is_demo=True,
            )
        )
        save_report(
            session,
            p,
            site_id=site_id,
            model_version=band.model_version,
            economics_version=p.provenance[0].value,
        )
        session.commit()
        print(f"persisted: site {site_id}, prediction (is_demo), report {REPORT_ID}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
