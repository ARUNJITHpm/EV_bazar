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

Wordmark direction **C — Instrument** (IBM Plex Mono caps) is the one chosen and
the one used throughout. It stays legible as a mark against a grotesque page
instead of dissolving into the nav.

> **2026-08-31:** all four canvas links above return "artifact not found" from
> this account — the images exist nowhere in `design/`. If the canvases are
> still wanted on record, whoever holds the publishing account must export
> them (PNG or HTML) into `design/canvases/`. The social-images canvas is the
> only source of `og-identity.png`, which the reference build's `<head>`
> references but never included.

## Mapbox

A dark style is published at
`mapbox://styles/chargeworthy/cmtcw48t4002401s146owc0tv`.

Whether to use it is an open decision — see INTEGRATION.md §4. If Leaflet wins,
the style is still useful as a colour specification.

> **2026-08-31:** decided, then amended. Leaflet + colour-spec first
> (DECISIONS.md (c)); after the owner supplied the style's public token the
> public surface switched to the real style — credentials and the
> URL-restriction action item are in `MAPBOX.md`.
