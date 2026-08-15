"""Which price card prices this call - PART C.1.

``pricing.py`` does the arithmetic over a card. This finds the card, from the
effective-dated ``provider_price_cards`` table, and holds the seed data for the
cards we ship with.

The important rule is at the bottom of ``card_for``: **a paid provider with no
price card raises.** The tempting alternative - fall back to a zero card so the
call still goes through - produces a spend report that says Rs 0 while money
leaves the building, which is strictly worse than an outage. So a configured
API key without a card fails when the cascade is *built*, before any call.

Prices below are what the providers published as at the ``effective_from``
date, in paise, converted at a rate recorded in the note. Two of the three
overage rates are **unverified** and deliberately conservative - see the
``verified`` flag, which ``scripts.seed_price_cards`` prints a warning for.
Overstating our own cost is the safe direction; understating it is the failure
this table exists to prevent.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.metering.pricing import PriceCard
from app.models.price_cards import ProviderPriceCard


class PriceCardMissingError(LookupError):
    """No effective card covers this provider/operation on this date.

    Raised rather than defaulting to free. See the module docstring.
    """

    def __init__(self, provider: str, operation: str, on: dt.date) -> None:
        super().__init__(
            f"metering: no price card for {provider}/{operation} effective {on}. "
            "Seed one with `uv run python -m scripts.seed_price_cards` - a paid call "
            "with no price is a spend report that reads Rs 0 while the bill arrives."
        )
        self.provider = provider
        self.operation = operation
        self.on = on


def card_for(
    session: Session,
    provider: str,
    operation: str,
    *,
    model: str | None = None,
    on: dt.date | None = None,
) -> PriceCard:
    """The card in force for this provider/operation on ``on`` (default today).

    A model-specific card wins over the all-models (``model IS NULL``) card, so
    an LLM can be priced per model without a row for every model that is not.
    """
    when = on or dt.datetime.now(dt.UTC).date()

    stmt = (
        select(ProviderPriceCard)
        .where(
            ProviderPriceCard.provider == provider,
            ProviderPriceCard.operation == operation,
            ProviderPriceCard.effective_from <= when,
            or_(
                ProviderPriceCard.effective_to.is_(None),
                ProviderPriceCard.effective_to > when,
            ),
        )
        .order_by(ProviderPriceCard.effective_from.desc())
    )
    rows = list(session.execute(stmt).scalars())

    chosen = next((r for r in rows if r.model == model), None)
    if chosen is None:
        chosen = next((r for r in rows if r.model is None), None)
    if chosen is None:
        raise PriceCardMissingError(provider, operation, when)

    return PriceCard(
        version=chosen.version,
        micro_paise_per_unit_in=chosen.micro_paise_per_unit_in,
        micro_paise_per_unit_out=chosen.micro_paise_per_unit_out,
        free_units_per_month=chosen.free_units_per_month,
    )


# ---------------------------------------------------------------------------
# Seed data. A reviewable diff, not a fixture nobody can find.
# ---------------------------------------------------------------------------

#: Paise per US dollar, used for the two USD-priced providers. Recorded as a
#: constant rather than folded into the numbers so that when the rupee moves,
#: the new card is one obvious edit and the old card still reprices history.
USD_PAISE = 8_800  # Rs 88.00/USD, August 2026

_FROM = dt.date(2026, 8, 1)


@dataclass(frozen=True)
class CardSpec:
    """One price card as published. ``verified`` is not a database column - it
    is the seed script's warning flag for a number nobody has confirmed yet."""

    provider: str
    operation: str
    micro_paise_per_unit_in: int
    free_units_per_month: int
    version: str
    source_url: str
    note: str
    verified: bool
    model: str | None = None
    micro_paise_per_unit_out: int = 0
    effective_from: dt.date = _FROM


GEOCODING_CARDS: tuple[CardSpec, ...] = (
    CardSpec(
        provider="ola_maps",
        operation="geocode",
        # 25 paise/call. UNVERIFIED - Ola publishes the 500k free tier
        # prominently and the overage rate far less so.
        micro_paise_per_unit_in=25_000_000,
        free_units_per_month=500_000,
        version="ola_maps-geocode-2026-08",
        source_url="https://maps.olakrutrim.com/pricing",
        note=(
            "500,000 free calls/month (India-only service). Overage rate of 25 paise/call "
            "is a CONSERVATIVE PLACEHOLDER and has not been confirmed against a bill. "
            "Confirm before the free tier is exhausted; a wrong rate here shows up as a "
            "spend report that will not reconcile."
        ),
        verified=False,
    ),
    CardSpec(
        provider="mappls",
        operation="geocode",
        # 20 paise/call. UNVERIFIED - Mappls prices per plan, not per public rate card.
        micro_paise_per_unit_in=20_000_000,
        free_units_per_month=10_000,
        version="mappls-geocode-2026-08",
        source_url="https://about.mappls.com/api/",
        note=(
            "Free tier taken as 10,000 transactions/month on the entry plan. Both the "
            "allowance and the 20 paise/call overage are PLACEHOLDERS pending the actual "
            "plan we sign. Mappls prices per contract, not per public rate card."
        ),
        verified=False,
    ),
    CardSpec(
        provider="google_maps",
        operation="geocode",
        # $5 per 1,000 = $0.005 = 44 paise at Rs 88/USD.
        micro_paise_per_unit_in=5 * USD_PAISE * 1_000_000 // 1_000,
        # 10,000 is the GLOBAL Essentials allowance, seeded deliberately low.
        free_units_per_month=10_000,
        version="google_maps-geocode-2026-08",
        source_url="https://developers.google.com/maps/billing-and-pricing/pricing",
        note=(
            "USD 5.00 per 1,000 calls converted at Rs 88.00/USD. Free allowance seeded at "
            "the 10,000/month GLOBAL Essentials figure, NOT the 70,000 an India-billed "
            "account receives (PLAN 1.3 L5) - understating the free tier overstates our "
            "cost, which is the safe direction. Raise it to 70,000 with a NEW card once "
            "the Indian billing entity is confirmed; never edit this row."
        ),
        verified=True,
    ),
)


def seed_price_cards(
    session: Session, specs: tuple[CardSpec, ...] = GEOCODING_CARDS
) -> tuple[list[str], list[str]]:
    """Insert any card whose ``version`` is not already present.

    Idempotent, and never updates: a card is superseded by a new row with a new
    version and an ``effective_to`` on the old one, exactly like the SERC tariff
    table. Returns ``(inserted, skipped)`` versions.
    """
    existing = {
        v for (v,) in session.execute(select(ProviderPriceCard.version)) if isinstance(v, str)
    }
    inserted: list[str] = []
    skipped: list[str] = []

    for spec in specs:
        if spec.version in existing:
            skipped.append(spec.version)
            continue
        session.add(
            ProviderPriceCard(
                version=spec.version,
                provider=spec.provider,
                operation=spec.operation,
                model=spec.model,
                micro_paise_per_unit_in=spec.micro_paise_per_unit_in,
                micro_paise_per_unit_out=spec.micro_paise_per_unit_out,
                free_units_per_month=spec.free_units_per_month,
                effective_from=spec.effective_from,
                effective_to=None,
                source_url=spec.source_url,
                note=spec.note,
            )
        )
        inserted.append(spec.version)

    session.flush()
    return inserted, skipped
