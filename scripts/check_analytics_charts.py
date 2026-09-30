"""Part 3 browser acceptance: development demo and production exclusion."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-url", required=True)
    parser.add_argument("--url", required=True, help="Production Vite preview or Caddy")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        demo = args.dev_url.rstrip("/") + "/data/chart-demo?fixtures=1"
        page.goto(demo, wait_until="networkidle")
        expect(page.locator("h1")).to_have_text("Chart development demo")
        expect(page.locator("figure")).to_have_count(5)
        expect(page.get_by_role("img")).to_have_count(6)
        figure = page.locator("#demo-line")
        figure.get_by_label("Region (state or district)").fill("north")
        figure.get_by_label("Time period").select_option("2026-01")
        figure.get_by_label("Indicator").select_option("Energy")
        figure.get_by_role("button", name="Table", exact=True).click()
        page.reload(wait_until="networkidle")
        expect(figure.get_by_label("Region (state or district)")).to_have_value("north")
        expect(figure.get_by_label("Time period")).to_have_value("2026-01")
        expect(figure.get_by_label("Indicator")).to_have_value("Energy")
        expect(figure.locator("tbody tr")).to_have_count(1)
        expect(figure.locator("tbody tr td").nth(5)).to_have_text("10,000")
        for label, count in (
            ("Download CSV (current selection)", 1),
            ("Download CSV (all data)", 6),
        ):
            with page.expect_download() as pending:
                figure.get_by_role("button", name=label, exact=True).click()
            download = pending.value
            with Path(download.path()).open(encoding="utf-8-sig", newline="") as source:
                rows = list(csv.DictReader(source))
            assert len(rows) == count, rows
            assert rows[0]["value"] == "10000"
            assert rows[0]["p10"] == "8000" and rows[0]["p90"] == "14000"
            assert "Test fixture only" in rows[0]["source_licences"]
            assert rows[0]["renderer_version"] == "analytics_svg_v1"
            if count == 6:
                assert rows[4]["value"] == "" and rows[4]["sample_size"] == ""
        # Keyboard can switch back to the graphic without a pointer.
        figure.get_by_role("button", name="Chart", exact=True).focus()
        page.keyboard.press("Enter")
        expect(figure.get_by_role("img")).to_have_count(1)
        assert "demo-line.view" not in page.url
        page.go_back(wait_until="networkidle")
        expect(figure.locator("table")).to_have_count(1)
        page.goto(demo, wait_until="networkidle")
        for width in (375, 768, 1440):
            page.set_viewport_size({"width": width, "height": 1000})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
            if args.screenshots:
                args.screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(args.screenshots / f"charts-{width}.png"), full_page=True)
        page.goto(args.dev_url.rstrip("/") + "/data/chart-demo", wait_until="networkidle")
        expect(page.locator("h1")).to_have_text("Data page unavailable")
        for javascript in (False, True):
            context = browser.new_context(java_script_enabled=javascript)
            production = context.new_page()
            production.goto(
                args.url.rstrip("/") + "/data/chart-demo?fixtures=1", wait_until="networkidle"
            )
            expect(production.locator("h1")).to_have_text("Data page unavailable")
            expect(production.locator("figure")).to_have_count(0)
            expect(production.get_by_text("Test District North", exact=False)).to_have_count(0)
            context.close()
        assert not errors, errors
        browser.close()
    print(
        "PASS: five chart types, URL/reload/back, keyboard, both real CSV downloads, "
        "three widths and production demo exclusion."
    )


if __name__ == "__main__":
    main()
