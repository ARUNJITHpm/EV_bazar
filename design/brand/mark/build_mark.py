"""Build the favicon set from Direction C - Worthy.

    python design/brand/mark/build_mark.py

Source of record is `wordmark-directions.html` beside this file: the design
canvas, exported as a self-unpacking bundle. Board C embeds the exact
Newsreader variable font it was drawn with, so the glyph outlines here are
read from those bytes rather than from whatever Newsreader a machine has
installed. A favicon cannot load a webfont, so every mark is drawn as paths.

Sizes follow board C's "Favicon - actual size" row:
  16 px  "C"  alone, Bold   - "Cw" does not survive sixteen pixels
  32 px  "Cw" Bold
  64 px  "C" SemiBold + "w" Bold
  touch  the 512 monogram: "C" Regular + "w" SemiBold, square, iOS rounds it

Writes SVG only - text, so it is safe in git and in the Hugging Face
mirror, which refuses raw binaries. frontend/brand/mark-*.svg are the
sources; `npm run build` rasterises them into dist/ (favicon.ico and the
touch icons) with scripts/build-favicons.mjs. frontend/public/favicon.svg is
the 32 px mark, served as is. Needs fontTools + brotli.
"""

from __future__ import annotations

import base64
import gzip
import io
import json
import re
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = Path(__file__).resolve().parent
FRONTEND = HERE.parents[2] / "frontend"
SOURCE = HERE / "wordmark-directions.html"

GROUND = "#0D151E"  # --cw-ground
TEXT = "#F4F1EC"  # --cw-text


def _island(html: str, kind: str) -> str:
    m = re.search(rf'<script type="__bundler/{kind}"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise SystemExit(f"no __bundler/{kind} island - has the canvas export format changed?")
    return m.group(1)


def _unpack(entry: dict) -> bytes:
    raw = base64.b64decode(entry["data"])
    return gzip.decompress(raw) if entry.get("compressed") else raw


def newsreader() -> TTFont:
    """The upright Newsreader variable font embedded in board C."""
    root = json.loads(_island(SOURCE.read_text(encoding="utf-8"), "manifest"))
    for page in root.values():
        if page["mime"] != "text/html":
            continue
        board = _unpack(page).decode("utf-8")
        if "Direction C" not in board:
            continue
        for asset in json.loads(_island(board, "manifest")).values():
            if not asset["mime"].startswith("font/"):
                continue
            font = TTFont(io.BytesIO(_unpack(asset)))
            name = font["name"].getDebugName(1) or ""
            axes = {a.axisTag for a in font["fvar"].axes} if "fvar" in font else set()
            if name.startswith("Newsreader") and "wght" in axes:
                return font
    raise SystemExit("board C carries no upright Newsreader variable font")


_cache: dict[tuple[int, int], TTFont] = {}


def instance(wght: int, opsz: int) -> TTFont:
    if (wght, opsz) not in _cache:
        _cache[(wght, opsz)] = instantiateVariableFont(
            newsreader(), {"wght": wght, "opsz": opsz}, inplace=False
        )
    return _cache[(wght, opsz)]


def glyph_run(letters: list[tuple[str, int]], opsz: int, tracking: float) -> tuple[str, tuple]:
    """Path data for the letters set on one baseline, in font units, y down.

    `letters` is (character, weight) pairs - board C splits weight inside the
    mark. Returns the joined path and its ink bounds.
    """
    parts: list[str] = []
    x = 0.0
    bounds = None
    for ch, wght in letters:
        font = instance(wght, opsz)
        upm = font["head"].unitsPerEm
        name = font.getBestCmap()[ord(ch)]
        glyph = font.getGlyphSet()[name]
        svg = SVGPathPen(font.getGlyphSet())
        glyph.draw(TransformPen(svg, (1, 0, 0, -1, x, 0)))
        parts.append(svg.getCommands())
        bp = BoundsPen(font.getGlyphSet())
        glyph.draw(TransformPen(bp, (1, 0, 0, -1, x, 0)))
        if bp.bounds:
            b = bp.bounds
            if bounds is not None:
                b = (min(bounds[0], b[0]), min(bounds[1], b[1]),
                     max(bounds[2], b[2]), max(bounds[3], b[3]))
            bounds = b
        x += glyph.width + tracking * upm
    return " ".join(parts), bounds


def mark_svg(
    letters: list[tuple[str, int]],
    *,
    box: int,
    font_px: float,
    opsz: int,
    radius: float,
    tracking: float = 0.0,
) -> str:
    """One square mark: ground, optional corner radius, glyphs centred on their ink."""
    path, (x0, y0, x1, y1) = glyph_run(letters, opsz, tracking)
    upm = instance(letters[0][1], opsz)["head"].unitsPerEm
    s = font_px / upm
    tx = box / 2 - (x0 + x1) / 2 * s
    ty = box / 2 - (y0 + y1) / 2 * s
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {box} {box}">'
        f'<rect width="{box}" height="{box}" rx="{radius}" fill="{GROUND}"/>'
        f'<path fill="{TEXT}" transform="translate({tx:.3f} {ty:.3f}) scale({s:.6f})" d="{path}"/>'
        "</svg>\n"
    )


MARKS = {
    # name: (letters, design box, font px, opsz, radius, tracking)
    "16": ([("C", 700)], 16, 10, 10, 3, 0.0),
    "32": ([("C", 700), ("w", 700)], 32, 18, 18, 6, 0.0),
    "64": ([("C", 600), ("w", 700)], 64, 34, 34, 10, 0.0),
    "touch": ([("C", 400), ("w", 600)], 200, 104, 72, 0, -0.02),
}


def svg_for(name: str) -> str:
    letters, box, px, opsz, radius, tracking = MARKS[name]
    return mark_svg(letters, box=box, font_px=px, opsz=opsz, radius=radius, tracking=tracking)


def main() -> None:
    brand = FRONTEND / "brand"
    brand.mkdir(exist_ok=True)
    for name in MARKS:
        (brand / f"mark-{name}.svg").write_text(svg_for(name), encoding="utf-8")
    # The tab favicon modern browsers take: board C's 32 px design, the size a
    # tab actually rasterises at on most screens today.
    (FRONTEND / "public" / "favicon.svg").write_text(svg_for("32"), encoding="utf-8")
    for f in sorted(brand.glob("mark-*.svg")):
        print(f.relative_to(FRONTEND), f.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
