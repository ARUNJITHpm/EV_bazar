"""CEA monthly EV charging electricity reports - parser and fetch helpers.

The fixtures are the text pypdf extracted from two real reports (December 2025
and March 2026), so the layout quirks are the source's own: names wrapped
mid-word ("Maharashtr" / "a"), headers wrapped differently between months,
states that report nothing ("-").
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from app.domain.cea.parse import (
    ReportFormatError,
    lgd_state_code,
    mu_to_kwh,
    parse_report,
)
from scripts.fetch_cea_ev import _PDF

FIXTURES = Path(__file__).parent / "fixtures" / "cea"


def pages(month: str) -> list[str]:
    return json.loads((FIXTURES / f"ev_report_{month}.json").read_text(encoding="utf-8"))


def by_name(rows, name):  # type: ignore[no-untyped-def]
    return next(r for r in rows if (r.discom or r.state_name) == name)


def test_march_2026_state_rows_and_india_total() -> None:
    report = parse_report(pages("2026_03"))
    assert report.report_month == dt.date(2026, 3, 1)
    assert report.fy_start == dt.date(2025, 4, 1)
    assert len(report.states) == 33
    kerala = by_name(report.states, "Kerala")
    assert kerala.region == "Southern"
    assert kerala.month == {
        "pcs_kwh": 1_720_000,
        "heavy_duty_pcs_kwh": 700_000,
        "other_kwh": None,  # "-" is not reported, never zero
        "total_kwh": 2_420_000,
    }
    assert kerala.fy_to_date["total_kwh"] == 25_860_000
    assert report.india is not None
    assert report.india.month["total_kwh"] == 149_590_000
    assert report.india.fy_to_date["total_kwh"] == 1_558_690_000
    assert report.warnings == []


def test_wrapped_names_are_rejoined() -> None:
    report = parse_report(pages("2026_03"))
    names = {r.state_name for r in report.states}
    assert "Dadra & Nagar Haveli and Daman & Diu" in names
    discoms = {r.discom for r in report.discoms}
    assert {"Noida Power (NPCL)", "Brihan Mumbai (BEST)", "Thrissur Corporation"} <= discoms


def test_discoms_belong_to_the_state_listed_above_them() -> None:
    report = parse_report(pages("2026_03"))
    kerala = [r.discom for r in report.discoms if r.state_name == "Kerala"]
    assert kerala == ["Cochin Port Authority", "KSEB", "Technopark", "Thrissur Corporation"]
    assert by_name(report.discoms, "KSEB").fy_to_date["total_kwh"] == 25_510_000


def test_december_2025_mid_word_breaks_and_wrapped_header() -> None:
    # "Maharashtr" / "a" and "MPMKVVC" / "L" are broken inside the word; a
    # space would misname them and file Maharashtra's DISCOMs under MP.
    report = parse_report(pages("2025_12"))
    assert report.report_month == dt.date(2025, 12, 1)
    assert report.warnings == []
    assert [r.discom for r in report.discoms if r.state_name == "Madhya Pradesh"] == [
        "MPMKVVCL",
        "MPPKVVCL",
    ]
    assert "MSEDCL" in [r.discom for r in report.discoms if r.state_name == "Maharashtra"]


def test_state_rows_that_do_not_add_up_are_refused() -> None:
    tampered = pages("2026_03")
    page = next(i for i, p in enumerate(tampered) if "State/UT wise" in p)
    tampered[page] = tampered[page].replace(
        "Kerala 1.72 0.70 - 2.42 18.22 7.64 - 25.86",
        "Kerala 9.72 0.70 - 2.42 18.22 7.64 - 25.86",
    )
    with pytest.raises(ReportFormatError, match="Grand Total"):
        parse_report(tampered)


def test_unrecognised_document_is_refused() -> None:
    with pytest.raises(ReportFormatError, match="not found"):
        parse_report(["Annual report", "nothing here"])


def test_mu_values_become_exact_kwh() -> None:
    assert mu_to_kwh("435.31") == 435_310_000
    assert mu_to_kwh("0.00") == 0
    assert mu_to_kwh("-") is None
    with pytest.raises(ReportFormatError):
        mu_to_kwh("n/a")


def test_cea_state_spellings_map_to_one_lgd_state_or_none() -> None:
    states = {
        "KERALA": 32,
        "JAMMU & KASHMIR": 1,
        "LADAKH": 37,
        "DADRA,NAGAR HAVELI,DAMAN & DIU": 38,
    }
    assert lgd_state_code("Kerala", states) == 32
    assert lgd_state_code("UT of J&K", states) == 1
    assert lgd_state_code("UT of Ladakh", states) == 37
    assert lgd_state_code("Dadra & Nagar Haveli and Daman & Diu", states) == 38
    assert lgd_state_code("UT of J&K and Ladakh", states) is None  # two states


def test_listing_links_are_recognised() -> None:
    html = (
        '<a href="https://cea.nic.in/wp-content/uploads/ev_charging_rep/2026/08/Mar_26_EV.pdf"'
        ' download>x</a><a href="https://cea.nic.in/wp-content/uploads/2021/03/other.pdf">y</a>'
    )
    assert _PDF.findall(html) == [
        "https://cea.nic.in/wp-content/uploads/ev_charging_rep/2026/08/Mar_26_EV.pdf"
    ]
