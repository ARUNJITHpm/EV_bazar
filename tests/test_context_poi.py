"""PART 2.2 - POI gravity and the dwell-anchor score, over fixtures. Pure."""

from __future__ import annotations

from typing import Any

from app.domain.context.poi import build_poi_query, parse_pois

LAT, LNG = 8.567, 76.873


def _at(metres: float) -> dict[str, float]:
    return {"lat": LAT + metres / 111_195, "lon": LNG}


def _fixture() -> dict[str, Any]:
    return {
        "elements": [
            {"type": "node", "id": 1, **_at(200), "tags": {"amenity": "cafe", "name": "Chai Stop"}},
            {
                "type": "way",
                "id": 2,
                "center": _at(800),
                "tags": {"shop": "mall", "name": "Technopark Mall"},
            },
            {
                "type": "node",
                "id": 3,
                **_at(900),
                "tags": {"tourism": "hotel", "name": "Karthika Park"},
            },
            {"type": "node", "id": 4, **_at(2500), "tags": {"amenity": "fuel"}},
        ]
    }


def test_counts_bucket_into_the_three_rings() -> None:
    g = parse_pois(_fixture(), LAT, LNG)
    assert g is not None
    assert g.counts[500] == {**dict.fromkeys(g.counts[500], 0), "food": 1}
    assert g.counts[1000]["food"] == 1
    assert g.counts[1000]["mall"] == 1
    assert g.counts[1000]["hotel"] == 1
    assert g.counts[1000]["fuel"] == 0
    assert g.counts[3000]["fuel"] == 1


def test_dwell_score_weights_what_holds_a_driver() -> None:
    """A mall anchors a fast-charge session; a fuel stop holds nobody. The
    2.5 km fuel station is outside the dwell ring anyway."""
    g = parse_pois(_fixture(), LAT, LNG)
    assert g is not None
    assert g.dwell_anchor_score == 5.5  # mall 3.0 + hotel 1.5 + cafe 1.0
    assert g.dwell_anchors[0] == "Technopark Mall"
    assert "fuel" not in g.dwell_anchors


def test_duplicate_elements_from_the_union_query_count_once() -> None:
    body = _fixture()
    body["elements"].append(body["elements"][0])
    g = parse_pois(body, LAT, LNG)
    assert g is not None
    assert g.counts[500]["food"] == 1


def test_empty_body_is_a_true_zero_not_an_unknown() -> None:
    g = parse_pois({"elements": []}, LAT, LNG)
    assert g is not None
    assert all(count == 0 for ring in g.counts.values() for count in ring.values())
    assert g.dwell_anchor_score == 0.0


def test_malformed_body_is_none_never_fake_zeros() -> None:
    assert parse_pois(None, LAT, LNG) is None
    assert parse_pois({"remark": "timeout"}, LAT, LNG) is None


def test_query_covers_every_category_at_the_outer_ring() -> None:
    q = build_poi_query(LAT, LNG)
    for fragment in ('"amenity"', '"shop"', '"tourism"', '"office"'):
        assert fragment in q
    assert "3000" in q and "out center" in q
