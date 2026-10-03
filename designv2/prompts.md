# Animation prompts — for pasting into another AI platform

Each prompt is self-contained: the target tool has no access to this repo, so
the palette, constraints and beat sheet are spelled out in full. Paste one at a
time. They share a house style, so keep the "House rules" block in all three.

---

## House rules (prepend to every prompt)

```
Build this as a single self-contained HTML file: inline CSS and inline SVG only.
No animation library — no GSAP, Framer, Lottie, Rive, anime.js, or three.js.
CSS keyframes and SVG only. No JavaScript except where explicitly allowed.

Palette — use these exact values, and no other colours:
  ground        #0d151e   page background
  surface       #16212c   panels
  surface-2     #1e2c39   raised / nested
  line          #253340   borders, hairlines, inactive strokes
  text          #f4f1ec   warm white, never pure white
  muted         #93a1ad   secondary text and labels
  slate         #4a8fb8   the brand blue — data, roads, structure
  accent        #d98a3d   copper — STRICTLY ~5% of pixels, see below
  positive      #3fa37f   semantic only
  negative      #c4564a   semantic only

Copper (#d98a3d) is rationed. It marks exactly one thing per composition and
nothing else. If more than about 5% of the frame is copper, you have overused it
— reduce until it is a highlight, not a theme.

Type: Archivo or system-ui for prose; IBM Plex Mono for every number, label and
code. All figures tabular-nums. Body text never below 17px.

Motion: cubic-bezier(0.16, 1, 0.3, 1). Entrances ~520ms, state changes ~200ms.
Movement should read as weight settling, not as play or bounce. Nothing pulses
for attention. No glow, no bloom, no lens flare, no particles, no confetti.

Aesthetic: a technical survey instrument, not a marketing landing page.
Hairline rules instead of drop shadows. Flat fills instead of gradients, except
one very subtle vertical gradient permitted on a hardware body. This should look
like a certificate or an engineering plan, NOT like it was made in a design tool.
Deliberately austere. Resist prettiness.

prefers-reduced-motion: reduce MUST render the final state of the sequence
immediately, with zero running animations, and the composition must still read
completely. Test this.
```

---

## Prompt A — Route to charge

Landing hero. Full-bleed panel, roughly 1000×620 viewBox, 16:10.

```
Draw a dark top-down map — a survey plan, not a game map. Faint 1px grid,
a handful of flat building blocks in #16212c. No terrain, no labels, no icons.

One highway corridor curves from the bottom-left corner to a site at the upper
right: a 26px-wide stroke in #1e2c39 with dashed #4a8fb8 lane markings down its
centre at 50% opacity.

At the end of the corridor: a parking bay drawn as a thin outlined rectangle
with three bay dividers, and beside it a DC charging unit drawn in flat SVG —
a low plinth, a tall rounded body ~38×114 with a barely-perceptible vertical
gradient, an inset dark screen showing two short slate data bars, a small
holstered connector with a circular port, and a vertical LED strip on its flank.

An 11-second loop, in this exact order — the order is the argument and must not
be resequenced:

  0.0–1.3s   the corridor draws itself in, stroke-dashoffset, from the
             bottom-left origin toward the site
  0.7–1.8s   the lane markings fade up; the bay and the charging unit settle
             in beneath them
  1.4–5.3s   a small top-down white car drives the corridor using CSS
             offset-path with offset-rotate: auto, following the identical
             path data as the road. It carries two tiny copper tail dots and a
             soft forward light cone that is visible ONLY while moving.
             It decelerates into the bay and stops.
  5.5–6.3s   a cable reaches out from the charging unit to the car —
             stroke-dashoffset drawing a short curve, in #253340
  6.3–9.7s   copper charge pulses travel along that cable, car-ward, on a
             loop of about two passes; simultaneously the unit's LED strip
             fills from the bottom upward, 0 to 100%, in copper
  6.6–10.2s  a readout panel fades in at the TOP-LEFT (the top-right belongs
             to the rings): a hairline-bordered box on a translucent ground,
             reading CHARGING / a percentage counting 0→100 in copper mono at
             30px / a site ID in small mono caps
  6.6–10.2s  three concentric catchment rings expand outward from the charging
             unit — radii roughly 58, 102, 148 — in 1.25px copper, staggered
             about 250ms apart, scaling from 0.72 to 1 and settling at low
             opacity. These are 3 km / 5 km / 10 km catchment.
  10.2–11s   everything fades out and the loop restarts clean

The percentage counter must animate WITHOUT JavaScript. Use a registered custom
property: @property --pct { syntax: "<integer>"; initial-value: 0 } driven by a
keyframe, surfaced with counter-reset and content: counter(pct) "%".

Copper appears three times only and nowhere else: the LED meter strip, the live
cable pulses, and the catchment rings. The car's tail dots are the one small
exception. Everything else is slate, line, muted, or white.

Critical: the catchment rings appear LAST, after the car has arrived and is
charging. They are the consequence of a site a real car can reach — never the
opening claim. Do not move them earlier for visual impact.

Two implementation traps to avoid:
- A CSS stroke-dasharray on the lane-marking path will overwrite its dash
  attribute and render it solid. Give the lane markings their own class that
  animates opacity only, and never stroke-dasharray.
- The car's offset-path must contain the byte-identical path data as the road
  stroke, or the car will drive off the road.
```

