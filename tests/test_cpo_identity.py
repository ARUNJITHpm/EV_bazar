"""Operator identity - PART 6's precondition. Pure, no database.

The property under test is not "does it match names". It is **does it refuse
to guess**: every wrong merge here silently mis-states how much of a site's
demand one network can divert into its own nearby plugs, and no downstream
test catches it.
"""

from __future__ import annotations

from app.domain.cpo.identity import (
    CANONICAL,
    OPERATOR_ALIASES,
    UNATTRIBUTED,
    canonical_operator,
    coverage,
    normalise_operator,
)


def test_a_canonical_name_matches_itself_exactly():
    for name in CANONICAL:
        match = canonical_operator(name)
        assert match.canonical == name
        assert match.confidence == "exact"


def test_the_two_spellings_of_one_network_land_on_one_name():
    # The whole reason this module exists: Open Charge Map and the operator's
    # own feed write the same network differently, and both rows are kept.
    assert canonical_operator("Zeon Charging").canonical == "Zeon"
    assert canonical_operator("Zeon").canonical == "Zeon"
    assert canonical_operator("GoEC").canonical == "GO EC"
    assert canonical_operator("GO EC").canonical == "GO EC"
    assert canonical_operator("Charge+Zone").canonical == "ChargeZone"
    assert canonical_operator("charge zone").canonical == "ChargeZone"


def test_corporate_suffixes_are_noise_but_identity_words_are_not():
    assert normalise_operator("Statiq Pvt. Ltd.") == "statiq"
    assert canonical_operator("Statiq Private Limited").canonical == "Statiq"
    # "power" and "energy" are identity, not noise. Stripping them is how two
    # unrelated networks quietly become one.
    assert normalise_operator("Tata Power") == "tata power"
    assert normalise_operator("Pulse Energy") == "pulse energy"
    assert (
        canonical_operator("Tata Power").canonical != canonical_operator("Pulse Energy").canonical
    )


def test_a_near_miss_is_refused_rather_than_guessed():
    # One character out of a known name. A fuzzy matcher would take these;
    # nothing reviews the result, so this module must not.
    for typo in ("Zeom", "Statiqq", "Charge Zonne", "Kazaam"):
        match = canonical_operator(typo)
        assert match.canonical is None, typo
        assert match.confidence == "unresolved"


def test_open_charge_map_country_suffix_is_not_part_of_the_brand():
    # 45% of the inventory when this was measured. Without it every OCM row is
    # a separate network from the same operator's own feed.
    assert canonical_operator("GO EC (IN)").canonical == "GO EC"
    assert canonical_operator("Chargezone (India)").canonical == "ChargeZone"
    assert canonical_operator("ChargeMod (IN)").canonical == "chargeMOD"
    assert canonical_operator("Ather Grid Point (India)").canonical == "Ather Grid"
    # Anchored to the end, and only a country-shaped token: a name that is
    # itself parenthesised keeps its parentheses and stays unresolved.
    assert canonical_operator("(Unknown Operator)").canonical is None


def test_unattributed_is_its_own_bucket_and_never_a_network():
    # Every phrasing of "the source would not say" folds to one bucket, so it
    # is counted once rather than once per wording.
    for raw in (
        None,
        "",
        "   ",
        UNATTRIBUTED,
        "(Unknown Operator)",
        "(Business Owner at Location)",
    ):
        match = canonical_operator(raw)
        assert match.canonical is None
        assert match.confidence == "unresolved"
        assert match.raw == UNATTRIBUTED
        assert not match.countable


def test_self_operate_is_not_a_failed_match():
    match = canonical_operator("Self-operate")
    assert match.canonical is None
    assert not match.countable
    # The distinction the report turns on: "you run it" and "we could not name
    # this" are both uncountable and must not read as the same sentence.
    assert match.confidence == "not_a_network"
    assert canonical_operator("Zeom").confidence == "unresolved"


def test_every_alias_points_at_a_canonical_name_and_is_already_normalised():
    for key, value in OPERATOR_ALIASES.items():
        assert value in CANONICAL, key
        assert normalise_operator(key) == key, key


def test_the_alias_table_carries_no_entry_an_exact_match_already_covers():
    """It should read as exactly the decisions someone had to make."""
    exact = {normalise_operator(name) for name in CANONICAL}
    redundant = sorted(exact & set(OPERATOR_ALIASES))
    assert redundant == []


def test_coverage_separates_a_missing_alias_from_an_unnamed_source_row():
    c = coverage(
        ["Zeon Charging", "Statiq", "Zeom", "Zeom", None, "(Unknown Operator)", "Self-operate"]
    )
    assert c.total == 7
    assert c.resolved == 2
    # Misses are deduped and named, because a percentage nobody can act on is
    # not a finding. "Self-operate" is not a miss - there is nothing to fix.
    assert c.unresolved_names == ("Zeom",)
    # And a row the source would not attribute is held apart: it is a fact
    # about the feed, not a line someone forgot to add to the alias table.
    assert c.unattributed == 2


def test_coverage_of_nothing_does_not_divide_by_zero():
    assert coverage([]).pct == 0.0
