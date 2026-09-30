"""Capture -> validate -> district resolve -> export -> optional inventory upsert.

    uv run python -m scripts.refresh_stations --states kerala tamilnadu
    uv run python -m scripts.refresh_stations --sources goec zeon --write
    uv run python -m scripts.refresh_stations --sources --csv chargemod stations.csv

Each run produces an immutable raw capture directory and an export/manifest.
No paid providers and no status polling. See STATION_PIPELINE.md.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import uuid
from functools import partial
from pathlib import Path

from app.domain.context.competitors import (
    CompetitorStationData,
    dedupe,
    fetch_goec,
    fetch_ocm,
    fetch_zeon,
    tile_bbox,
)
from app.domain.context.station_pipeline import (
    DEFAULT_STATES,
    STATE_BBOX,
    VERSION_STAMPS,
    CaptureClient,
    collect_source,
    coverage_gaps,
    export_rows,
    fetch_ncr_boundary,
    fetch_osm_states,
    locate_stations,
    persist_inventory_rows,
    read_station_csv,
)


def fetch_ocm_states(
    client: CaptureClient,
    api_key: str,
    base_url: str,
    states: list[str],
    grid: int,
) -> list[CompetitorStationData]:
    batch = []
    for state in dict.fromkeys(states):
        for box in tile_bbox(STATE_BBOX[state], rows=grid, cols=grid):
            result = fetch_ocm(client, api_key, bbox=box, max_results=500, base_url=base_url)
            if result.raw_count >= 500:
                raise ValueError("OCM tile hit cap; rerun with a finer --grid")
            batch.extend(result.stations)
    return batch


def fetch_direct(client: CaptureClient, source: str) -> list[CompetitorStationData]:
    fetcher = fetch_goec if source == "goec" else fetch_zeon
    return fetcher(client).stations


def write_csv_exports(directory: Path, rows: list[dict], columns: list[str]) -> None:
    """Combined export and convenient source-preserving per-state/per-CPO views."""
    groups: dict[Path, list[dict]] = {directory / "stations.csv": rows}
    for row in rows:
        for folder, name in (
            ("by_state", row["state"] or "needs_geography_review"),
            ("by_cpo", row["canonical_operator"] or "unresolved_operator"),
        ):
            slug = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
            groups.setdefault(directory / folder / f"{slug}.csv", []).append(row)
    for path, records in groups.items():
        path.parent.mkdir(exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", nargs="+", choices=sorted(STATE_BBOX), default=DEFAULT_STATES)
    parser.add_argument(
        "--sources",
        nargs="*",
        choices=["ocm", "goec", "zeon", "osm"],
        default=["ocm", "goec", "zeon"],
    )
    parser.add_argument("--csv", nargs=2, action="append", metavar=("SOURCE", "FILE"))
    parser.add_argument("--out", type=Path, default=Path("data/station_inventory"))
    parser.add_argument("--grid", type=int, default=3)
    parser.add_argument("--max-requests", type=int, default=100)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--stale-days", type=int, default=30)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--osm-server", choices=["primary", "private-coffee"], default="primary")
    args = parser.parse_args(argv)
    if args.grid < 1 or args.max_requests < 1 or args.delay < 0 or args.stale_days < 1:
        parser.error("grid, request budget and stale days must be positive; delay >= 0")
    if not args.sources and not args.csv:
        parser.error("select sources or supply --csv SOURCE FILE")

    now = dt.datetime.now(dt.UTC)
    directory = args.out / f"{now:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=False)
    outcomes: dict = {}
    stations: list[CompetitorStationData] = []
    manifest = {
        **VERSION_STAMPS,
        "fetched_at": now.isoformat(),
        "states": args.states,
        "sources": outcomes,
        "database_write": "not_attempted",
        "notes": [
            "Inventory only; no live occupancy or proof of current operation.",
            "Delhi-NCR uses the archived official RP-2021 subregion geometry when selected.",
            "No missing listing is interpreted as closed or deleted.",
        ],
    }
    with CaptureClient(
        directory / "raw", max_requests=args.max_requests, delay_seconds=args.delay
    ) as client:
        ncr_boundary = None
        if "delhincr" in args.states:
            client.source = "ncr_boundary"
            try:
                ncr_boundary = fetch_ncr_boundary(client)
                manifest["ncr_boundary"] = "official_RP2021_subregions_20250123_service"
            except (ValueError, RuntimeError, KeyError, TypeError) as error:
                manifest["ncr_boundary"] = {"status": "failed", "error_type": type(error).__name__}
            except Exception as error:
                manifest["ncr_boundary"] = {"status": "failed", "error_type": type(error).__name__}
            if ncr_boundary is None:
                (directory / "manifest.json").write_text(
                    json.dumps(manifest, indent=2), encoding="utf-8"
                )
                print(f"NCR boundary unavailable; refusing to claim full NCR coverage. {directory}")
                return 2
        for source in dict.fromkeys(args.sources):
            client.source = source
            if source == "ocm":
                from app.config import get_settings

                config = get_settings().open_charge_map
                if not config.enabled:
                    outcomes[source] = {"status": "blocked", "reason": "OCM key not configured"}
                    continue

                assert config.api_key is not None
                stations.extend(
                    collect_source(
                        source,
                        partial(
                            fetch_ocm_states,
                            client,
                            config.api_key,
                            config.base_url,
                            args.states,
                            args.grid,
                        ),
                        outcomes,
                    )
                )
            elif source == "osm":
                stations.extend(
                    collect_source(
                        source,
                        partial(
                            fetch_osm_states,
                            client,
                            args.states,
                            url=(
                                "https://overpass.private.coffee/api/interpreter"
                                if args.osm_server == "private-coffee"
                                else "https://overpass-api.de/api/interpreter"
                            ),
                        ),
                        outcomes,
                    )
                )
            else:
                stations.extend(
                    collect_source(source, partial(fetch_direct, client, source), outcomes)
                )

        for index, (source, filename) in enumerate(args.csv or []):
            path = Path(filename)
            # Archive supplied bytes before interpreting them, with a distinct capture identity.
            key = f"csv:{index}:{source}"
            try:
                body = path.read_bytes()
            except OSError as error:
                outcomes[key] = {"status": "failed", "error_type": type(error).__name__}
                continue
            archive = directory / f"input-{index:02d}.csv"
            with archive.open("xb") as stream:
                stream.write(body)
            stations.extend(
                collect_source(key, partial(read_station_csv, archive, source=source), outcomes)
            )
            outcomes[key].update(file=archive.name, sha256=hashlib.sha256(body).hexdigest())
        manifest["request_count"] = client.requests_sent

    # Save outcomes even when the reference database is unavailable.
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    stations = dedupe(stations)
    if not stations:
        print(f"No stations accepted. Source outcomes: {manifest_path}")
        return 2

    try:
        from app.db import SessionLocal

        with SessionLocal() as session:
            rows, selected = export_rows(
                stations,
                locate_stations(session, stations),
                states=args.states,
                fetched_at=now,
                stale_days=args.stale_days,
                ncr_boundary=ncr_boundary,
            )
            export = directory / "stations.json"
            export.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
            columns = [
                "source",
                "source_id",
                "name",
                "operator",
                "canonical_operator",
                "latitude",
                "longitude",
                "state",
                "district",
                "lgd_state_code",
                "lgd_district_code",
                "boundary_vintage",
                "resolution",
                "fetched_at",
                "source_last_status_update",
                "freshness",
                "source_age_days",
                "in_selected_states",
                "target_region",
                *VERSION_STAMPS,
            ]
            write_csv_exports(directory, rows, columns)
            manifest.update(
                exported_rows=len(rows),
                accepted_for_db=len(selected),
                geography_review=sum(r["resolution"] != "contained" for r in rows),
                coverage=coverage_gaps(rows, args.states),
            )
            if args.write:
                count = persist_inventory_rows(session, rows)
                session.commit()
                manifest.update(database_write="committed", upserted=count)
            else:
                manifest["database_write"] = "disabled"
    except Exception as error:
        # Keep captures; do not print DB connection strings from exception messages.
        manifest.update(database_write="failed", error_type=type(error).__name__)
        print(f"Resolution/storage failed ({type(error).__name__}); captures preserved.")
        return 2
    finally:
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Run archive: {directory}")
    print(f"Exported {len(rows)} source rows, {len(selected)} in selected states.")
    return 0 if all(s["status"] == "ok" for s in outcomes.values()) else 2


if __name__ == "__main__":
    sys.exit(main())
