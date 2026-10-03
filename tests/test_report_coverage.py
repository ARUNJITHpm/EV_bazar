"""What the twelve sections can print from a stored payload - Track B R12.

Every field the rebuild added is optional, so an older payload renders a
complete-looking document while quietly showing less. That is the correct
behaviour and it is invisible from the page, which is the whole reason this
module exists: the absence has to be counted somewhere or it is not a fact
anyone can act on.

What is worth pinning:

1. **An old payload drops the RIGHT things**, named the way a reader would
   name them - a column, a table, a chart rule - not by field.
2. **An empty payload is never mistaken for a complete one.**
3. **A column is earned by one row, not by all of them** - the same rule
   section 06 itself uses, or the panel sends someone hunting a bug in a
   section that is behaving correctly.

The fourth thing worth pinning is that TODAY's assembler output leaves only
the gaps we know about, and that lives in ``test_report_pipeline.py`` where
the assembler's own fixtures are.
"""

from __future__ import annotations

from typing import Any

from app.domain.report.coverage import SECTION_IDS, coverage


def _sections(payload: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    return {s.id: s.dropped for s in coverage(payload)}


def test_the_twelve_ids_are_the_documents_own_order() -> None:
    """The ids are the ``data-report-section`` attributes the print
    measurements select on, and the order is reading order. The frontend
    pins them against the rendered article; this only guards the shape."""
    assert len(SECTION_IDS) == 12
    assert [n for n, _, _ in SECTION_IDS] == list(range(1, 13))
    assert [sid for _, sid, _ in SECTION_IDS][:3] == ["verdict", "money", "judged"]
    assert [sid for _, sid, _ in SECTION_IDS][-1] == "disclosure"


def test_an_empty_payload_reports_gaps_rather_than_completeness() -> None:
    dropped = _sections({})
    # Not one section may come back clean: a payload with nothing in it must
    # never read like a finished document.
    assert dropped["site"], "section 04 must notice it has no checks at all"
    assert dropped["operators"], "section 06 must notice it has no operator rows"
    assert dropped["money"], "section 02 must notice it has no plain-money block"
    assert dropped["ledger"] and dropped["provenance"]


def test_an_old_payload_drops_exactly_what_it_cannot_fill() -> None:
    """A payload stored by economics 0.2.0: no plain money, no breakdowns,
    no engine ledger, no date - and it still validates, which is the point."""
    old: dict[str, Any] = {
        "breakeven": {"utilisation": 0.19},
        "financials": {"scenarios": [{"label": "central"}]},
        "competitors": {"within_3km": 8},
        "site_facts": [{"label": "Road class", "value": "NH", "unverified": False}],
        "cpo": [{"operator": "chargeMOD", "irr_p50_pct": 12.0}],
        "model_assumptions": [],
    }
    dropped = _sections(old)

    assert any("case table" in d for d in dropped["money"])
    assert any("running total" in d for d in dropped["financials"])
    assert any("full-cost rule row" in d for d in dropped["judged"])
    assert any("build-cost rule" in d for d in dropped["statistical"])
    assert any("build-cost lever" in d for d in dropped["change"])
    assert any("cash-per-year" in d for d in dropped["operators"])
    assert any("WHAT IT MEANS" in d for d in dropped["site"])
    assert any("engine's own assumption ledger" in d for d in dropped["ledger"])
    assert any("date" in d for d in dropped["provenance"])
    # 01 and 12 read from required fields and static prose; neither can
    # degrade, and a rule that claimed otherwise would be noise.
    assert dropped["verdict"] == ()
    assert dropped["disclosure"] == ()


def test_a_column_is_earned_by_one_row_not_by_all_of_them() -> None:
    """Section 06 gates whole columns on ``any``, so the coverage rule has
    to as well - one operator with a repair target is what earns the
    column, and reporting it as missing would send someone looking for a
    bug in the section."""
    payload: dict[str, Any] = {
        "cpo": [
            {"operator": "A", "repair_hours": None},
            {"operator": "B", "repair_hours": 4},
        ]
    }
    dropped = _sections(payload)
    assert not any("repair-target" in d for d in dropped["operators"])
    assert any("tie-in" in d for d in dropped["operators"])


def test_the_recovery_term_is_reported_apart_from_the_rule_itself() -> None:
    """Having the full-cost line but not R7's recovery term is a real state
    (economics 0.2.0 through 0.3.0), and section 09 then states the division
    without showing it. Reporting the whole rule as missing would be wrong."""
    payload: dict[str, Any] = {
        "breakeven": {"utilisation": 0.19, "full_cost_utilisation": 0.31},
    }
    dropped = _sections(payload)
    assert not any("dashed build-cost rule" in d for d in dropped["statistical"])
    assert any("recovery term" in d for d in dropped["statistical"])


def test_the_shortfall_in_site_checks_is_counted_not_asserted() -> None:
    payload: dict[str, Any] = {
        "site_facts": [
            {"label": f"check {i}", "group": "Access", "direction": "neutral", "means": "why"}
            for i in range(16)
        ]
    }
    dropped = _sections(payload)
    assert any("18 of the 34 checks" in d for d in dropped["site"])
    # The three things R4 added are all present, so none of them is reported.
    assert not any("grouped chapters" in d for d in dropped["site"])
    assert not any("markers" in d for d in dropped["site"])


def test_a_full_section_04_of_placeholders_is_still_reported_as_a_gap() -> None:
    """Owner's call on 2026-09-09 filled section 04 out to its promised
    length with UNVERIFIED rows, so the page no longer LOOKS short. Counting
    the placeholders is what stops "full" being read as "finished" - a
    placeholder nobody is counting is a placeholder that ships for ever."""
    payload: dict[str, Any] = {
        "site_facts": [
            {
                "label": f"check {i}",
                "group": "Access",
                "direction": "neutral",
                "means": "why",
                "unverified": i >= 14,
            }
            for i in range(39)
        ]
    }
    dropped = _sections(payload)
    # Long enough that the shortfall line is gone...
    assert not any("of the 34 checks" in d for d in dropped["site"])
    # ...and the real gap is named instead.
    assert any("25 of the 39 checks have no source behind them" in d for d in dropped["site"])


def test_measured_busyness_is_always_reported_missing() -> None:
    """It has never existed for any payload - it waits on the poller - and a
    section that silently omits it would let the gap disappear the day
    someone stops remembering it."""
    for payload in ({}, {"competitors": {"within_5km": 12, "dc_fast_within_3km": 3}}):
        dropped = _sections(dict(payload))
        assert any("busyness" in d for d in dropped["competitors"])
