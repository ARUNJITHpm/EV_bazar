# Chargeworthy brochure

A4 landscape, folded in three. Two faces, printed on one sheet.

| File | What it is |
|---|---|
| `chargeworthy-brochure-outside.png` | Outside face at 288 dpi: inside flap, back cover, front cover |
| `chargeworthy-brochure-inside.png` | Inside face at 288 dpi: the three-panel spread |
| `chargeworthy-brochure.pdf` | Both faces, 297 x 210 mm. Print at 100%, duplex, short-edge flip |
| `chargeworthy-brochure.pptx` | The two faces as A4 landscape slides, with fold notes in the speaker notes |
| `source/` | The design files the exports were rendered from |

## Fold order

Outside face, left to right: inside flap, back cover, front cover. The front cover
is on top when folded; the flap folds in first. The inside face reads left to right
once opened: how it works, what a full assessment checks, the report.

## Before printing

Everything in square brackets is a placeholder, per the same rule the landing page
follows: `[38%]`, `[340]`, `[129]`, `[your web address]`, `[email on your domain]`,
`[WhatsApp Business number]`, `[city, state]`. Fill them from the real ledger, or
cut the line. Nothing bracketed should reach a printer.

Copy is taken from `design/brand/` and the shipped landing page. Partner operators
and charger makers are not named, per `design/DECISIONS.md`.

## Re-exporting

The exports are rendered from `source/` with Playwright and python-pptx. Edit the
`.dc.html` files (or the design canvas, then re-export from there) and re-run the
export; the layout is fixed at 1123 x 794 px per face, which is A4 landscape at
96 px per inch.

## Design canvas

The editable canvas lives at https://claude.ai/code/artifact/24fc1feb-31ab-4556-b0ea-a745bf7b7f32