---

## Prompt B — The charger, assessed

Section hero. Two columns: SVG hardware left (~380×460), a data ledger right.
Collapses to one column below 640px.

```
LEFT — a DC charging unit, front elevation, flat SVG, drawn to the palette:
a wide floor plinth, a recessed base, a tall rounded body ~156×270 with a very
subtle diagonal gradient, an inset screen reading "60 kW" in mono with
"CCS-2 · DC" beneath it and a small slate progress bar, a vertical copper LED
strip down the centre, and two holstered connectors with circular ports whose
heavy cables curve down and outward to the floor.

RIGHT — an assessment ledger: a small mono eyebrow reading MEASURED, NOT
ASSUMED; a headline "Nothing here is a guess."; then five hairline-ruled rows,
each a factor name on the left and its measured value in mono on the right:

  AADT traffic count           18,400 /day
  Transformer distance         140 m
  Sanctioned load              75 kVA
  Competitor density, 5 km     3 stations
  Grid outage hours            unverified

Below the rows, a horizontal band: a thin track, a slate fill spanning roughly
P10 to P90, and a single hard white vertical line marking BREAKEVEN sitting
INSIDE that span. Legend beneath in mono: P10 / BREAKEVEN / P90.

Below that, above a 2px rule, a verdict: the word BUILD in mono caps at 38px in
#3fa37f, with one line of muted explanation.

A 12-second loop, in this exact order:

  0.0–1.7s   the unit's outline draws itself in slate via stroke-dashoffset
  1.0–2.4s   the body fill, plinth, holsters and cables fade in behind it
  2.2–2.9s   the screen wakes — it fades up already showing its readout
  2.4–7.4s   a copper survey line sweeps slowly from the top of the unit to
             the bottom, clipped to the unit's silhouette so it reads as a scan
             of THIS object. It is a 2.5px hard copper edge with a soft
             copper-to-transparent trailing band about 30px above it. It fades
             out at the bottom and does not return.
  2.2–4.0s   the ledger rows resolve one at a time, 360ms apart, each rising
             6px and fading in
  6.7–8.6s   the utilisation band fills outward from its left edge
  7.2–8.4s   the breakeven line fades in on top of the filled band
  8.9–10.1s  the verdict rises 8px and fades in — LAST

Only ONE value in the entire ledger is copper: "unverified" on the final row.
Every other value is muted grey. That single copper word is the whole point of
the composition — an unresolved assumption is the loudest thing on the page
after the verdict itself. Do not colour any other value.

Critical: the verdict lands last and must never be resequenced earlier. This is
an assessment being performed, not a result being announced. An assessment that
led with its answer would be describing a different product.

The LED strip should breathe subtly — dim, brighten, settle — but never blink or
strobe.
```

---

## Prompt C — Sources in, report out

A third hero, for the "why trust the answer" / "what a full assessment checks"
section. Site factors arrive from named real sources, pass through the network,
and resolve into a report.

The network topology here is decorative marketing imagery — a fixed, arbitrary
graph, not a diagram of the real model, which uses a different approach and
different parameters. Draw it as a static structure that signal passes THROUGH;
do not attempt to depict training, weights, or inference.

