"""The tier gate - PLAN 1.6. "How much do we know here", as a number.

``tier_for`` is the gate as a pure function, moved here from the Lookup
panel so the DOMAIN owns the judgement and the API layers only display it -
/assess and the coverage table must never be able to disagree about what a
tier means.

``state_tier`` derives one state's evidence flags live from the tables and
returns the verdict. Deliberately NOT persisted per district yet: today
every flag except the tariff is state-wide or national, so a data_coverage
table would hold thousands of identical copies of a judgement three
subselects can make. It becomes worth persisting the day tiers vary WITHIN
a state - which needs district-attributed occupancy (the poller + FINDINGS
B3). What IS persisted is the stamp: /assess writes ``sites.data_tier`` at
request time, so every site records what we knew when it was asked about,
the same way it records its geocode confidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

#: LGD state codes of PLAN Part 1's first markets: Kerala (32), Tamil Nadu (33).
FOCUS_STATES = frozenset({32, 33})

TIER_RULE = (
    "A tier measures how much WE know about a state - it is our data coverage, not "
    "the size or importance of its cities. Tier 1 = we hold tariffs AND competitor "
    "occupancy AND vehicle counts, so a full report is honest. Tier 2 = tariffs "
    "alone - enough for a breakeven number and a tariff audit, the first sellable "
    "product. Tier 3 = we know too little; log the pin, waitlist the customer, and "
    "count the district as demand. A state moves UP by us loading data for it, "
    "starting with the focus states."
)


def tier_for(*, tariff: bool, poll: bool, vahan: bool, osm: bool) -> tuple[int, str]:
    """The gate, as a pure function of the evidence flags."""
    if tariff and poll and vahan:
        return 1, "tariffs, occupancy and vehicle counts are all present"
    if tariff:
        missing = [
            label
            for label, present in (
                ("competitor occupancy", poll),
                ("VAHAN vehicle counts", vahan),
                ("road quality", osm),
            )
            if not present
        ]
        return 2, "tariffs are loaded, so a breakeven number is honest; still missing " + ", ".join(
            missing
        )
    return 3, "no tariff data for this state, so no number here would be trustworthy"


@dataclass(frozen=True)
class TierVerdict:
    tier: int
    why: str
    has_tariff: bool
    has_vahan: bool
    has_poll: bool


_EVIDENCE = text("""
    SELECT
      (SELECT count(*) FROM electricity_tariffs
        WHERE lgd_state_code = :code
          AND (effective_to IS NULL OR effective_to > CURRENT_DATE)),
      (SELECT count(*) FROM vahan_ev_registrations WHERE lgd_state_code = :code),
      (SELECT count(*) FROM poll_runs)
""")


def state_tier(session: Session, lgd_state_code: int) -> TierVerdict:
    """One state's tier, from live evidence. One round trip.

    The tariff flag needs a CURRENTLY-effective row - a superseded order is
    history, not coverage. Occupancy is national until a poll can be
    attributed to a district (the same caveat the coverage table states).
    OSM road quality has no table yet, so it is false by construction here
    exactly as it is there.
    """
    row = session.execute(_EVIDENCE, {"code": lgd_state_code}).one()
    has_tariff, has_vahan, has_poll = bool(row[0]), bool(row[1]), bool(row[2])
    tier, why = tier_for(tariff=has_tariff, poll=has_poll, vahan=has_vahan, osm=False)
    return TierVerdict(
        tier=tier, why=why, has_tariff=has_tariff, has_vahan=has_vahan, has_poll=has_poll
    )
