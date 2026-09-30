"""Part 1 acceptance against a built preview or Caddy URL (no backend needed).

Run after `npm run build --prefix frontend` and starting a preview server:
    python scripts/check_analytics_shell.py --url http://127.0.0.1:4187
Screenshots are saved only when --screenshots is supplied.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--dev-url", help="Optional Vite dev URL for fixture isolation acceptance")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    paths = {
        "/data": "Chargeworthy Data",
        "/data/vehicles": "Vehicles",
        "/data/charging-network": "Charging network",
        "/data/electricity": "Electricity",
        "/data/usage": "Usage",
        "/data/corridors": "Corridors",
        "/data/method": "Method",
        "/data/methodology": "Methodology",
        "/data/sources": "Sources",
        "/data/district": "District data",
        "/data/district/unpublished-district": "District data",
        "/data/district/ernakulam-555": "Ernakulam",
        "/data/insights": "Insights",
        "/data/insights/unpublished-article": "Insights",
        "/data/weekly": "One question, one chart",
        "/data/weekly/unpublished-post": "One question, one chart",
        "/data/unknown-topic": "Data page unavailable",
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for javascript in (False, True):
            context = browser.new_context(java_script_enabled=javascript)
            page = context.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
            page.on(
                "console",
                lambda message, errors=errors: (
                    errors.append(message.text)
                    if "hydrat" in message.text.lower() and message.type == "error"
                    else None
                ),
            )
            for path, heading in paths.items():
                response = page.goto(base + path, wait_until="networkidle")
                assert response and response.ok, (path, response)
                assert page.locator("h1").inner_text() == heading, (javascript, path)
                assert page.locator("main").inner_text().strip(), path
                assert "CC BY 4.0" in page.locator("footer").inner_text(), path
                if path != "/data":
                    assert page.locator('meta[name="robots"]').get_attribute("content") == (
                        "noindex, follow"
                    ), path
            assert not errors, errors
            context.close()
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.goto(base + "/data", wait_until="networkidle")
        page.get_by_label("District name").fill("Ernakulam")
        page.locator("#district-search-results").get_by_role("link", name="Ernakulam").click()
        expect(page.locator("h1")).to_have_text("Ernakulam")
        expect(
            page.get_by_text("No district indicators have been published", exact=False)
        ).to_be_visible()
        page.goto(base + "/data", wait_until="networkidle")
        page.get_by_label("Search Chargeworthy Data").fill("electri")
        expect(page.get_by_role("status")).to_have_text("1 result found")
        page.locator("#data-search-results").get_by_role("link").click()
        expect(page.locator("h1")).to_have_text("Electricity")
        page.reload(wait_until="networkidle")
        assert page.locator("h1").inner_text() == "Electricity"
        page.go_back(wait_until="networkidle")
        expect(page.locator("h1")).to_have_text("Chargeworthy Data")
        page.get_by_role("link", name="Chargeworthy home").click()
        assert page.locator("header").get_by_role("link", name="Data", exact=True).count() == 1
        assert page.locator("#home-data-title").inner_text() == "Chargeworthy Data"
        assert page.locator('meta[name="robots"]').count() == 0
        assert page.title() == "Chargeworthy — will your land pay for a charger?"
        page.get_by_role("link", name="Explore the data").click()
        expect(page.locator("h1")).to_have_text("Chargeworthy Data")
        expect(page.locator("h1")).to_be_in_viewport()
        for width in (375, 768, 1440):
            page.set_viewport_size({"width": width, "height": 1000})
            page.goto(base + "/data", wait_until="networkidle")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
            if args.screenshots:
                args.screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(args.screenshots / f"data-{width}.png"), full_page=True)
        page.goto(base + "/data")
        page.keyboard.press("Tab")
        assert page.locator(":focus").inner_text() == "Skip to content"
        page.keyboard.press("Enter")
        assert page.locator(":focus").get_attribute("id") == "data-main"
        page.goto(base + "/data?fixtures=1", wait_until="networkidle")
        expect(page.get_by_role("complementary", name="Test data")).to_have_count(0)
        expect(page.get_by_text("Test Station 01", exact=True)).to_have_count(0)
        if args.dev_url:
            page.goto(args.dev_url.rstrip("/") + "/data?fixtures=1", wait_until="networkidle")
            expect(page.get_by_role("complementary", name="Test data")).to_be_visible()
            expect(page.get_by_text("Test Station 01", exact=True)).to_be_visible()
            page.goto(args.dev_url.rstrip("/") + "/data", wait_until="networkidle")
            expect(page.get_by_role("complementary", name="Test data")).to_have_count(0)
        context.close()
        browser.close()
    print(
        f"PASS: {len(paths)} routes with and without JavaScript; "
        "hydration, search, navigation, metadata, keyboard and 3 viewport widths."
    )


if __name__ == "__main__":
    main()
