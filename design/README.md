# design/

Brand, visual system and UI design for the public-facing side of EV Bazar,
produced under the name **Chargeworthy**.

**Read `INTEGRATION.md` first.** It maps this work onto the repo and names
eight places where it conflicts — one of them a hard-constraint violation in
`AGENTS.md`.

**`reference/` is a specification you read, not source you merge.** It is
JavaScript, inline styles, hash routing and Mapbox. This repo is TypeScript,
Tailwind, react-router and Leaflet.

```
INTEGRATION.md   what transfers, what conflicts, what to throw away
IMPLEMENT.md     the prompt for Claude Code, with three decisions to settle first
tokens.css       the palette as custom properties, ready for tokens.css
brand/           positioning, copy pass, visual system, launch checklist
reference/       standalone builds — read for layout, motion and print CSS
assets/          ambient video (cut — carries a KlingAI watermark)
```

## Design canvases

| | |
|---|---|
| Wordmark, three directions | https://claude.ai/code/artifact/732084bb-f4a6-4797-8130-15cd4b4a5a4f |
| Landing page | https://claude.ai/code/artifact/a15e54b9-d30f-454d-b762-9eefea5283b3 |
| Assessment flow | https://claude.ai/code/artifact/4301ff29-bee6-49ba-8e14-541db28f79e8 |
| Social images | https://claude.ai/code/artifact/ab13f6d8-ed81-4437-8673-76558956a030 |

Wordmark direction **C — Worthy** is the one in use since 2026-10-03, chosen by
the owner from `brand/mark/wordmark-directions.html` (the canvas export, kept
on record; boards A — Ledger and B — Instrument are the alternatives). One
word in Newsreader, Regular "Charge", SemiBold "worthy": the
`Wordmark` component (`frontend/src/features/public/Wordmark.tsx`) on the
header, the report masthead and the sample paper. The `Cw` mark is the
favicon set in `frontend/public/`, built by `brand/mark/build_mark.py` from
the font bytes embedded in that canvas — regenerate it, don't hand-edit it.
It replaced the earlier IBM Plex Mono caps wordmark.

> **2026-08-31:** all four canvas links above return "artifact not found" from
> this account — the images exist nowhere in `design/`. If the canvases are
> still wanted on record, whoever holds the publishing account must export
> them (PNG or HTML) into `design/canvases/`. The social-images canvas is the
> only source of `og-identity.png`, which the reference build's `<head>`
> references but never included.

## Hero animations

Three CSS-only animations argue the product on the public surface. They were
drawn as standalone HTML in `Designv3/` (untracked at the repo root, the same
read-not-merge rule as `reference/`) and ported in 2026-09-05:

| | Where it ships | What it argues |
|---|---|---|
| `route-to-charge.html` | landing hero — `features/animation/RouteToCharge.tsx` | several candidates are compared, one is chosen, and only then does a vehicle reach it |
| `candidate-site-assessment.html` | landing "what a full assessment checks" — `SiteAssessed.tsx` | the 34 factors walked one source at a time, ending on a verdict |
| `sources-to-assessment-report.html` | `/animation` only — `SourcesToReport.tsx` | named sources feed a document; nothing appears that was not fetched |

Rules they are held to:

- **No animation library** (IMPLEMENT.md): keyframes, `offset-path`,
  `stroke-dashoffset`, and `@property` counters. The one JS is an
  `IntersectionObserver` gate so an animation off-screen costs nothing.
- **`prefers-reduced-motion: reduce` shows the final state immediately**, with
  zero running animations — verified, not assumed.
- **Every value is illustrative and bracketed**, from one file
  (`features/animation/data.ts`), which also owns the 34 factor names verbatim
  from the landing page and their grouping BY SOURCE (12/4/8/7/3). The
  landing page, `/animation` and the live assessment screen all read that one
  file, so a visitor cannot meet one taxonomy on the landing page and a
  different one inside their own assessment.
- **No "site fit score."** The report payload has no such field, and marketing
  a headline metric the product does not produce would sell a report that
  cannot be delivered.

`/animation` is an unlinked review surface holding all three side by side.

## Mapbox

A dark style is published at
`mapbox://styles/chargeworthy/cmtcw48t4002401s146owc0tv`.

Whether to use it is an open decision — see INTEGRATION.md §4. If Leaflet wins,
the style is still useful as a colour specification.

> **2026-08-31:** decided, then amended. Leaflet + colour-spec first
> (DECISIONS.md (c)); after the owner supplied the style's public token the
> public surface switched to the real style — credentials and the
> URL-restriction action item are in `MAPBOX.md`.
