"""The fold behind report section 06. Pure - the query is the DB's half.

Two properties matter here and nothing else does:

  * the same physical station seen through two feeds is ONE station, or every
    network we cover well looks twice its size;
  * a name we cannot place is dropped rather than bucketed, because a count
    beside a name nobody can act on is worse than no count.
"""

from __future__ import annotations

from app.domain.cpo.presence import StationRow, fold_presence

#: A point and its immediate neighbours, in degrees. ~20 m apart is the same
#: station reported twice; ~200 m apart is two stations.
LAT, LNG = 8.5000, 76.8700
SAME_STATION = (8.50018, 76.87018)
NEXT_STREET = (8.5018, 76.8718)


def row(operator, lat=LAT, lng=LNG, *, district=True, state=True, near=True, wide=True):
    return StationRow(
        operator=operator,
        lat=lat,
        lng=lng,
        in_district=district,
        in_state=state,
        within_near=near,
        within_wide=wide,
    )


def test_one_station_seen_through_two_feeds_is_counted_once():
    # Open Charge Map says "Zeon Charging"; zeoncharging.com says "Zeon". Both
    # rows are kept upstream on purpose, and both describe one charger.
    out = fold_presence([row("Zeon Charging"), row("Zeon", *SAME_STATION)])
    assert set(out) == {"Zeon"}
    assert out["Zeon"].own_within_3km == 1
    assert out["Zeon"].stations_district == 1


def test_two_real_stations_stay_two():
    out = fold_presence([row("Zeon"), row("Zeon", *NEXT_STREET)])
    assert out["Zeon"].own_within_3km == 2


def test_networks_are_never_folded_into_each_other():
    out = fold_presence([row("Zeon"), row("Statiq", *SAME_STATION)])
    assert out["Zeon"].own_within_3km == 1
    assert out["Statiq"].own_within_3km == 1


def test_a_name_we_cannot_place_is_dropped_not_bucketed():
    out = fold_presence([row("Zeon"), row("Some Local Garage"), row(None)])
    assert set(out) == {"Zeon"}


def test_self_operate_is_not_a_footprint():
    assert fold_presence([row("Self-operate")]) == {}


def test_the_four_counts_are_independent():
    # A station 4 km away, in the same state but the next district: outside the
    # near radius, inside the wide one, and outside the district count.
    out = fold_presence(
        [
            row("Statiq", district=True, state=True, near=True, wide=True),
            row(
                "Statiq",
                *NEXT_STREET,
                district=False,
                state=True,
                near=False,
                wide=True,
            ),
        ]
    )
    p = out["Statiq"]
    assert p.own_within_3km == 1
    assert p.own_within_10km == 2
    assert p.stations_district == 1
    assert p.stations_state == 2


def test_no_stations_yields_no_entry_rather_than_a_zero_row():
    # An absent network must reach the report as "unknown", which is the
    # caller's job to say. A zero row here would make it say "none".
    assert fold_presence([]) == {}
