"""Offline acquisition regressions; run with the isolated osmium tool environment."""

import csv
import hashlib

import pytest

from scripts.extract_public_osm_power import extract

osmium = pytest.importorskip("osmium")


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.osm.pbf"
    header = osmium.io.Header()
    header.set("osmosis_replication_timestamp", "2026-09-30T20:22:42Z")
    with osmium.SimpleWriter(str(path), header=header) as writer:
        writer.add_node(
            osmium.osm.mutable.Node(id=1, location=(76.0, 10.0), tags={"power": "transformer"})
        )
        writer.add_node(osmium.osm.mutable.Node(id=2, location=(77.0, 11.0)))
        writer.add_node(
            osmium.osm.mutable.Node(id=3, location=(78.0, 12.0), tags={"power": "tower"})
        )
        writer.add_way(
            osmium.osm.mutable.Way(
                id=10, nodes=[2, 3], tags={"power": "substation", "voltage": "110000;33000"}
            )
        )
        writer.add_way(osmium.osm.mutable.Way(id=11, nodes=[999], tags={"power": "substation"}))
        writer.add_relation(osmium.osm.mutable.Relation(id=12, tags={"power": "substation"}))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_mapping_nulls_source_vertex_and_unresolved_objects(source, tmp_path):
    path, digest = source
    output = tmp_path / "candidate.csv"
    audit = extract(path, output, expected_sha256=digest)
    with output.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert [r["osm_id"] for r in rows] == ["node/1", "way/10"]
    assert rows[0]["voltage"] == rows[0]["lgd_code"] == ""
    assert rows[1]["lat"] == "11.0" and rows[1]["lon"] == "77.0"
    assert rows[1]["voltage"] == "110000;33000"
    assert rows[1]["point_derivation"] == "representative_point"
    assert audit["statistics"]["relations_excluded"] == 1
    assert audit["statistics"]["unresolved_ways_excluded"] == 1
    assert audit["extract_timestamp"] == "2026-09-30T20:22:42Z"


def test_changed_archive_refused_before_output(source, tmp_path):
    path, _ = source
    output = tmp_path / "candidate.csv"
    with pytest.raises(ValueError, match="checksum mismatch"):
        extract(path, output, expected_sha256="0" * 64)
    assert not output.exists()
