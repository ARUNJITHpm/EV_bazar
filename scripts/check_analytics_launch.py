"""Repeatable Part 9 browser audit against a production build, never private APIs.

Requires frontend's pinned axe-core. --output writes measurements, not private data.
Performance uses cold-cache Chromium, 4x CPU slowdown and 4G (9 Mbps, 150 ms).
This is a lab approximation, not a physical Android or production CDN measurement.
"""

from __future__ import annotations

import argparse
import json
import re
from html import unescape
from pathlib import Path

from playwright.sync_api import Request, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
PATHS = (
    "/data",
    "/data/electricity",
    "/data/district/ernakulam-555",
    "/data/insights/what-does-the-district-reference-cover",
    "/data/weekly/how-many-entries-in-the-district-reference",
    "/data/sources",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", action="store_true", help="Record defects without refusing")
    parser.add_argument(
        "--skip-performance",
        action="store_true",
        help="Functional CI only; lab performance is a separate measured check",
    )
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument(
        "--report-payload",
        type=Path,
        help="Existing stored demo payload; intercept only, never regenerate",
    )
    args = parser.parse_args()
    results: dict = {"pages": [], "performance": [], "failures": []}
    failures = results["failures"]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in (390, 1440):
            context = browser.new_context(viewport={"width": width, "height": 900})
            page = context.new_page()
            page.on("pageerror", lambda error: failures.append(str(error)))
            for path in PATHS:
                requests = []

                def listener(request: Request, requests: list[str] = requests) -> None:
                    requests.append(request.url)

                page.on("request", listener)
                page.goto(args.url.rstrip("/") + path, wait_until="networkidle")
                expect(page.locator("h1")).to_have_count(1)
                page.add_script_tag(path=str(REPO / "frontend/node_modules/axe-core/axe.min.js"))
                report = page.evaluate("async () => await axe.run(document)")
                violations = [
                    {
                        "id": v["id"],
                        "impact": v["impact"],
                        "targets": [n["target"] for n in v["nodes"]],
                    }
                    for v in report["violations"]
                ]
                serious = [v for v in violations if v["impact"] in ("serious", "critical")]
                if serious:
                    failures.append({"path": path, "width": width, "axe": serious})
                if not page.evaluate("document.documentElement.scrollWidth <= innerWidth"):
                    failures.append({"path": path, "width": width, "overflow": True})
                if args.screenshots:
                    args.screenshots.mkdir(parents=True, exist_ok=True)
                    page.screenshot(
                        path=str(
                            args.screenshots / f"{path.strip('/').replace('/', '-')}-{width}.png"
                        ),
                        full_page=True,
                    )
                if not page.locator("figure.analytics-chart").count() and any(
                    re.search(r"/Chart-[^/]+\.js", url) for url in requests
                ):
                    failures.append({"path": path, "chart_code_without_chart": True})
                for figure in page.locator("figure.analytics-chart").all():
                    expect(figure.locator("figcaption")).to_contain_text("Source:")
                    expect(figure.locator("figcaption time").first).to_be_visible()
                    figure.get_by_role("button", name="Table", exact=True).click()
                    expect(figure.get_by_role("table")).to_be_visible()
                    for selection in ("current selection", "all data"):
                        with page.expect_download() as download:
                            figure.get_by_role(
                                "button", name=f"Download CSV ({selection})", exact=True
                            ).click()
                        assert Path(download.value.path()).stat().st_size > 0
                results["pages"].append(
                    {
                        "path": path,
                        "width": width,
                        "axe": violations,
                        "charts": page.locator("figure.analytics-chart").count(),
                    }
                )
                page.remove_listener("request", listener)
            page.goto(args.url.rstrip("/") + "/data/district/ernakulam-555")
            expect(page.get_by_text("Not enough data yet", exact=True).first).to_be_visible()
            assert "noindex" in page.locator('meta[name="robots"]').get_attribute("content")
            page.goto(args.url.rstrip("/") + "/data?fixtures=1")
            expect(page.get_by_role("complementary", name="Test data")).to_have_count(0)
            context.close()
        # Quiet home integration and keyboard path.
        page = browser.new_page()
        page.goto(args.url.rstrip("/") + "/", wait_until="networkidle")
        expect(page.locator("header").get_by_role("link", name="Data", exact=True)).to_have_count(1)
        expect(page.locator("#home-data-title")).to_have_text("Chargeworthy Data")
        page.get_by_role("link", name="Explore the data").click()
        expect(page.locator("h1")).to_have_text("Chargeworthy Data")
        page.goto(args.url.rstrip("/") + "/data")
        page.keyboard.press("Tab")
        expect(page.locator(":focus")).to_have_text("Skip to content")
        page.keyboard.press("Enter")
        assert page.locator(":focus").get_attribute("id") == "data-main"
        page.close()
        # Three independent cold navigations per page. FCP is readable prerendered
        # content; report LCP separately rather than calling FCP full interactivity.
        for path in () if args.skip_performance else (PATHS[0], PATHS[2]):
            for run in range(3):
                context = browser.new_context(
                    viewport={"width": 390, "height": 844}, is_mobile=True, device_scale_factor=2
                )
                page = context.new_page()
                # Paint metrics and RAF enhancement require a visible tab.
                # Background Chromium pages can complete network work without
                # producing a paint, which is not an Android foreground load.
                page.bring_to_front()
                cdp = context.new_cdp_session(page)
                cdp.send("Network.enable")
                cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
                cdp.send(
                    "Network.emulateNetworkConditions",
                    {
                        "offline": False,
                        "latency": 150,
                        "downloadThroughput": 9_000_000 / 8,
                        "uploadThroughput": 1_500_000 / 8,
                    },
                )
                cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
                page.add_init_script(
                    "window.labLcp=0; new PerformanceObserver(l => "
                    "{for(const e of l.getEntries()) window.labLcp=e.startTime})"
                    ".observe({type:'largest-contentful-paint',buffered:true})"
                )
                page.goto(args.url.rstrip("/") + path, wait_until="networkidle")
                page.wait_for_function(
                    "performance.getEntriesByName('first-contentful-paint').length > 0",
                    timeout=10_000,
                )
                measurement = page.evaluate("""() => ({
                  fcp_ms: performance.getEntriesByName('first-contentful-paint')[0]?.startTime,
                  lcp_ms: window.labLcp,
                  resources: performance.getEntriesByType('resource').map(r => ({
                    name: new URL(r.name).pathname, bytes: r.transferSize}))
                })""")
                results["performance"].append({"path": path, "run": run + 1, **measurement})
                if measurement["fcp_ms"] is None or measurement["fcp_ms"] >= 2000:
                    failures.append({"path": path, "run": run + 1, "fcp_ms": measurement["fcp_ms"]})
                context.close()
        # Static HTML remains usable before any enhancement loads.
        context = browser.new_context(java_script_enabled=False)
        for path in PATHS:
            page = context.new_page()
            page.goto(args.url.rstrip("/") + path)
            expect(page.locator("h1")).to_be_visible()
            if "/insights/" in path or "/weekly/" in path:
                expect(page.get_by_role("table").first).to_be_visible()
            page.close()
        context.close()
        if args.report_payload:
            payload = json.loads(args.report_payload.read_text(encoding="utf-8"))
            assert payload.get("demo") is True, "PDF acceptance requires a labelled demo fixture"
            page = browser.new_page()
            page.route("**/api/internal/reports/**", lambda route: route.fulfill(json=payload))
            page.goto(args.url.rstrip("/") + "/report/PART9-STORED-FIXTURE")
            page.locator("[data-report-ready]").wait_for(timeout=20_000)
            page.evaluate("document.fonts.ready")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            pdf = args.output.with_suffix(".pdf")
            page.pdf(path=str(pdf), print_background=True, prefer_css_page_size=True)
            assert pdf.read_bytes().startswith(b"%PDF")
            results["stored_report_pdf"] = True
            page.close()
        browser.close()
    titles, descriptions = set(), set()
    published = json.loads(
        (REPO / "frontend/dist/analytics-data/published-routes.json").read_text(encoding="utf-8")
    )
    documents = list((REPO / "frontend/dist/data").rglob("index.html"))
    for document in documents:
        text = document.read_text(encoding="utf-8")
        title = unescape(re.search(r"<title>(.*?)</title>", text).group(1))
        description = unescape(
            re.search(r'<meta\s+name="description"\s+content="([^"]+)"', text).group(1)
        )
        assert title not in titles, f"Duplicate title: {document.relative_to(REPO)}"
        assert description not in descriptions, (
            f"Duplicate description: {document.relative_to(REPO)}"
        )
        titles.add(title)
        descriptions.add(description)
        route = "/" + document.parent.relative_to(REPO / "frontend/dist").as_posix()
        if route in published:
            assert 'content="index, follow"' in text
        else:
            assert 'content="noindex, follow"' in text
    results["seo"] = {
        "unique_documents": len(documents),
        "published_routes": len(published),
        "sitemap_generated": (REPO / "frontend/dist/sitemap.xml").is_file(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Audited {len(results['pages'])} page/viewport pairs; {len(failures)} failures.")
    if failures and not args.baseline:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
