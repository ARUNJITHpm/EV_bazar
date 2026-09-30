"""Pure parts of the charging-network backfill (scripts/backfill_network.py).

The database steps were run against Postgres inside a rolled-back transaction
when the script was written; what is pinned here is the logic that decides what
gets written.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.backfill_network import (
    ConnectorPlan,
    _find_station,
    connector_format,
    content_hash,
    current_type,
    plan_connectors,
    slug,
    standard_of,
)


def test_each_physical_connector_becomes_one_plan() -> None:
    plans = plan_connectors(
        [
            {"type": "CCS2", "power_kw": 60, "quantity": 2},
            {"type": "Type2", "power_kw": 7.4, "quantity": 1},
        ],
        3,
        60,
    )
    assert plans == [
        ConnectorPlan("CCS2", 60.0, None),
        ConnectorPlan("CCS2", 60.0, None),
        ConnectorPlan("Type2", 7.4, None),
    ]


def test_a_missing_or_zero_quantity_is_one_connector() -> None:
    assert len(plan_connectors([{"type": "CCS2", "power_kw": 30}], None, None)) == 1
    assert len(plan_connectors([{"type": "CCS2", "power_kw": 30, "quantity": 0}], None, None)) == 1


def test_with_no_breakdown_the_point_count_stands_in() -> None:
    assert plan_connectors(None, 2, 22.0) == [ConnectorPlan(None, 22.0, None)] * 2
    assert plan_connectors([], 0, 22.0) == []
    assert plan_connectors(None, None, None) == []


def test_unknown_power_is_none_never_zero() -> None:
    (plan,) = plan_connectors([{"type": None, "power_kw": None, "quantity": 1}], None, None)
    assert plan.power_kw is None
    assert plan_connectors([{"type": "AC", "power_kw": 0}], None, None)[0].power_kw is None


@pytest.mark.parametrize("raw", [None, "", "  ", "null", "Unknown", "NONE"])
def test_a_connector_type_the_source_did_not_give_is_none(raw: object) -> None:
    assert standard_of(raw) is None


def test_a_long_connector_type_is_kept_whole_within_the_column() -> None:
    assert standard_of("Type 2 (Tethered Connector)") == "Type 2 (Tethered Connector)"
    assert len(standard_of("x" * 90) or "") == 48


@pytest.mark.parametrize(
    ("standard", "expected"),
    [
        ("CCS2", "DC"),
        ("CCS (Type 2)", "DC"),  # DC even though it says Type 2
        ("GB/T", "DC"),
        ("CHAdeMO", "DC"),
        ("Type2", "AC"),
        ("Type 2 (Socket Only)", "AC"),
        ("15A", "AC"),
        ("IEC 60309 3-pin", "AC"),
        ("Type6", None),  # not something to guess at
        (None, None),
    ],
)
def test_current_type_from_the_standard(standard: str | None, expected: str | None) -> None:
    assert current_type(standard) == expected


def test_tethered_is_a_cable_and_socket_is_a_socket() -> None:
    assert connector_format("Type 2 (Tethered Connector)") == "cable"
    assert connector_format("Type 2 (Socket Only)") == "socket"
    assert connector_format("CCS2") is None


def test_slug() -> None:
    assert slug("Tata Power EZ Charge") == "tata-power-ez-charge"
    assert slug("  ChargeMOD (IN) ") == "chargemod-in"


def test_content_hash_ignores_key_order_and_sees_changes() -> None:
    assert content_hash({"a": 1, "b": [1, 2]}) == content_hash({"b": [1, 2], "a": 1})
    assert content_hash({"a": 1}) != content_hash({"a": 2})


def _row(id_: int, source: str, source_id: str, lat: float, lng: float, op: str | None):  # noqa: ANN202
    return SimpleNamespace(
        id=id_, source=source, source_id=source_id, lat=lat, lng=lng, operator=op
    )


def _charger(apps: list[tuple[str, str]], lat: float, lng: float, cpo: str | None) -> dict:  # type: ignore[type-arg]
    return {
        "lat": lat,
        "lng": lng,
        "cpo": cpo,
        "listed_in": [{"app": a, "app_id": i} for a, i in apps],
    }


def test_a_charger_is_found_by_any_app_id_it_is_listed_under() -> None:
    row = _row(1, "zeon", "77", 9.0, 76.0, "Zeon Charging")
    c = _charger([("pulse", "9"), ("zeon", "77")], 9.5, 76.5, "Zeon")  # far away: id wins
    assert _find_station(c, {("zeon", "77"): row}, [row]) is row


def test_otherwise_the_nearest_same_operator_row_within_60_m() -> None:
    near = _row(1, "open_charge_map", "a", 9.00027, 76.0, "ChargeMOD (IN)")  # ~30 m
    nearer = _row(2, "open_charge_map", "b", 9.00009, 76.0, "ChargeMOD")  # ~10 m
    other_op = _row(3, "open_charge_map", "c", 9.0, 76.0, "Statiq")  # nearest of all, wrong company
    c = _charger([("pulse", "9")], 9.0, 76.0, "ChargeMOD")
    assert _find_station(c, {}, [near, nearer, other_op]) is nearer


def test_nothing_is_matched_beyond_60_m_or_across_operators() -> None:
    far = _row(1, "open_charge_map", "a", 9.001, 76.0, "ChargeMOD")  # ~111 m
    other = _row(2, "open_charge_map", "b", 9.0, 76.0, "Statiq")
    c = _charger([("pulse", "9")], 9.0, 76.0, "ChargeMOD")
    assert _find_station(c, {}, [far, other]) is None


def test_a_row_with_no_operator_can_match_on_place_alone() -> None:
    row = _row(1, "open_charge_map", "a", 9.0, 76.0, None)
    assert _find_station(_charger([("pulse", "9")], 9.0, 76.0, "ChargeMOD"), {}, [row]) is row
