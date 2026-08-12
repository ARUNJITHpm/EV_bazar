"""Cost from the effective-dated price card - PART C.1.

Pure arithmetic over a card that was looked up elsewhere. Kept separate from
the DB lookup so the rounding rules can be unit-tested exhaustively, which
matters because these numbers end up in a spend report that must reconcile
against a provider's own billing dashboard within 5%.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

MICRO = 1_000_000
"""Price cards store micro-paise per unit so sub-paise LLM token prices
survive as integers rather than accumulating float drift over millions of
tokens."""


@dataclass(frozen=True)
class PriceCard:
    """The pricing facts needed to cost one call. No DB, no session."""

    version: str
    micro_paise_per_unit_in: int = 0
    #: Zero for call-metered providers; only LLMs price output separately.
    micro_paise_per_unit_out: int = 0
    free_units_per_month: int = 0


def billing_month(moment: dt.datetime) -> dt.date:
    """The quota window a call counts against: first of its UTC month.

    Providers reset quotas on their own calendar, in UTC. Using local time
    here would put end-of-month calls in the wrong bucket and make the cap
    leak by a few hours every month.
    """
    return moment.astimezone(dt.UTC).date().replace(day=1)


def cost_paise(
    card: PriceCard,
    units_in: int,
    units_out: int = 0,
    *,
    units_already_used_this_month: int = 0,
) -> int:
    """Cost of one call in whole paise.

    Free allowance is consumed by *input* units, which is how call-metered
    providers (Google, Ola, Mappls) actually bill: the free tier is a count
    of requests, not of response size.

    Rounds up. A half-paise rounded down, a few hundred thousand times, is a
    spend report that quietly understates the bill - and the whole point of
    this table is that it reconciles.
    """
    if units_in < 0 or units_out < 0:
        raise ValueError("metering: unit counts cannot be negative")

    remaining_free = max(0, card.free_units_per_month - units_already_used_this_month)
    chargeable_in = max(0, units_in - remaining_free)

    micro = chargeable_in * card.micro_paise_per_unit_in
    micro += units_out * card.micro_paise_per_unit_out

    return -(-micro // MICRO)  # ceiling division, integers only
