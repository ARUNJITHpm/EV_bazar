"""Part 4 map and district browser acceptance."""

from __future__ import annotations

import argparse

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--dev-url", required=True)
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.dev_url + "/data/map-demo?fixtures=1", wait_until="networkidle")
        expect(page.locator("h1")).to_have_text("District map development demo")
        shape = page.locator(".analytics-map-district").first
        assert "missing" in (shape.get_attribute("fill") or "")
        page.get_by_label("Find a district on this map").fill("Test District 01")
        button = page.get_by_role("button", name="Test District 01 · Test State")
        button.focus()
        page.keyboard.press("Enter")
        expect(page.get_by_role("status")).to_contain_text("Not enough data yet")
        expect(page.locator(".analytics-map-selected")).to_have_count(1)
        expect(page.locator("tbody tr td").last).to_have_text("Not enough data yet")
        page.get_by_label("Map indicator").select_option("chargers")
        expect(page.locator("tbody tr td").last).to_have_text("1")
        for width in (375, 768, 1440):
            page.set_viewport_size({"width": width, "height": 1000})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        for javascript in (False, True):
            context = browser.new_context(java_script_enabled=javascript)
            production = context.new_page()
            production.goto(args.url + "/data/district/ernakulam-555", wait_until="networkidle")
            expect(production.get_by_role("heading", name="Key figures")).to_have_count(1)
            expect(production.get_by_role("heading", name="What we don’t know yet")).to_have_count(
                1
            )
            expect(production.get_by_text("Not enough data yet", exact=True)).to_have_count(6)
            assert (
                production.locator('meta[name="robots"]').get_attribute("content")
                == "noindex, follow"
            )
            production.goto(args.url + "/data/map-demo?fixtures=1", wait_until="networkidle")
            expect(production.locator("h1")).to_have_text("Data page unavailable")
            context.close()
        assert not errors, errors
        browser.close()
    print(
        "PASS: missing-data hatching, keyboard selection, observed inventory, responsive map, "
        "static empty district and production demo exclusion."
    )


if __name__ == "__main__":
    main()
