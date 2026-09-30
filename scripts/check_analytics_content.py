"""Browser acceptance for public insight and weekly content."""

from __future__ import annotations

import argparse

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    insight = "/data/insights/what-does-the-district-reference-cover"
    weekly = "/data/weekly/how-many-entries-in-the-district-reference"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for javascript in (False, True):
            context = browser.new_context(java_script_enabled=javascript, accept_downloads=True)
            page = context.new_page()
            errors: list[str] = []
            page.on(
                "pageerror", lambda error, current_errors=errors: current_errors.append(str(error))
            )
            for path, charts in ((insight, 2), (weekly, 1)):
                page.goto(args.url + path, wait_until="networkidle")
                expect(page.locator("h1")).to_contain_text("?")
                expect(page.locator("figure.analytics-chart")).to_have_count(charts)
                assert (
                    page.locator('meta[name="robots"]').get_attribute("content") == "index, follow"
                )
                expect(page.get_by_text("783", exact=True).first).to_have_count(1)
                if path == insight:
                    expect(page.get_by_text("Updated on", exact=False)).to_have_count(1)
                    expect(page.get_by_role("heading", name="Changelog")).to_have_count(1)
                else:
                    expect(page.get_by_text("Caption for sharing")).to_have_count(1)
                for width in (375, 768, 1440):
                    page.set_viewport_size({"width": width, "height": 1000})
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                if not javascript:
                    assert page.locator("table").first.is_visible()
            if javascript:
                page.get_by_role("button", name="Table", exact=True).click()
                expect(page.get_by_role("table")).to_be_visible()
                with page.expect_download() as download:
                    page.get_by_role(
                        "button", name="Download CSV (current selection)", exact=True
                    ).click()
                assert download.value.suggested_filename.endswith(".csv")
                page.goto(args.url + "/data/weekly?vertical=usage", wait_until="networkidle")
                expect(page.get_by_text("No posts have been published", exact=False)).to_have_count(
                    1
                )
                page.get_by_role("link", name="Method", exact=True).click()
                assert "vertical=method" in page.url
                expect(
                    page.get_by_role(
                        "link", name="How many district entries are in our archived reference?"
                    )
                ).to_have_count(1)
            page.goto(args.url + "/data/insights/unknown", wait_until="networkidle")
            assert page.locator('meta[name="robots"]').get_attribute("content") == "noindex, follow"
            assert not errors, errors
            context.close()
        browser.close()
    print(
        "PASS: articles, dates, changelog, live charts, CSV, URL filters and responsive/no-JS views"
    )


if __name__ == "__main__":
    main()
