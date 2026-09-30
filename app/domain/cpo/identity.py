"""Operator identity - PART 6's precondition. Pure functions, no DB, no network.

``competitor_stations.operator`` is whatever the source called the network,
verbatim. Open Charge Map's ``OperatorInfo.Title`` says "Zeon Charging";
zeoncharging.com's own feed says "Zeon"; and both rows are kept, because the
same physical charger seen from two sources is deliberately two rows until the
PLAN 2.3 dedupe. Counting stations per operator directly on that column
produces confident wrong numbers - which is worse than no numbers, and is the
exact failure ``resolution/crosswalk.py`` exists to prevent for districts.

This module is that module's shape, with one tier removed:

    exact          the name already IS one of the canonical networks
    alias          a known spelling, listed by hand below, each one a decision
    not_a_network  "Self-operate" - a real arrangement, not an operator
    unresolved     nothing matched; kept verbatim as its own bucket

**There is no fuzzy tier, deliberately.** The district crosswalk can afford one
because a human queue reviews every fuzzy proposal. Nothing reviews an operator
name. A near-miss here would silently merge two networks and mis-state how much
of a site's demand one of them can divert into its own nearby plugs - the very
number PART 6 exists to report. An unresolved name reports as unknown, and
unknown is not zero.

Growing the table is a human step: the console's operator surface names what
came back unresolved, someone confirms which network it is, and the alias is
added here with the source it was seen in.

**Checked against the whole inventory on 2026-09-07** - 1,788 rows, 23 distinct
names, all of them placed except the 86 the source itself declines to attribute.
The table is complete against that inventory and no further; a new feed, or a
new state, will introduce names it has never seen, and those must reach a human
rather than a fuzzy matcher.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

Confidence = Literal["exact", "alias", "not_a_network", "unresolved"]

#: What a source writes when it does not attribute a station to anyone. It is
#: its own bucket and is NEVER merged into a network - "we do not know who runs
#: this" is evidence about the source, not about any operator.
UNATTRIBUTED = "(unattributed)"

#: Corporate-form words that carry no identity and vary freely between feeds.
#: Kept deliberately short. "power", "energy" and "charging" are NOT here:
#: they are identity in "Tata Power", "Pulse Energy" and "Zeon Charging", and
#: stripping them is how two networks quietly become one. Where a feed really
#: does drop such a word, that is an alias entry below - a decision on the
#: record, not a rule applied to every name in the country.
_CORPORATE = {
    "pvt",
    "private",
    "ltd",
    "limited",
    "llp",
    "inc",
    "co",
    "corp",
    "company",
}

#: Every name we are willing to COUNT as a network. Not a partner list and not
#: an endorsement - a station run by Shell Recharge is a Shell Recharge station
#: whether or not we would ever put them on a comparison table. Each entry is a
#: name a feed actually attributed, seen in the inventory on 2026-09-07.
CANONICAL: tuple[str, ...] = (
    # Wired feeds of our own, and the networks CPO_SOURCES.md tracks.
    "chargeMOD",
    "Tata Power",
    "Statiq",
    "ChargeZone",
    "Zeon",
    "GO EC",
    "Kazam",
    "Ather Grid",
    "Jio-bp",
    "Relux",
    "ElectricPe",
    "Pulse Energy",
    "Bolt.Earth",
    "Glida",
    # Present in the Open Charge Map inventory for KL/TN, and counted for the
    # same reason: their chargers compete for, and divide, the same drivers.
    "Shell Recharge",
    "EESL",
    "Rebolt",
    "Adani",
    "Charge_iN",
    "Wheels Drive",
    "Hydra Charging",
    "Midgard Electric",
)

#: What a feed writes when it declines to name the operator. These are NOT
#: gaps in the alias table - there is nothing to look up - so they fold into
#: the one unattributed bucket and stay out of the "names to resolve" list.
_UNATTRIBUTED_MARKERS = {
    "unattributed",
    "unknown",
    "unknown operator",
    "business owner at location",
    "private individual",
}

#: Arrangements that are not a charging network at all. "Self-operate" is a
#: real row on the comparison table - the owner runs the station themselves -
#: and reporting it as a name we failed to match would be a lie about our own
#: coverage.
_NOT_A_NETWORK = {
    "self operate",
    "selfoperate",
    "self run",
    "owner operated",
    "owner run",
}

#: Hand-maintained, normalised key -> canonical display name. VARIANTS ONLY:
#: a key that ``normalise_operator`` already turns into a canonical name does
#: not belong here, and a test enforces that, so this table reads as exactly
#: the decisions someone had to make. Each comment names where it was seen.
OPERATOR_ALIASES: dict[str, str] = {
    # chargeMOD - ours.
    "charge mod": "chargeMOD",
    "bpm power": "chargeMOD",  # the operating entity behind com.bpm.chargemod
    # GO EC ships a row per connector, its own feed unspaced.
    "goec": "GO EC",
    "goec world": "GO EC",
    "go ec world": "GO EC",
    # Zeon - OCM writes the long form, zeoncharging.com the short one.
    "zeon charging": "Zeon",  # open_charge_map, 154 rows
    "zeon electric": "Zeon",
    # Tata Power - the retail brand and the parent appear interchangeably.
    "tata power ez charge": "Tata Power",
    "ez charge": "Tata Power",
    "tata power evcharge": "Tata Power",
    # ChargeZone writes itself with and without the plus.
    "charge zone": "ChargeZone",
    "charge+zone": "ChargeZone",
    # The rest, one variant each, seen in open_charge_map.
    "kazam ev": "Kazam",
    "ather": "Ather Grid",
    "ather grid point": "Ather Grid",
    "ather energy": "Ather Grid",
    "jiobp": "Jio-bp",
    "jio bp pulse": "Jio-bp",
    "relux electric": "Relux",
    "electric pe": "ElectricPe",
    "bolt": "Bolt.Earth",
    "fortum": "Glida",  # Fortum Charge & Drive India became Glida
    "fortum charge drive": "Glida",
    "adani gas ev": "Adani",
    "charge in by mahindra": "Charge_iN",
}

_PUNCT = re.compile(r"[^a-z0-9+]+")

#: Open Charge Map suffixes its operator titles with the country: "GO EC (IN)",
#: "Chargezone (India)". Without this, every OCM row is a separate network from
#: the same operator's own feed - it was 45% of the inventory when measured.
#: Anchored to the end and limited to a country-shaped token, so a brand that
#: genuinely ends in a parenthetical keeps it.
_COUNTRY_TAG = re.compile(r"\s*\((?:[a-z]{2,3}|india)\)\s*$", re.IGNORECASE)


def normalise_operator(raw: str) -> str:
    """Casefold, strip accents and punctuation, drop corporate-form words.

    ``+`` survives, because "Charge+Zone" is written that way and the plus is
    the only thing distinguishing it from a two-word spelling of the same brand
    - both of which are aliases below, so nothing turns on it, but dropping a
    character the brand actually uses would be a normaliser that lies.
    """
    folded = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    spaced = _PUNCT.sub(" ", _COUNTRY_TAG.sub("", folded).lower())
    words = [w for w in spaced.split() if w and w not in _CORPORATE]
    return " ".join(words)


#: Canonical names, normalised, for the ``exact`` tier.
_EXACT: dict[str, str] = {normalise_operator(name): name for name in CANONICAL}


@dataclass(frozen=True)
class OperatorMatch:
    """What we decided a raw operator string is, and how sure we are."""

    raw: str
    canonical: str | None
    confidence: Confidence

    @property
    def countable(self) -> bool:
        """True only when this name may be counted as a network's station.

        ``not_a_network`` and ``unresolved`` both answer False, for different
        reasons that the caller must keep apart when it explains itself.
        """
        return self.canonical is not None


def canonical_operator(raw: str | None) -> OperatorMatch:
    """Resolve one source-supplied operator name. Never guesses."""
    text = (raw or "").strip()
    if not text:
        return OperatorMatch(raw=UNATTRIBUTED, canonical=None, confidence="unresolved")

    key = normalise_operator(text)
    if not key or key in _UNATTRIBUTED_MARKERS:
        # Reported under the one bucket name, so the caller counts "the source
        # would not say" once rather than once per phrasing.
        return OperatorMatch(raw=UNATTRIBUTED, canonical=None, confidence="unresolved")
    if key in _NOT_A_NETWORK:
        return OperatorMatch(raw=text, canonical=None, confidence="not_a_network")
    if key in _EXACT:
        return OperatorMatch(raw=text, canonical=_EXACT[key], confidence="exact")
    if key in OPERATOR_ALIASES:
        return OperatorMatch(raw=text, canonical=OPERATOR_ALIASES[key], confidence="alias")
    return OperatorMatch(raw=text, canonical=None, confidence="unresolved")


@dataclass(frozen=True)
class Coverage:
    """How much of an inventory this table can actually name.

    ``unattributed`` is held apart from ``unresolved_names`` on purpose: a row
    the source itself refused to attribute is a fact about the source and has
    no fix, while an unresolved name is a missing line in the alias table and
    has exactly one. Reporting them as one number would ask someone to chase
    work that does not exist.
    """

    total: int
    resolved: int
    unattributed: int
    unresolved_names: tuple[str, ...]

    @property
    def pct(self) -> float:
        return 0.0 if self.total == 0 else round(100 * self.resolved / self.total, 1)


def coverage(raws: Iterable[str | None]) -> Coverage:
    """Resolution coverage over a list of raw names, with the misses named.

    The misses are the point: they are the next entries in ``OPERATOR_ALIASES``,
    and a coverage figure with no list attached is a number nobody can act on.
    """
    total = 0
    resolved = 0
    unattributed = 0
    misses: dict[str, None] = {}
    for raw in raws:
        total += 1
        match = canonical_operator(raw)
        if match.countable:
            resolved += 1
        elif match.raw == UNATTRIBUTED:
            unattributed += 1
        elif match.confidence == "unresolved":
            misses[match.raw] = None
    return Coverage(
        total=total,
        resolved=resolved,
        unattributed=unattributed,
        unresolved_names=tuple(misses),
    )
