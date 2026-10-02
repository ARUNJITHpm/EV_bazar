"""Exercise homepage routes and print using an existing flagged report fixture."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
DEMO = "KL-TVM-DEMO-001"
SECTIONS = [
    "verdict",
    "money",
    "judged",
    "site",
    "financials",
    "operators",
    "competitors",
    "change",
    "statistical",
    "ledger",
    "provenance",
    "disclosure",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Existing preview server; otherwise start one")
    parser.add_argument(
        "--output", type=Path, default=REPO / "frontend/node_modules/.cache/report-home"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    payload = json.loads(
        (REPO / "tests/fixtures/part9-stored-report.json").read_text(encoding="utf-8")
    )
    assert payload["demo"] is True
    for operator in payload["cpo"]:
        operator["irr_p50_pct"] = None
    server = None
    url = args.url or "http://127.0.0.1:4203"
    try:
        if not args.url:
            server = subprocess.Popen(
                [
                    "node",
                    "node_modules/vite/bin/vite.js",
                    "preview",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "4203",
                    "--strictPort",
                ],
                cwd=REPO / "frontend",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Preview server exited")
                try:
                    urllib.request.urlopen(url, timeout=1).close()
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Preview server did not start")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width in [390, 1440]:
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.route(
                    "**/api/internal/reports/**", lambda route: route.fulfill(json=payload)
                )
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
                page.goto(url)
                page.locator("[data-report-ready]").wait_for()
                expect(page.get_by_role("heading", level=1)).to_have_text(payload["site"]["name"])
                assert (
                    page.locator("[data-report-section]").evaluate_all(
                        "nodes => nodes.map(n => n.dataset.reportSection)"
                    )
                    == SECTIONS
                )
                page.screenshot(path=str(args.output / f"viewport-{width}.png"))
                overflow = page.evaluate(
                    "() => Array.from(document.querySelectorAll('body *'))"
                    ".filter(n => n.getBoundingClientRect().right > innerWidth + 1)"
                    ".slice(0,12).map(n => ({tag:n.tagName,cls:n.className,"
                    "right:n.getBoundingClientRect().right}))"
                )
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), overflow
                expect(
                    page.get_by_role("link", name="Assess my site", exact=True)
                ).to_have_attribute("href", "/assess")
                expect(page.get_by_role("link", name="About", exact=True)).to_have_attribute(
                    "href", "/about"
                )
                page.evaluate("document.fonts.ready")
                page.screenshot(path=str(args.output / f"home-{width}.png"), full_page=True)
                axe = (REPO / "frontend/node_modules/axe-core/axe.min.js").read_text(
                    encoding="utf-8"
                )
                page.add_script_tag(content=axe)
                violations = page.evaluate(
                    "async () => (await axe.run(document, {runOnly:{type:'tag',"
                    "values:['wcag2a','wcag2aa','wcag21aa']}})).violations.map(v => "
                    "({id:v.id,nodes:v.nodes.map(n=>n.target)}))"
                )
                assert not violations, violations
                if width == 1440:
                    pdf = page.pdf(print_background=True, prefer_css_page_size=True)
                    assert pdf.startswith(b"%PDF") and len(pdf) > 10_000
                    (args.output / "sample-report.pdf").write_bytes(pdf)
                page.get_by_role("link", name="About", exact=True).click()
                expect(page).to_have_url(url + "/about")
                page.reload()
                expect(page.get_by_role("heading", level=1)).to_be_visible()
                expect(page).to_have_title(
                    "About Chargeworthy — site assessments and operator matching"
                )
                page.goto(url + "/report/sample")
                expect(page).to_have_url(url + f"/report/{DEMO}")
                page.locator("[data-report-ready]").wait_for()
                page.goto(url + "/data")
                expect(page.get_by_role("heading", level=1)).to_be_visible()
                page.goto(url + "/assess")
                expect(
                    page.get_by_role("textbox", name="Search for the site location")
                ).to_be_visible()
                page.goto(url + "/owner")
                expect(
                    page.get_by_role("heading", name="Welcome. Are you new here?")
                ).to_be_visible()
                page.goto(url + "/not-a-real-route")
                expect(page.get_by_role("heading", name="Page not found")).to_be_visible()
                assert not errors, errors
                context.close()
            browser.close()
        print(
            "PASS: homepage at 390/1440px, twelve sections, nullable IRR, "
            "route navigation/refresh, accessibility and PDF"
        )
    finally:
        if server is not None:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
