"""Peer comparison hides itself below ten comparable stations."""

from __future__ import annotations

from app.domain.owner.peers import (
    MIN_PEERS,
    PeerRow,
    cohort_size,
    cohort_stat,
    percentile_rank,
)


def _peers(n: int, age: int = 6, base: float = 10.0) -> list[PeerRow]:
    return [PeerRow(station_id=i, age_months=age, kwh_per_kw=base + i) for i in range(n)]


def test_threshold_is_ten() -> None:
    assert MIN_PEERS == 10


def test_nine_peers_show_nothing() -> None:
    rows = _peers(9)
    assert cohort_size(rows, 6) == 9
    assert cohort_stat(rows, 6) is None
    assert percentile_rank(12.0, rows, 6) is None


def test_ten_peers_show_a_band_and_the_sample_size() -> None:
    rows = _peers(10)
    stat = cohort_stat(rows, 6)
    assert stat is not None
    assert stat.n == 10
    assert stat.p10 < stat.p50 < stat.p90
    assert percentile_rank(12.5, rows, 6) == 30.0  # ahead of 10, 11, 12


def test_a_peer_counts_once_however_many_bills_it_has() -> None:
    rows = _peers(9) + [PeerRow(99, 5, 20.0), PeerRow(99, 6, 21.0), PeerRow(99, 7, 22.0)]
    assert cohort_size(rows, 6) == 10


def test_similar_age_means_within_three_months() -> None:
    rows = _peers(9) + [PeerRow(50, 9, 15.0)]
    assert cohort_size(rows, 6) == 10  # 3 months apart: in
    rows = _peers(9) + [PeerRow(50, 10, 15.0)]
    assert cohort_size(rows, 6) == 9  # 4 months apart: out


def test_the_nearest_bill_of_a_peer_is_the_one_used() -> None:
    # Station 0 has a low bill at age 4 and a high one at age 6; at age 6 only the
    # high one counts.
    others = [PeerRow(i, 6, 100.0) for i in range(1, 10)]
    rows = [PeerRow(0, 4, 5.0), PeerRow(0, 6, 100.0), *others]
    stat = cohort_stat(rows, 6)
    assert stat is not None
    assert stat.n == 10
    assert stat.p10 == 100.0


def test_empty_cohort() -> None:
    assert cohort_size([], 3) == 0
    assert cohort_stat([], 3) is None