```
A three-band composition, roughly 1160×640, dark ground.

LEFT BAND — four labelled source plates, stacked vertically. Each is a hairline
rectangle with a mono label and a smaller mono stamp beneath it:

  VAHAN · Parivahan          registrations
  OpenStreetMap · Overpass   roads and POIs
  State tariff order         effective 2026-04-01
  Competitor census          3 / 5 / 10 km

Each plate has a small output port on its right edge.

MIDDLE BAND — a feed-forward network, drawn as a precision instrument rather
than as an "AI" motif. Four layers, left to right: 4 input nodes (one per
source plate), then 7, then 7, then 5. Fixed arbitrary topology — decide the
edge set once and keep it stable across the loop; it must not appear to
reorganise.

  · Nodes are small HOLLOW circles, r≈5, 1.25px slate stroke, ground-coloured
    fill. Not filled dots, not glowing orbs, not blobs.
  · Layers sit on a strict vertical rhythm — evenly spaced, mathematically
    aligned. This is a lattice, not an organic web.
  · Edges are 1px hairlines in #253340 at about 35% opacity. Dense enough to
    read as a network, dim enough that no single edge shouts.
  · NO glow, NO bloom, NO blur, NO particle trails, NO gradient meshes, NO
    depth-of-field. Flat, hard-edged, precise.

RIGHT BAND — a report sheet on pale paper (#faf8f4) with dark ink, in clear
contrast to the dark instrument surround. Numbered section rules and a few
short mono figures, like a page of a technical report. The last node layer
feeds into its left edge.

A 13-second loop:

  0.0–1.5s   the four source plates fade in, staggered 200ms apart; each
             stamps its sub-label 200ms after its own plate lands
  1.2–2.6s   the network fades up as a whole — nodes first, then edges
             beneath them at low opacity. It arrives already built; do not
             animate it assembling node by node.
  2.4–7.6s   SIGNAL. Short bright dashes travel left to right along the edges,
             layer by layer: inputs → L2 → L3 → L4 → report. Implement exactly
             as the cable pulse in prompt A — a stroke-dasharray dash pattern
             with an animated stroke-dashoffset, in slate at full opacity —
             so the three animations share one visual family. A node brightens
             briefly as signal reaches it, then settles back. Never all at
             once: the wavefront moves through the layers with a clear
             left-to-right lag of about 700ms per layer.
  6.4–9.0s   as the wavefront lands, the report sheet's numbered lines resolve
             one at a time, 300ms apart, each rising 4px and fading in
  9.0–10.4s  ONE report line resolves to the word "unverified" in copper with
             a small copper chip beside it. The single edge chain that fed it
             brightens to copper for a beat, then releases back to slate.
             This is the only copper in the composition.
  10.4–13s   hold on the complete state, then fade out and restart

Copper appears once and only once: the unverified line and the one chain
feeding it. Every node, every edge, every other figure is slate, line, or
muted. If the network as a whole reads copper or amber, it is wrong — the
network is slate infrastructure and copper is the exception it surfaces.

Restraint is the brief. This must look like a signal-flow diagram on an
instrument panel, not like an AI product's hero section. If it starts to look
energetic, exciting, or futuristic, pull it back until it looks like
engineering documentation that happens to move.
```

---

## Notes on using these

**Order matters and models will "improve" it.** Prompt A's catchment rings and
prompt B's verdict must land last. Any general-purpose model will be tempted to
front-load them for impact. If the output resequences them, reject it and repeat
the constraint — it is the single most common failure.

**Copper discipline is the other one.** The palette block states the ~5% ration,
but models treat an accent colour as a theme. Check the output frame by frame; if
copper is doing anything except marking the one reserved thing per composition,
send it back.

**Ask for the reduced-motion pass explicitly if it is missing.** All three
prompts require it, but it is the first thing dropped. Verify by loading the
result with `prefers-reduced-motion: reduce` — there should be zero running
animations and the composition should still read completely.

**Bring the result back here** and it can be converted to a token-driven React
component the way `RouteToCharge.tsx` and `ChargerAssessed.tsx` were: hex values
swapped for `var(--cw-*)`, keyframes moved into `animations.css`, and typechecked
against the app's tsconfig.
