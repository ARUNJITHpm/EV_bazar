"""What the twelve sections can print from a payload, and what they drop.

Every field the rebuild added is optional on ``ReportPayload``, for a reason
recorded there: a payload stored by an older economics version must still
validate, and the section that would have printed it omits the block rather
than inventing one. That is the right behaviour and it is also invisible - a
report renders a complete-looking page while quietly showing less than the
document is capable of, and nobody can tell by looking.

This module is how you tell. Given a stored payload, it says per section what
is NOT on the page and names it the way a reader would - "the cash column",
"the ten-year running total" - rather than by field.

Pure, and takes a ``dict`` rather than a ``ReportPayload``: what is stored is
the authority (AGENTS.md rule 9), and validating first would fill defaults in
and hide exactly the absences being counted.

The section list here is the backend's copy of the order in
``frontend/src/features/report/Report.tsx``. It is pinned from the frontend
side, where the components are - ``features/console/ReportBuild.test.tsx``
renders the report and asserts the ids match, in order.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.domain.report.public_coverage import public_context_gaps as public_context_gaps

#: The document's twelve sections, in reading order. The id is the
#: ``data-report-section`` attribute the print measurements select on.
SECTION_IDS: tuple[tuple[int, str, str], ...] = (
    (1, "verdict", "Verdict"),
    (2, "money", "What this means for your money"),
    (3, "judged", "How this site was judged"),
    (4, "site", "The site"),
    (5, "financials", "Financial working"),
    (6, "operators", "Operator comparison"),
    (7, "competitors", "Competitors"),
    (8, "change", "What would change this verdict"),
    (9, "statistical", "Statistical basis"),
    (10, "ledger", "Assumptions ledger"),
    (11, "provenance", "Provenance"),
    (12, "disclosure", "Disclosure and independence"),
)

#: Section 04 promises 34 checks across five groups (the landing page's own
#: figure, from `features/animation/data.ts`). A payload carrying fewer is
#: short of what was advertised, and that is a fact about the payload rather
#: than a defect in the section, so it is reported as one.
#:
#: Since 2026-09-09 the assembler emits MORE than this - the promised list
#: plus a handful it genuinely measures on top. The number that matters now
#: is not the shortfall but how many of the checks have nothing behind them,
#: counted below.
PROMISED_SITE_FACTS = 34


@dataclass(frozen=True)
class SectionCoverage:
    n: int
    id: str
    title: str
    #: Reader-visible blocks this payload cannot fill. Empty means the section
    #: is printing everything it knows how to print.
    dropped: tuple[str, ...]


def _rows(payload: Mapping[str, Any], key: str) -> Sequence[Mapping[str, Any]]:
    value = payload.get(key)
    return value if isinstance(value, list) else []


def _some(rows: Sequence[Mapping[str, Any]], field: str) -> bool:
    """Does any row carry this field? The sections gate whole COLUMNS on
    exactly this test - one operator with a repair target is enough to earn
    the column, and none is what drops it."""
    return any(row.get(field) is not None for row in rows)


def _block(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def coverage(payload: Mapping[str, Any]) -> tuple[SectionCoverage, ...]:
    """Per section, what this payload leaves off the page."""
    breakeven = _block(payload, "breakeven")
    financials = _block(payload, "financials")
    competitors = _block(payload, "competitors")
    facts = _rows(payload, "site_facts")
    cpo = _rows(payload, "cpo")
    scenarios = financials.get("scenarios")
    scenario_rows: Sequence[Mapping[str, Any]] = scenarios if isinstance(scenarios, list) else []

    full_cost = breakeven.get("full_cost_utilisation") is not None
    plain = _some(scenario_rows, "plain")

    dropped: dict[str, list[str]] = {sid: [] for _, sid, _ in SECTION_IDS}

    def drop(section: str, what: str) -> None:
        dropped[section].append(what)

    # 02 · the plain-money vocabulary (economics 0.3.0). Without it the
    # section is the fixed-deposit comparison alone - which is the half a
    # landowner cannot read.
    if not plain:
        drop("money", "the setup / cash / recovery figures and the four-row case table")
        drop("money", "the time-to-recover line")
        drop("financials", "the ten-year running total against the setup cost")

    # 03, 09 and 08 all print the full-cost rule (economics 0.2.0), and 09
    # prints its division in full (0.4.0's recovery term).
    if not full_cost:
        drop(
            "judged", "the full-cost rule row - the table falls back to the running-bill line alone"
        )
        drop("statistical", "the dashed build-cost rule on the chart, and both divisions below it")
        drop("change", "the build-cost lever")
    elif breakeven.get("full_cost_recovery_paise_year") is None:
        drop("statistical", "the recovery term, so the full-cost division is stated and not shown")

    # 04 · the three things R4 added, each optional so an older payload still
    # renders a table.
    if facts and not _some(facts, "group"):
        drop("site", "the three grouped chapters - every check falls into one flat table")
    if facts and not _some(facts, "direction"):
        drop("site", "the favours / neutral / against markers")
    if facts and not _some(facts, "means"):
        drop("site", "the WHAT IT MEANS column")
    if not facts:
        drop("site", "every check - the payload carries no site facts at all")
    else:
        if len(facts) < PROMISED_SITE_FACTS:
            drop("site", f"{PROMISED_SITE_FACTS - len(facts)} of the {PROMISED_SITE_FACTS} checks")
        # The row exists, is named, and says UNVERIFIED - which is honest on
        # the page and still a gap in the product. Counting it here is what
        # keeps "the section is full" from being mistaken for "the section is
        # finished": a placeholder that nobody is counting is a placeholder
        # that ships for ever.
        placeholders = sum(1 for f in facts if f.get("unverified"))
        if placeholders:
            drop(
                "site",
                f"{placeholders} of the {len(facts)} checks have no source behind them "
                "yet and print as UNVERIFIED",
            )

    # 05 · the three breakdowns (economics 0.3.0).
    if financials.get("capex_lines") is None:
        drop("financials", "the one-time budget, line by line")
    if financials.get("unit_economics") is None:
        drop("financials", "the per-unit chain - price minus every cut")
    if financials.get("fixed_costs") is None:
        drop("financials", "the monthly bills, itemised")

    # 06 · four column groups, each gated on the whole table (R9).
    if not cpo:
        drop("operators", "both tables - the payload carries no operator rows")
    else:
        if not _some(cpo, "cash_p50_paise_year"):
            drop("operators", "the cash-per-year column")
        if not _some(cpo, "own_within_3km") and not _some(cpo, "stations_district"):
            drop("operators", "the network footprint table - district, state, 3 km and 10 km")
        if not _some(cpo, "repair_hours"):
            drop("operators", "the repair-target column (waits on cpo_terms)")
        if not _some(cpo, "tie_in_years"):
            drop("operators", "the tie-in column (waits on cpo_terms)")

    # 07 · the wider rings, and the busyness that has never existed.
    if competitors.get("within_5km") is None:
        drop("competitors", "the 5 km ring")
    if competitors.get("dc_fast_within_3km") is None:
        drop("competitors", "the DC-fast count within 3 km")
    drop("competitors", "measured busyness at every neighbour (waits on the poller)")

    if payload.get("public_context") is not None:
        for gap in public_context_gaps(payload):
            drop("provenance", gap)

    # 10 and 11 · what R10 added.
    if not payload.get("model_assumptions"):
        drop("ledger", "the engine's own assumption ledger - the input table prints alone")
    if not payload.get("generated_at"):
        drop("provenance", "the date, so the document record cannot say when it was made")

    return tuple(
        SectionCoverage(n=n, id=sid, title=title, dropped=tuple(dropped[sid]))
        for n, sid, title in SECTION_IDS
    )
