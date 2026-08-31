# Prompt for Claude Code

Run `claude` from `D:\EV_Bazar` and paste the block below.

It deliberately does **not** ask for the whole thing at once. The first task is
to resolve three decisions that would otherwise be baked in wrong, and one of
them is a hard-constraint violation in the design as delivered.

---

```
Read AGENTS.md, OVERVIEW.md, STACK.md and FINDINGS.md before doing anything.
Then read design/INTEGRATION.md, which maps a set of brand and UI design work
onto this repo and names where it conflicts.

CONTEXT
design/ contains finished design work for the public-facing side of this
product: brand, visual system, landing page, a seven-step public assessment
flow, and a site assessment report. It was produced without sight of this repo.
design/reference/ holds a standalone build of it.

Treat design/reference/ as a SPECIFICATION YOU READ, NOT SOURCE YOU MERGE.
It is JavaScript, inline styles, hash routing and Mapbox. This repo is
TypeScript, Tailwind + shadcn, react-router and Leaflet, and AGENTS.md settles
every one of those. Port the design; do not import the code.

TASK 1 — resolve three decisions, in writing, before implementing anything

Write design/DECISIONS.md answering these. Argue each from what is in this
repo, not from what the design assumed. Where the answer needs a business call
rather than a technical one, say so plainly and stop rather than guessing.

  (a) POINT ESTIMATE VIOLATION. The designed result screen shows "2.1%
      effective return" — a point estimate, which AGENTS.md constraint 6
      forbids in any user-facing output. Propose the banded replacement.
      The confidence-band pattern already exists in section 08 of the
      reference report; assess whether lifting it into the result screen
      works, and what P10/P50/P90 the roi_engine can actually supply.

  (b) VERDICT VERSUS TIER. POST /api/internal/assess returns tier, tier_why,
      teaser, waitlisted. The designed flow ends on a verdict with return,
      payback and downside. These are different products. Set out what the
      public flow should return, what that requires from AssessOut, and
      whether the full verdict is public, gated or paid. Do not implement the
      result screen until this is answered.

  (c) MAPBOX VERSUS LEAFLET. A Mapbox style is published and the reference
      build uses Mapbox GL JS; this repo uses Leaflet. Running both means two
      bills and a duplicated bundle. Recommend one, with the bundle and cost
      numbers. Note that this repo already has its own geocoding cascade, so
      the Mapbox geocoder may buy nothing.

Stop after Task 1 and show me DECISIONS.md.

TASK 2 — tokens and the public route group

  · Merge design/tokens.css into frontend/src/styles/tokens.css and wire it
    into the Tailwind theme. No raw hex may reach a component.
  · Scaffold features/public/ as a route group in the existing SPA, alongside
    features/console/. Not a second frontend.
  · Build the landing page from the reference: hero, how it works, the 34
    factor chips, the card set, the report showcase, the close. Copy comes
    from design/brand/copy-pass.md, which is already the corrected version —
    use it verbatim, including the definition of "operator" in the hero.
  · Motion: entrances 520ms, state changes 200ms, cubic-bezier(0.16,1,0.3,1),
    rise 20px, 40–60ms stagger, fire once at 20% viewport entry, never replay.
    Full prefers-reduced-motion support. IntersectionObserver plus CSS
    transitions; no animation library.
  · Do not add the ambient background video. It carries a KlingAI watermark
    and was cut.

TASK 3 — the assessment flow

Seven steps: locate · transformer · distance · capacity · land · intent ·
working · result. Reference implementation in design/reference/.

Non-negotiable, because these are the point of the redesign:
  · One question per screen. NO DROPDOWNS anywhere in the flow.
  · Tap targets 56px minimum. The user may be standing at the site on a phone.
  · Every step reversible with a visible back control, and browser back must
    work. State survives a refresh.
  · The map stays continuous behind every step so location context is never
    lost.
  · The working screen shows real progress from real work. If the assessment
    returns in two seconds, show two seconds. A padded progress bar is the one
    element that would undo everything this product argues.

Wire it to the real API. GET /api/internal/lookup/point already returns
district, state, confidence and field-level sources — use it for the
confirmation card instead of a third-party reverse geocode, and check whether
its `layers` can supply road class, which the design currently leaves as "not
yet determined".

Flag as a blocker, do not work around: every assessment route is under
/api/internal and behind console session auth. A public flow needs public
endpoints with rate limiting. Tell me what you need and stop.

TASK 4 — the report

Read design/reference/chargeworthy-report.tar.gz for layout, print CSS and
section structure, then implement it in this repo's architecture — payload
persisted as JSONB, served verbatim from GET /api/internal/reports/{id}, PDF
archived as immutable bytes. Do NOT adopt the reference's build-report.mjs
model; a rebuilt report is not the report that was sent.

The reference has eleven sections against this repo's seven. The four extra —
thresholds stated before the data, what would change the verdict, provenance,
and the independence disclosure — each exist to make the document defensible.
Recommend which to adopt; do not silently drop them.

Two rules that survive any stack:
  · Nothing carries meaning by colour alone. A bank file gets photocopied.
    Direction markers are a sign plus a word: "+ FAVOURS", "− AGAINST".
  · Money stays paise-as-integer end to end. The reference data file uses
    display strings; that shape is wrong here. lib/money.ts formats.

WORKING RULES
  · Small commits, one concern each. Run the existing checks — ruff, mypy,
    eslint, tsc, vitest, import-linter — and do not weaken a contract to make
    something compile.
  · If a design decision conflicts with AGENTS.md, AGENTS.md wins. Tell me
    what you dropped and why.
  · Where the design assumed a number that this repo does not have, leave it
    visibly bracketed rather than inventing one.
```

---

## Still outstanding, and none of it is design work

- **Prediction accuracy** renders as `[XX%]` on the landing page. No figure was
  ever supplied.
- **Partner logos** — GOEC, ChargeMOD, ChargeZone, Lubi, ABB, Quench are set as
  type, not marks. Nothing goes up without written permission from each.
- **One real completed assessment** to populate the report. It is the most
  persuasive artefact the company will own and it cannot be fabricated.
- **The three claims in the report's own defence** — fixed thresholds applied to
  every site, a real rejection rate, fees genuinely not contingent on a positive
  verdict. They are what earn the trust and what would cost you badly if a bank
  checked and found them decorative.
