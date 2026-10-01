"""Offline, deterministic OSM power extraction; no HTTP, DB or runtime scraping.

Install osmium==4.2.0 in an isolated tool environment. Archive/checksum the PBF
and publisher's dated entry first. Writes a candidate outside data/public;
review and activate separately through the shared validator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def extract(source: Path, output: Path, *, expected_sha256: str) -> dict:
    if output.resolve().is_relative_to(Path(__file__).resolve().parents[1] / "data/public"):
        raise ValueError("Extract outside data/public and review before activation")
    import osmium

    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise ValueError("OSM source checksum mismatch")
    reader = osmium.io.Reader(str(source))
    try:
        timestamp = reader.header().get("osmosis_replication_timestamp")
    finally:
        reader.close()
    if not timestamp:
        raise ValueError("OSM extract timestamp missing")
    extract_date = timestamp[:10]
    rows: list[dict] = []
    ways: list[tuple] = []
    wanted: set[int] = set()
    statistics = {
        "nodes": 0,
        "ways": 0,
        "relations_excluded": 0,
        "invalid_nodes_excluded": 0,
        "unresolved_ways_excluded": 0,
    }

    class Features(osmium.SimpleHandler):
        def node(self, node: osmium.osm.Node) -> None:
            kind = node.tags.get("power")
            if kind not in ("substation", "transformer"):
                return
            if not node.location.valid():
                statistics["invalid_nodes_excluded"] += 1
                return
            rows.append(
                {
                    "osm_id": f"node/{node.id}",
                    "kind": kind,
                    "voltage": node.tags.get("voltage", ""),
                    "lat": node.location.lat,
                    "lon": node.location.lon,
                    "lgd_code": "",
                    "extract_date": extract_date,
                    "point_derivation": "node",
                }
            )
            statistics["nodes"] += 1

        def way(self, way: osmium.osm.Way) -> None:
            kind = way.tags.get("power")
            if kind not in ("substation", "transformer"):
                return
            if not way.nodes:
                statistics["unresolved_ways_excluded"] += 1
                return
            # A source vertex is a reproducible representative point. It is
            # not a surveyed equipment center, centroid or connection location.
            node_id = way.nodes[0].ref
            wanted.add(node_id)
            ways.append((way.id, kind, way.tags.get("voltage", ""), node_id))

        def relation(self, relation: osmium.osm.Relation) -> None:
            if relation.tags.get("power") in ("substation", "transformer"):
                statistics["relations_excluded"] += 1

    Features().apply_file(str(source))
    locations: dict[int, tuple[float, float]] = {}

    class Locations(osmium.SimpleHandler):
        def node(self, node: osmium.osm.Node) -> None:
            if node.id in wanted and node.location.valid():
                locations[node.id] = (node.location.lat, node.location.lon)

    Locations().apply_file(str(source))
    for identifier, kind, voltage, node_id in ways:
        location = locations.get(node_id)
        if location is None:
            statistics["unresolved_ways_excluded"] += 1
            continue
        rows.append(
            {
                "osm_id": f"way/{identifier}",
                "kind": kind,
                "voltage": voltage,
                "lat": location[0],
                "lon": location[1],
                "lgd_code": "",
                "extract_date": extract_date,
                "point_derivation": "representative_point",
            }
        )
        statistics["ways"] += 1
    rows.sort(key=lambda row: row["osm_id"])
    if len({row["osm_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate OSM feature IDs")
    if not rows:
        raise ValueError("No power observations in source")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    audit = {
        "source_sha256": expected_sha256,
        "extract_timestamp": timestamp,
        "rows": len(rows),
        "statistics": statistics,
        "lgd_mapping": "unresolved; no boundary inference",
        "point_derivation": "nodes as mapped; ways use first mapped perimeter vertex",
        "transformation_version": "osm_power_first_vertex_v1",
    }
    output.with_suffix(".audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if (Path(__file__).resolve().parents[1] / "data/public") in args.output.resolve().parents:
        raise SystemExit("Extract outside data/public and review before activation")
    print(json.dumps(extract(args.pbf, args.output, expected_sha256=args.sha256), indent=2))


if __name__ == "__main__":
    main()
