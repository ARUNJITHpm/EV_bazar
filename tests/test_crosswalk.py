"""PART 1.2 - district name matching.

PLAN 1.2: "Getting this wrong misattributes every downstream number silently."

Silently is the operative word, so most of these tests are about the matcher
*refusing*. A matcher that always answers is worse than one that sometimes
says "ask a human", because nothing downstream can tell the difference between
a good answer and a confident wrong one.
"""

from __future__ import annotations

import pytest

from app.domain.resolution.crosswalk import (
    AMBIGUITY_MARGIN,
    Candidate,
    canonical_name,
    match_district,
    normalise_name,
)

KERALA = [
    Candidate(565, "Thiruvananthapuram", "KERALA"),
    Candidate(555, "Ernakulam", "KERALA"),
    Candidate(559, "Kozhikode", "KERALA"),
    Candidate(566, "Thrissur", "KERALA"),
    Candidate(558, "Kasaragod", "KERALA"),
]

KARNATAKA = [
    Candidate(572, "Bengaluru Urban", "KARNATAKA"),
    Candidate(571, "Bengaluru Rural", "KARNATAKA"),
    Candidate(583, "Mysuru", "KARNATAKA"),
]

# The classic trap: the same district name in two different states.
BILASPUR = [
    Candidate(388, "Bilaspur", "CHHATTISGARH"),
    Candidate(24, "Bilaspur", "HIMACHAL PRADESH"),
]


# --- normalisation ----------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Thiruvananthapuram", "thiruvananthapuram"),
        ("  THRISSUR  ", "thrissur"),
        ("Thrissur District", "thrissur"),
        ("Bilaspur (H.P.)", "bilaspur"),
        ("The Nilgiris", "nilgiris"),
        ("Y.S.R.", "y s r"),
        ("Dakshina  Kannada", "dakshina kannada"),
    ],
)
def test_normalisation_strips_presentation_not_identity(raw: str, expected: str) -> None:
    assert normalise_name(raw) == expected


def test_diacritics_are_folded() -> None:
    assert normalise_name("Puducherry") == normalise_name("Pudučherry")


# --- exact and alias: the trustworthy half ----------------------------------


def test_an_exact_name_matches() -> None:
    match = match_district("Ernakulam", "KERALA", KERALA)
    assert (match.lgd_district_code, match.method) == (555, "exact")
    assert match.trustworthy


def test_case_and_suffix_do_not_prevent_an_exact_match() -> None:
    assert match_district("THRISSUR district", "Kerala", KERALA).lgd_district_code == 566


@pytest.mark.parametrize(
    ("old", "expected"),
    [
        ("Trivandrum", 565),
        ("Cochin", 555),
        ("Kochi", 555),
        ("Calicut", 559),
        ("Trichur", 566),
    ],
)
def test_the_old_names_resolve(old: str, expected: int) -> None:
    """A 2014 tariff order says Trivandrum. LGD says Thiruvananthapuram.

    Those two score far below any fuzzy floor, so without the alias table they
    would sit in the manual queue forever - which is why the table exists.
    """
    match = match_district(old, "KERALA", KERALA)
    assert match.lgd_district_code == expected
    assert match.trustworthy


def test_a_rename_is_an_alias_not_a_guess() -> None:
    match = match_district("Bangalore Urban", "KARNATAKA", KARNATAKA)
    assert (match.lgd_district_code, match.method) == (572, "alias")
    assert match.trustworthy


# --- refusing: the half that matters ----------------------------------------


def test_a_fuzzy_match_is_proposed_but_never_trusted() -> None:
    match = match_district("Thrisur", "KERALA", KERALA)  # one letter short
    assert match.lgd_district_code == 566
    assert match.method == "fuzzy"
    assert not match.trustworthy  # a human still has to look


def test_a_name_from_nowhere_is_refused() -> None:
    match = match_district("Atlantis", "KERALA", KERALA)
    assert match.lgd_district_code is None
    assert match.method == "unresolved"


def test_matching_is_scoped_to_the_state() -> None:
    """Bilaspur exists in two states; the state decides, not the score."""
    assert match_district("Bilaspur", "HIMACHAL PRADESH", BILASPUR).lgd_district_code == 24
    assert match_district("Bilaspur", "CHHATTISGARH", BILASPUR).lgd_district_code == 388


def test_an_unknown_state_is_refused_rather_than_searched_nationwide() -> None:
    match = match_district("Bilaspur", "ATLANTIS", BILASPUR)
    assert match.lgd_district_code is None
    assert "no candidate districts" in (match.note or "")


def test_a_name_missing_its_qualifier_is_refused() -> None:
    """Bengaluru Urban and Bengaluru Rural are different districts.

    Bare "Bengaluru" is not either of them, and a matcher that picks the
    higher score by a nose is how a report gets written against the wrong
    district. Refusing costs twenty seconds of someone's attention; guessing
    costs the customer's trust.
    """
    match = match_district("Bengaluru", "KARNATAKA", KARNATAKA)
    assert match.lgd_district_code is None
    assert match.method == "unresolved"


def test_bangalore_without_a_qualifier_is_also_refused() -> None:
    """The alias resolves the rename; it does not invent the missing half."""
    assert match_district("Bangalore", "KARNATAKA", KARNATAKA).lgd_district_code is None


def test_two_candidates_scoring_alike_are_refused_even_above_the_floor() -> None:
    """The ambiguity margin, exercised on its own.

    Both candidates clear the fuzzy floor and score identically. Without the
    margin the matcher would return whichever sorted first - a coin toss
    presented as an answer.
    """
    twins = [
        Candidate(1, "Pratapgarh East", "TEST"),
        Candidate(2, "Pratapgarh West", "TEST"),
    ]
    match = match_district("Pratapgarh", "TEST", twins)
    assert match.lgd_district_code is None
    assert match.method == "unresolved"
    assert match.score >= 80  # cleared the floor; refused on ambiguity alone
    assert "too close to call" in (match.note or "")
    assert AMBIGUITY_MARGIN > 0


def test_a_clear_winner_above_the_floor_is_still_proposed() -> None:
    """The margin must not refuse everything - the mirror of the test above."""
    clear = [
        Candidate(1, "Rampur North", "TEST"),
        Candidate(2, "Sultanpur", "TEST"),
    ]
    match = match_district("Rampur Norht", "TEST", clear)
    assert (match.lgd_district_code, match.method) == (1, "fuzzy")


def test_duplicate_normalised_names_in_one_state_are_refused() -> None:
    """A data problem, reported as one rather than resolved arbitrarily."""
    duplicated = [
        Candidate(1, "Aurangabad", "BIHAR"),
        Candidate(2, "Aurangabad district", "BIHAR"),
    ]
    match = match_district("Aurangabad", "BIHAR", duplicated)
    assert match.lgd_district_code is None
    assert "normalise to" in (match.note or "")


def test_canonical_name_applies_the_alias_table() -> None:
    assert canonical_name("Bangalore") == "bengaluru"
    assert canonical_name("Ernakulam") == "ernakulam"
