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
    parser.add_argument("--browser-channel", help="Use an installed browser for local review")
    parser.add_argument("--axe-script", type=Path, default=REPO / "frontend/node_modules/axe-core/axe.min.js")
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
            browser = p.chromium.launch(channel=args.browser_channel)
            for width in [390, 1440]:
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.route(
                    "**/api/internal/reports/**", lambda route: route.fulfill(json=payload)
                )
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda error, errors=errors: errors.append(str(error) + "\n" + error.stack))
                page.goto(url)
                expect(page.get_by_role("heading", level=1)).to_have_text("Is your land suitable for EV charging?")
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
                navigation = page.get_by_role("navigation", name="Main navigation")
                for label, href in [("Home", "/"), ("Sample report", f"/report/{DEMO}"), ("Data", "/data"), ("Station owners", "/owner")]:
                    expect(navigation.get_by_role("link", name=label, exact=True)).to_have_attribute("href", href)
                page.evaluate("document.fonts.ready")
                axe = args.axe_script.read_text(encoding="utf-8")
                page.add_script_tag(content=axe)
                home_violations = page.evaluate("async () => (await axe.run(document, {runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})).violations.map(v => ({id:v.id,nodes:v.nodes.map(n=>n.target)}))")
                assert not home_violations, home_violations
                visible_words = len(page.locator("body").inner_text().split())
                assert visible_words < 600, visible_words
                assert page.locator("details[open]").count() == 0
                checklist = page.locator("details").first
                checklist.locator("summary").click()
                assert checklist.locator("li").count() == 34
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                checklist.locator("summary").click()
                page.locator("h1").scroll_into_view_if_needed()
                page.screenshot(path=str(args.output / f"viewport-{width}.png"))
                print(f"Homepage {width}px: {visible_words} visible words; accessibility and full checklist passed", flush=True)
                page.screenshot(path=str(args.output / f"home-{width}.png"), full_page=True)
                page.get_by_label("Site location", exact=True).first.fill("Ernakulam")
                page.get_by_role("button", name="Check my location", exact=True).first.click()
                expect(page.get_by_role("textbox", name="Search for the site location")).to_have_value("Ernakulam")
                page.goto(url + "/about")
                expect(page).to_have_url(url + "/")
                expect(page.get_by_role("heading", level=1)).to_have_text("Is your land suitable for EV charging?")
                page.goto(url + f"/report/{DEMO}")
                page.locator("[data-report-ready]").wait_for()
                expect(page.get_by_role("heading", level=1)).to_have_text(payload["site"]["name"])
                assert page.locator("[data-report-section]").evaluate_all("nodes => nodes.map(n => n.dataset.reportSection)") == SECTIONS
                if width == 390:
                    page.locator("#statistical").scroll_into_view_if_needed()
                    expect(page.get_by_text("Scroll sideways to read the full diagram.", exact=True).last).to_be_visible()
                    labels = page.locator("#statistical svg text").evaluate_all("nodes => nodes.map(n=>n.getBoundingClientRect().height)")
                    assert labels and min(labels) >= 12, labels
                    page.screenshot(path=str(args.output / "report-diagram-mobile.png"))
                    expect(page.get_by_text("Scroll sideways to see all columns.", exact=True).first).to_be_attached()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.emulate_media(media="print")
                assert page.locator(".report-diagram svg").first.evaluate("n => getComputedStyle(n).minWidth") == "0px"
                print_widths = page.locator(".report-diagram svg").evaluate_all("nodes => nodes.map(n => n.getBoundingClientRect().width)")
                assert max(print_widths) <= 688, print_widths
                page.emulate_media(media="screen")
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
                page.get_by_role("link", name="Home", exact=True).click()
                expect(page).to_have_url(url + "/")
                page.reload()
                expect(page.get_by_role("heading", level=1)).to_be_visible()
                expect(page).to_have_title(
                    "Chargeworthy — is your land suitable for EV charging?"
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
            "PASS: landing homepage at 390/1440px, location handoff, about redirect, twelve report sections, nullable IRR, "
            "route navigation/refresh, homepage and report accessibility, readable mobile diagrams and PDF"
        )
    finally:
        if server is not None:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
