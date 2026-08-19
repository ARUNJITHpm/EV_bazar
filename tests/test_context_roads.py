"""PART 2.1 - the road parse over fixture Overpass bodies. Pure.

The geometry is arranged so the answers are checkable by hand: the site sits
at (8.567, 76.873); one trunk way runs east-west 40 m to its north; a
secondary way crosses it at a shared node ~117 m away.
"""

from __future__ import annotations

from typing import Any

from app.domain.context.roads import RoadFeatures, build_roads_query, parse_roads

LAT, LNG = 8.567, 76.873
#: ~40 m of latitude.
DLAT_40M = 40 / 111_195
#: ~300 m of latitude.
DLAT_300M = 300 / 111_195


def _fixture() -> dict[str, Any]:
    a = {"lat": LAT + DLAT_40M, "lon": LNG - 0.001}
    b = {"lat": LAT + DLAT_40M, "lon": LNG + 0.001}
    c = {"lat": LAT - DLAT_300M, "lon": LNG + 0.001}
    return {
        "elements": [
            {
                "type": "way",
                "id": 1,
                "nodes": [1, 2],
                "geometry": [a, b],
                "tags": {"highway": "trunk", "ref": "NH 66", "oneway": "yes"},
            },
            {
                "type": "way",
                "id": 2,
                "nodes": [2, 3],
                "geometry": [b, c],
                "tags": {"highway": "secondary", "name": "Service Road"},
            },
        ]
    }


def test_nearest_major_road_with_distance_and_class() -> None:
    f = parse_roads(_fixture(), LAT, LNG)
    assert f.nearest_class == "trunk"
    assert f.nearest_ref == "NH 66"
    assert f.distance_m is not None and 35 <= f.distance_m <= 45


def test_carriageway_pair_reads_as_divided() -> None:
    """OSM maps a divided road as paired oneway ways - the flag that says the
    median-access penalty MAY apply (PLAN 2.1)."""
    assert parse_roads(_fixture(), LAT, LNG).divided is True


def test_shared_node_within_radius_counts_as_a_junction() -> None:
    f = parse_roads(_fixture(), LAT, LNG)
    assert f.junction_count_500m == 1


def test_ties_break_toward_the_bigger_road() -> None:
    body = _fixture()
    # Put a secondary at the same distance as the trunk: the trunk must win.
    body["elements"].append(
        {
            "type": "way",
            "id": 3,
            "nodes": [4, 5],
            "geometry": [
                {"lat": LAT + DLAT_40M, "lon": LNG - 0.002},
                {"lat": LAT + DLAT_40M, "lon": LNG + 0.002},
            ],
            "tags": {"highway": "secondary"},
        }
    )
    assert parse_roads(body, LAT, LNG).nearest_class == "trunk"


def test_empty_body_yields_all_none_never_a_guess() -> None:
    f = parse_roads({"elements": []}, LAT, LNG)
    assert f == RoadFeatures(None, None, None, None, junction_count_500m=0)


def test_malformed_body_yields_none_features() -> None:
    """Real responses will be missing data (AGENTS.md null-handling rule)."""
    assert parse_roads(None, LAT, LNG).nearest_class is None
    assert parse_roads({"remark": "timeout"}, LAT, LNG).distance_m is None
    assert parse_roads({"elements": [{"type": "way"}]}, LAT, LNG).nearest_class is None


def test_query_names_the_major_classes_and_the_point() -> None:
    q = build_roads_query(LAT, LNG)
    assert "trunk" in q and "primary" in q
    assert f"{LAT}" in q and f"{LNG}" in q
    assert "out body geom" in q
