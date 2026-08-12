"""District name matching. Pure functions, no DB, no network - PART 1.2.

    "Build district_name_crosswalk by hand for 6 states. Shapefile names are
     not LGD names. Getting this wrong misattributes every downstream number
     silently."

The silence is the problem. Nothing fails when "Bangalore Rural" is matched to
Bengaluru Urban - a report is simply produced against the wrong tariff, the
wrong VAHAN counts, and the wrong competitors, and it looks exactly like a
correct report. There is no downstream test that catches it.

So this module's job is not to be clever. It is to be *honest about how
confident it is*, and to refuse rather than guess:

    exact       normalised strings are identical
    alias       a known rename or anglicisation, listed below by hand
    fuzzy       close enough to propose, NEVER close enough to trust
    unresolved  two candidates too close to call, or nothing near enough

Only ``exact`` and ``alias`` are safe to use unreviewed. Everything else is a
suggestion for a human, and ``verified_by`` on the table is what records that
the human turned up.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

#: Below this, a fuzzy suggestion is noise rather than a lead.
FUZZY_FLOOR = 80

#: If the best two candidates are within this many points of each other, the
#: match is refused outright. "Bilaspur" exists in both Chhattisgarh and
#: Himachal; picking the higher score by a nose is how a district silently
#: becomes the wrong one.
AMBIGUITY_MARGIN = 4

#: Words that carry no identity and vary freely between datasets.
_NOISE = {
    "district",
    "dist",
    "distt",
    "division",
    "zilla",
    "zila",
    "jilla",
    "the",
}

#: Hand-maintained. Every entry is a decision someone made, so each gets a
#: reason. Keys and values are both normalised forms.
#:
#: The renames are the dangerous half: a 2014 tariff order says "Bangalore",
#: LGD says "Bengaluru", and a fuzzy matcher scores those at 56 - well below
#: any sane floor - so without this table they would land in the manual queue
#: forever. The anglicisations are the common half.
DISTRICT_ALIASES: dict[str, str] = {
    # Official renames of the same place.
    "bangalore": "bengaluru",
    "bangalore urban": "bengaluru urban",
    "bangalore rural": "bengaluru rural",
    "mysore": "mysuru",
    "mangalore": "mangaluru",
    "belgaum": "belagavi",
    "bellary": "ballari",
    "gulbarga": "kalaburagi",
    "bijapur": "vijayapura",
    "hospet": "hosapete",
    "shimoga": "shivamogga",
    "tumkur": "tumakuru",
    "chikmagalur": "chikkamagaluru",
    "hassan": "hassan",
    "calicut": "kozhikode",
    "cochin": "ernakulam",
    "kochi": "ernakulam",
    "trivandrum": "thiruvananthapuram",
    "trichur": "thrissur",
    "quilon": "kollam",
    "alleppey": "alappuzha",
    "palghat": "palakkad",
    "cannanore": "kannur",
    "tellicherry": "kannur",
    "madras": "chennai",
    "trichy": "tiruchirappalli",
    "trichinopoly": "tiruchirappalli",
    "tanjore": "thanjavur",
    "tuticorin": "thoothukkudi",
    "nilgiris": "the nilgiris",
    "bombay": "mumbai",
    "poona": "pune",
    "baroda": "vadodara",
    "gurgaon": "gurugram",
    "allahabad": "prayagraj",
    "faizabad": "ayodhya",
    "orissa": "odisha",
    "pondicherry": "puducherry",
    "waltair": "visakhapatnam",
    "vizag": "visakhapatnam",
    # Spelling variants that differ by more than a fuzzy match tolerates.
    "y s r": "ysr kadapa",
    "cuddapah": "ysr kadapa",
    "kadapa": "ysr kadapa",
}


@dataclass(frozen=True)
class Candidate:
    """One LGD district, as the matcher sees it."""

    lgd_district_code: int
    name: str
    state_name: str


@dataclass(frozen=True)
class Match:
    """A proposal. ``method`` says how much to trust it."""

    lgd_district_code: int | None
    method: str  # exact | alias | fuzzy | unresolved
    score: int
    note: str | None = None

    @property
    def trustworthy(self) -> bool:
        """Safe to use without a human having looked.

        ``fuzzy`` is deliberately excluded. It is good enough to put in front
        of a person and not good enough to put in a report.
        """
        return self.method in {"exact", "alias"}


def normalise_name(name: str) -> str:
    """Strip everything that is presentation rather than identity.

    Diacritics, case, punctuation, the word "district", and any parenthesised
    aside - datasets disagree on all of them and none of them distinguish two
    real places.
    """
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    # "Bilaspur (H.P.)" -> "bilaspur". The parenthetical is a disambiguator
    # for humans, and it is the state that actually disambiguates here.
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [w for w in text.split() if w not in _NOISE]
    return " ".join(words).strip()


def canonical_name(name: str) -> str:
    """Normalise, then apply the alias table."""
    normalised = normalise_name(name)
    return DISTRICT_ALIASES.get(normalised, normalised)


def _similarity(a: str, b: str) -> int:
    return round(difflib.SequenceMatcher(None, a, b).ratio() * 100)


def match_district(
    source_name: str,
    source_state: str,
    candidates: list[Candidate],
) -> Match:
    """Propose an LGD district for a foreign spelling.

    Matching is scoped to the state first. Not an optimisation: India has
    several district names that repeat across states (Bilaspur, Hamirpur,
    Aurangabad, Balrampur, Pratapgarh), and a nationwide match on name alone
    would silently pick one of them.
    """
    state_key = canonical_name(source_state)
    in_state = [c for c in candidates if canonical_name(c.state_name) == state_key]
    if not in_state:
        return Match(None, "unresolved", 0, f"no candidate districts for state {source_state!r}")

    normalised = normalise_name(source_name)
    aliased = DISTRICT_ALIASES.get(normalised, normalised)

    by_name: dict[str, list[Candidate]] = {}
    for candidate in in_state:
        by_name.setdefault(canonical_name(candidate.name), []).append(candidate)

    for key, method in ((normalised, "exact"), (aliased, "alias")):
        hits = by_name.get(key)
        if not hits:
            continue
        if len(hits) > 1:
            # Two districts in one state normalising to the same string is a
            # data problem, not a matching problem. Refuse and say so.
            return Match(
                None,
                "unresolved",
                100,
                f"{len(hits)} districts in {source_state} normalise to {key!r}",
            )
        return Match(hits[0].lgd_district_code, method, 100)

    scored = sorted(
        ((_similarity(aliased, key), key) for key in by_name),
        reverse=True,
    )
    best_score, best_key = scored[0]
    if best_score < FUZZY_FLOOR:
        return Match(None, "unresolved", best_score, f"nearest was {best_key!r}")

    if len(scored) > 1 and best_score - scored[1][0] < AMBIGUITY_MARGIN:
        return Match(
            None,
            "unresolved",
            best_score,
            f"too close to call: {best_key!r} ({best_score}) vs {scored[1][1]!r} ({scored[1][0]})",
        )

    return Match(by_name[best_key][0].lgd_district_code, "fuzzy", best_score, f"~ {best_key!r}")
