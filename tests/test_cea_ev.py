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
    assert kerala.fy_to_date is not None
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
    kseb = by_name(report.discoms, "KSEB").fy_to_date
    assert kseb is not None and kseb["total_kwh"] == 25_510_000


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


def test_october_2024_three_column_layout_and_asterisks() -> None:
    # Reports up to late 2024 have no "other than PCS" column and print "*"
    # for a value not reported; Tamil Nadu's "*" row once hid inside the next
    # state's name and broke the Grand Total check.
    report = parse_report(pages("2024_10"))
    assert report.report_month == dt.date(2024, 10, 1)
    assert report.fy_start == dt.date(2024, 4, 1)
    assert report.warnings == []
    tamil = by_name(report.states, "Tamil Naidu")  # the source's spelling
    assert tamil.month == {
        "pcs_kwh": 1_340_000,
        "heavy_duty_pcs_kwh": None,
        "other_kwh": None,  # no such column in this layout
        "total_kwh": 1_340_000,
    }
    telangana = by_name(report.states, "Telangana").fy_to_date
    assert telangana is not None and telangana["total_kwh"] == 9_490_000
    assert report.india is not None
    assert report.india.fy_to_date["total_kwh"] == 439_460_000
    assert lgd_state_code("Tamil Naidu", {"TAMIL NADU": 33}) == 33


def test_april_2024_month_only_layout() -> None:
    report = parse_report(pages("2024_04"))
    assert report.report_month == dt.date(2024, 4, 1)
    assert report.fy_start is None
    assert all(r.fy_to_date is None for r in report.states)
    assert report.india is not None
    assert report.india.month["total_kwh"] == 52_860_000
    assert by_name(report.states, "Kerala").month["total_kwh"] == 960_000


def test_june_2024_repeated_page_title_is_not_a_name() -> None:
    # The title reprinted above a page's repeated header once glued itself to
    # "Karnataka", filing Karnataka's DISCOMs under Andhra Pradesh.
    report = parse_report(pages("2024_06"))
    assert report.warnings == []
    assert [r.discom for r in report.discoms if r.state_name == "Andhra Pradesh"] == [
        "APEPDCL",
        "APSPDCL",
    ]
    assert "BESCOM" in [r.discom for r in report.discoms if r.state_name == "Karnataka"]


def test_july_2025_two_digit_year_in_window_line() -> None:
    report = parse_report(pages("2025_07"))
    assert report.report_month == dt.date(2025, 7, 1)
    assert report.fy_start == dt.date(2025, 4, 1)
    assert report.india is not None
    assert report.india.month["total_kwh"] == 115_390_000


def test_november_2025_footer_fused_onto_a_row() -> None:
    # "CEA-PL-14-26/11/2025-PDM Division I/64009/2026Odisha 0.10 ..."
    report = parse_report(pages("2025_11"))
    assert report.warnings == []
    assert "TPCODL" in [r.discom for r in report.discoms if r.state_name == "Odisha"]
    assert not any("CEA-PL" in (r.discom or "") for r in report.discoms)


def test_january_2026_table_across_pages_with_wrapped_region_and_total() -> None:
    # The state table runs onto page 5, "North " / "Eastern" and "Grand " /
    # "Total" wrap, and the DISCOM table starts mid-page.
    report = parse_report(pages("2026_01"))
    assert report.report_month == dt.date(2026, 1, 1)
    assert report.warnings == []
    assert by_name(report.states, "Assam").region == "North Eastern"
    assert report.india is not None
    assert report.india.month["total_kwh"] == 147_150_000
    assert report.india.fy_to_date is not None
    assert report.india.fy_to_date["total_kwh"] == 1_262_500_000


def test_reports_whose_tables_are_images_are_refused() -> None:
    with pytest.raises(ReportFormatError, match="images"):
        parse_report(pages("2025_01_images"))
