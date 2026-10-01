"""Browser checks for public methodology, source links and CSV licensing."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for javascript in (False, True):
            context = browser.new_context(java_script_enabled=javascript, accept_downloads=True)
            page = context.new_page()
            errors = []
            page.on(
                "pageerror", lambda error, current_errors=errors: current_errors.append(str(error))
            )
            for path in ("/data/methodology", "/data/sources"):
                page.goto(args.url + path, wait_until="networkidle")
                expect(page.locator("h1")).to_have_count(1)
                expect(page.locator("footer")).to_contain_text("CC BY 4.0")
                assert (
                    page.locator('meta[name="robots"]').get_attribute("content") == "index, follow"
                )
                for width in (375, 768, 1440):
                    page.set_viewport_size({"width": width, "height": 1000})
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            expect(
                page.get_by_role("heading", name="LGD district reference snapshot")
            ).to_have_count(1)
            expect(
                page.get_by_role("link", name="CC0-1.0 (india-geodata release files)")
            ).to_have_count(1)
            chart_link = page.locator(
                'a[href="/data/weekly/how-many-entries-in-the-district-reference#how-many-entries-in-the-district-reference-chart"]'
            )
            chart_link.click()
            assert "#" in page.url
            expect(page.locator("figure")).to_be_visible()
            page.get_by_role("link", name="Corrections log", exact=True).click()
            expect(page.get_by_role("heading", name="Corrections", exact=True)).to_be_in_viewport()
            expect(
                page.get_by_text("No approved real validation summary", exact=False)
            ).to_have_count(1)
            expect(page.get_by_text("currently has no affiliation", exact=False)).to_have_count(1)
            expect(page.get_by_text("do not plan to own them", exact=False)).to_have_count(1)
            expect(page.get_by_text("business model is based", exact=False)).to_have_count(1)
            assert "awaiting confirmation" not in page.locator("main").inner_text()
            assert not errors, errors
            context.close()
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.goto(
            args.url + "/data/weekly/how-many-entries-in-the-district-reference",
            wait_until="networkidle",
        )
        with page.expect_download() as download:
            page.get_by_role("button", name="Download CSV (all data)").click()
        csv = Path(download.value.path()).read_text(encoding="utf-8-sig")
        assert csv.startswith("# Chargeworthy Data: ")
        assert "CC BY 4.0" in csv and "CC0-1.0" in csv and "source_licences" in csv
        catalogue = context.request.get(args.url + "/analytics-data/catalogue.json").json()
        for dataset in catalogue["datasets"]:
            response = context.request.get(args.url + dataset["data_url"])
            raw = response.body()
            assert hashlib.sha256(raw).hexdigest() == dataset["sha256"]
            if dataset["data_url"].endswith(".csv"):
                preamble = raw.decode("utf-8-sig").splitlines()[0]
                licence = json.loads(preamble.removeprefix("# Chargeworthy Data: "))
                assert licence["source_data_licence"] == dataset["metadata"]["licence"]
                assert licence["source_url"] == dataset["metadata"]["source_url"]
        page.goto(args.url + "/data/methodology", wait_until="networkidle")
        page.set_viewport_size({"width": 375, "height": 900})
        page.screenshot(path="D:/EV_Bazar/local_scratch/part7-method-mobile.png", full_page=True)
        context.close()
        browser.close()
    print(
        "PASS: methodology and sources with/without JS, correction anchors, "
        "responsive pages and licensed/checksummed CSVs"
    )


if __name__ == "__main__":
    main()
