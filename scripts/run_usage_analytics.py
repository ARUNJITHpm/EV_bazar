"""Offline private owner analytics. Refuses unreviewed inputs; never prints records."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.domain.analytics.inputs import VERSIONS, Bill, Station
from app.domain.analytics.ledger import PredictionLedger
from app.domain.analytics.publication import PUBLIC_FIELDS
from app.domain.analytics.runner import run_private
from app.models.owner import OwnerBill, OwnerStationRecord
from app.models.site import Site

ROOT = Path(__file__).resolve().parents[1]


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stations: list[Station]
    charger_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    registration_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewed_full_calendar_bill_ids: list[int]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--month", required=True, type=dt.date.fromisoformat)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument(
        "--public-source-url", help="Verified HTTPS methodology URL, required to publish"
    )
    args = parser.parse_args()
    if args.month.day != 1:
        parser.error("Month must be its first calendar day")
    if args.publish and (
        not args.public_source_url
        or not args.public_source_url.startswith("https://")
        or "example.invalid" in args.public_source_url
    ):
        parser.error("Publication requires a verified HTTPS methodology source URL")
    private = (ROOT / "data/private/analytics").resolve()
    if private != (ROOT / "data/private/analytics").absolute():
        parser.error("Private analytics path cannot use symlinks or junctions")
    review_path = args.review.resolve()
    if not review_path.is_relative_to(private):
        parser.error("Reviewed inputs must stay in data/private/analytics")
    review = Review.model_validate_json(review_path.read_text(encoding="utf-8"))
    for dataset, expected in [
        ("public_chargers", review.charger_sha256),
        ("ev_registrations", review.registration_sha256),
    ]:
        path = ROOT / f"data/public/{dataset}/data.csv"
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            parser.error("Verified public input is absent or differs from the reviewed snapshot")
        metadata = json.loads((path.parent / "meta.json").read_text(encoding="utf-8"))
        if (
            metadata.get("fixture")
            or "example.invalid" in str(metadata)
            or not metadata.get("licence")
        ):
            parser.error("Fixture or unlicensed source is not eligible for a real run")
    with (ROOT / "data/public/public_chargers/data.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        public = list(csv.DictReader(handle))
    if {row["charger_id"] for row in public} != {station.public_id for station in review.stations}:
        parser.error("Review must match every physical station in the approved inventory")
    by_public = {row["charger_id"]: row for row in public}
    if any(
        int(by_public[station.public_id]["lgd_code"]) != station.lgd_code
        for station in review.stations
    ):
        parser.error("Reviewed LGD join differs from the approved inventory")
    from app.db import SessionLocal

    run_id = uuid.uuid4()
    with SessionLocal() as session:
        bills = []
        for station in review.stations:
            site = session.get(Site, station.site_id)
            if site is None or site.lgd_district_code != station.lgd_code:
                parser.error(
                    "A reviewed, resolved site mapping is required for prediction persistence"
                )
            if station.owner_station_id is None:
                continue
            owner = session.get(OwnerStationRecord, station.owner_station_id)
            if (
                owner is None
                or owner.consent_aggregate != station.consent
                or owner.meter_type != station.meter_type
            ):
                parser.error("Owner eligibility changed since the review")
            for bill in session.scalars(
                select(OwnerBill).where(OwnerBill.station_id == station.owner_station_id)
            ):
                # OwnerBill is inserted only after confirmation; created_at is
                # that confirmation time, not a guessed billing exposure date.
                confirmed = bill.created_at
                bills.append(
                    Bill(
                        station_id=station.owner_station_id,
                        month=bill.period,
                        kwh=bill.kwh,
                        confirmed_at=confirmed,
                        confirmed=True,
                        full_calendar_month_verified=bill.id
                        in review.reviewed_full_calendar_bill_ids,
                        correction_id=bill.id,
                    )
                )
        ledger = PredictionLedger(session, run_id, is_demo=False)
        report = private / str(run_id) / "validation.json"
        rows = run_private(review.stations, bills, args.month, ledger, report)
    candidate = private / str(run_id) / "aggregate_candidate.json"
    candidate.write_text(
        json.dumps({"versions": VERSIONS, "rows": rows}, allow_nan=False), encoding="utf-8"
    )
    if args.publish:
        destination = ROOT / "data/published"
        if destination.is_symlink() or (destination / "usage_estimates.csv").exists():
            parser.error("Refuse replacement: overlapping releases need a separate privacy review")
        # Failed groups contribute only a label and district/month, not counts.
        if not any(row["district_total_p50"] is not None for row in rows):
            parser.error("No district passed every publication gate; candidate stays private")
        destination.mkdir(parents=True, exist_ok=True)
        with (destination / "usage_estimates.csv").open(
            "x", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=PUBLIC_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        metadata = {
            "versions": VERSIONS,
            "run_id": str(run_id),
            "source": "Consented full-calendar-month owner observations "
            "and approved source inventory",
            "unit": "kWh per listed physical station per month; legacy kwh_per_charger field names",
            "note": "Not all chargers in the district; no private report "
            "or station record accompanies this artifact.",
            "source_hashes": {
                "public_chargers": review.charger_sha256,
                "ev_registrations": review.registration_sha256,
            },
            "is_demo": False,
            "privacy_gates": "usage_privacy_v1",
            "validation_passed": True,
            "licence": "CC BY 4.0",
            "retrieved_on": dt.date.today().isoformat(),
            "source_url": args.public_source_url,
        }
        (destination / "meta.json").write_text(
            json.dumps(metadata, allow_nan=False), encoding="utf-8"
        )
    print(
        "Offline run finished. Validation and candidates remain private "
        "unless publication gates pass."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Validation exceptions can include whole private input records. The
        # immutable private report carries diagnostics; stdout stays generic.
        print("Offline run refused. Check the private review and validation report locally.")
        raise SystemExit(1) from None
