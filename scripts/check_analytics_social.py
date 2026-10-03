"""Verify social PNGs, readable SVG bounds, browser exports and OG metadata locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def inspect_png(raw: bytes) -> tuple[int, int, dict]:
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", raw[16:24])
    offset = 8
    provenance = None
    while offset < len(raw):
        length = int.from_bytes(raw[offset : offset + 4], "big")
        kind = raw[offset + 4 : offset + 8]
        payload = raw[offset + 8 : offset + 8 + length]
        crc = int.from_bytes(raw[offset + 8 + length : offset + 12 + length], "big")
        assert zlib.crc32(kind + payload) == crc
        if kind == b"iTXt" and payload.startswith(b"Chargeworthy Data\0"):
            provenance = json.loads(payload.split(b"\0", 5)[5])
        offset += length + 12
    assert provenance is not None
    versions = provenance["versions"]
    assert all(
        versions[k]
        for k in (
            "model_version",
            "economics_version",
            "schema_version",
            "archetype_version",
            "tariff_effective_date",
            "renderer_version",
        )
    )
    assert versions["renderer_version"] == "analytics_social_v1"
    assert provenance["sources"] and provenance["original_content_licence"] == "CC BY 4.0"
    assert "Test Station" not in str(provenance) and "owner_id" not in str(provenance)
    return width, height, provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(accept_downloads=True)
        manifest = context.request.get(args.url + "/analytics-images/manifest.json").json()
        assert manifest["images"]
        counts = {}
        for image in manifest["images"]:
            counts.setdefault(image["article"], set()).add(image["format"])
            raw = context.request.get(args.url + image["path"]).body()
            assert hashlib.sha256(raw).hexdigest() == image["sha256"]
            width, height, provenance = inspect_png(raw)
            assert (width, height) == (image["width"], image["height"])
            assert provenance["rows"][0]["value"] == 783  # reviewed historical reference
            page = context.new_page()
            page.goto(args.url + image["path"].replace(".png", ".svg"))
            page.evaluate("""async () => {
                const fonts = [['Source Serif 4','SourceSerif4'],['IBM Plex Mono','IBMPlexMono']];
                for (const [family,file] of fonts) {
                    const face = new FontFace(family, `url(/analytics-fonts/${file}.ttf)`);
                    document.fonts.add(await face.load());
                }
                await document.fonts.ready;
            }""")
            violations = page.evaluate("""() => {
                const root = document.querySelector('svg');
                const width = root.viewBox.baseVal.width, height = root.viewBox.baseVal.height;
                return [...root.querySelectorAll('text')].flatMap(el => {
                    const b = el.getBBox(), size = Number(el.getAttribute('font-size'));
                    const bad = b.x < 0 || b.x+b.width > width || b.y < 0 || b.y+b.height > height;
                return bad || size*300/width < 10 ? [el.textContent] : [];
                });
            }""")
            assert not violations, violations
            page.close()
        assert all(formats == {"portrait", "square", "og"} for formats in counts.values())
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for slug in counts:
            page.goto(args.url + "/data/weekly/" + slug, wait_until="networkidle")
            og = page.locator('meta[property="og:image"]').get_attribute("content")
            assert og and og.endswith(slug + "-og.png")
            expect(page.get_by_role("button", name="Save image", exact=True)).to_be_enabled()
            for fmt, dimensions in (
                ("portrait", (1080, 1350)),
                ("square", (1080, 1080)),
                ("og", (1200, 630)),
            ):
                page.get_by_label("Image format").select_option(fmt)
                with page.expect_download() as download:
                    page.get_by_role("button", name="Save image", exact=True).click()
                raw = Path(download.value.path()).read_bytes()
                width, height, provenance = inspect_png(raw)
                assert (width, height) == dimensions
                assert provenance["rows"][0]["value"] == 783
                Path(f"local_scratch/part8-browser-{fmt}.png").write_bytes(raw)
            for size in (375, 768, 1440):
                page.set_viewport_size({"width": size, "height": 1000})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.get_by_label("Region (state or district)").fill("No matching place")
            expect(page.get_by_role("button", name="Save image", exact=True)).to_be_disabled()
            page.get_by_label("Region (state or district)").fill("")
            page.get_by_role("link", name="Sources", exact=True).first.click()
            expect(page.locator('meta[property="og:image"]')).to_have_count(0)
        assert not errors, errors
        page.set_viewport_size({"width": 960, "height": 600})
        gallery = "".join(
            f'<img src="{args.url}{image["path"]}" '
            f'style="width:300px;height:auto;vertical-align:top" alt="{image["format"]}">'
            for image in manifest["images"]
        )
        page.set_content(gallery)
        page.wait_for_function("[...document.images].every(image => image.complete)")
        page.screenshot(path="local_scratch/part8-300px.png")
        context.close()
        # Crawlers receive image metadata and working controls without JavaScript.
        context = browser.new_context(java_script_enabled=False)
        page = context.new_page()
        for slug in counts:
            page.goto(args.url + "/data/weekly/" + slug)
            assert page.locator('meta[property="og:image"]').count() == 1
            expect(page.locator("figure")).to_be_visible()
        context.close()
        browser.close()
    print(
        "PASS: three PNG formats per weekly post; checksums, provenance, fonts/bounds at 300px, "
        "browser downloads, responsive controls and OG metadata JS on/off. "
        "Real WhatsApp preview still requires deployment."
    )


if __name__ == "__main__":
    main()
