# designv2 — two hero animations

Open `index.html` in a browser. No build step, no server needed. Both loops run
side by side with notes on what each beat is doing.

| File | What it is |
| --- | --- |
| `index.html` | Standalone preview. Tokens are inlined so it opens from disk. |
| `animations.css` | The keyframes, prefixed `cwa-`. Append to `frontend/src/styles/index.css`. |
| `RouteToCharge.tsx` | Animation A as a drop-in component. |
| `ChargerAssessed.tsx` | Animation B as a drop-in component. |

---

## A — Route to charge (landing hero)

11s loop. The corridor draws in → the site settles → a vehicle drives the road
and parks in the bay → the cable reaches out → charge pulses along it and the
unit's LED strip fills 0→100% → the 3/5/10 km catchment rings expand.

The order is the argument. A real location, on a real road, that a real car
reaches — the catchment is the *consequence*, not the opening claim.

**Where it goes:** replaces or sits beside `<HeroMap />` in
`frontend/src/features/public/Landing.tsx`. Unlike `HeroMap` it carries no
Mapbox payload, so it needs no `React.lazy` boundary and costs nothing on first
paint.

## B — The charger, assessed (section hero)

12s loop. The unit draws itself → a survey line sweeps it → the factors resolve
one at a time against real units → the utilisation band fills against the
breakeven line → the verdict lands **last**.

That last beat is not negotiable for visual punch. The *report* leads with the
verdict; this is the *assessment*, and an assessment that announced its answer
first would be describing a different product.

**Where it goes:** the `WhatWeCheck` or `ReportShowcase` section of
`Landing.tsx`.

---

## Wiring in

```
cp designv2/RouteToCharge.tsx    frontend/src/features/public/
cp designv2/ChargerAssessed.tsx  frontend/src/features/public/
cat designv2/animations.css   >> frontend/src/styles/index.css
```

Then in `Landing.tsx`:

```tsx
import { RouteToCharge } from "./RouteToCharge";
// in Hero(), in place of the <Suspense><HeroMap /></Suspense> block:
<div data-reveal="5"><RouteToCharge /></div>
```

The components read `var(--cw-*)` straight from `tokens.css` — there is not one
hex value in either of them, so the tokens stay the single source of truth.

## Constraints these were built to

- **`design/IMPLEMENT.md:65-68`** — cubic-bezier(0.16, 1, 0.3, 1), no animation
  library, `IntersectionObserver` + CSS transitions only. Both are pure CSS and
  SVG; the percentage counter uses `@property`, not JS.
- **`tokens.css`** — copper on ~5% of surface. In A it appears three times (the
  meter strip, the live cable, the catchment rings); in B once in the ledger,
  on the unverified factor, which is the accent's reserved meaning.
- **`reveal.ts`'s contract** — `prefers-reduced-motion` renders the final state
  immediately and nothing loops. Verified: zero running animations under
  `reduced_motion: reduce`.
- **The bracketed-number rule** — the only number that moves is A's charge
  percentage, which is a state of the animation, not a claim about the
  business. The `[340]` / `[38%]` statistics stay still.

## What is *not* here, and why

**The Dribbble charger renders.** Both shots
(`GreenVolt`, `Ecoors`) sit behind Dribbble's bot-verification wall, so the
images could not be read — and they are the original designers' assets, not
licensed for production use. The charger in both animations is drawn from
scratch as SVG, in the same visual spirit.

**The gloss.** The references are gradient-and-glassmorphism marketing pages.
`tokens.css` commits the opposite direction in writing: *"instrument panel, not
dashboard… must not look like it was invented in a design tool."* The one idea
worth borrowing was the second shot's map sequence — a car travelling to a
charger — and that is what A is. If you want the reference look instead, that is
a tokens-level decision, not an animation one, and worth making deliberately.
