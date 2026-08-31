# Design → EV Bazar: what fits, what conflicts

The design work in this folder was produced without sight of this repo. After
reading `AGENTS.md`, `README.md`, `openapi.json` and `frontend/package.json`,
here is an honest map of what transfers and what does not.

**The short version: the design transfers, the code does not.** Treat
`reference/` as a specification you read, not source you merge.

---

## Conflicts, most serious first

### 1. The result screen shows a point estimate — a hard-constraint violation

`AGENTS.md` constraint 6: *"No point estimates in any user-facing output.
P10/P50/P90 or a labelled scenario band."*

The designed result screen shows `2.1%` effective return, `7.1%` fixed deposit,
`None` payback. The first of those is a point estimate and cannot ship.

**Resolution:** the result screen must show a band. The design already contains
the right pattern — the confidence band in section 08 of the report. Lift it up
into the result screen and drop the bare percentage. The fixed-deposit
comparison survives, because an FD rate genuinely is a point value.

This is not a small edit. It changes the most important screen in the flow, and
it should be settled before anything is built.

### 2. Two frontends versus one SPA

`AGENTS.md`: *"One React SPA... Public site, report and operations console are
all routes in the same app — not two frontends."*

`reference/chargeworthy-site.tar.gz` is a standalone Vite app. It must not be
added to the repo as a second frontend. Port it into `frontend/` as a route
group — `features/public/` alongside the existing `features/console/`.

### 3. Stack mismatch throughout the reference build

| Reference build | This repo |
|---|---|
| JavaScript | TypeScript `strict`, no `any` at the API boundary |
| Inline styles, raw hex | Tailwind + shadcn, tokens in `src/styles/tokens.css`, **no raw hex in a component** |
| Hash routing | `react-router-dom` |
| Mapbox GL JS | Leaflet + react-leaflet |
| `fetch` written by hand | `openapi-fetch` against generated `schema.d.ts` |

Every one of those is settled in `AGENTS.md` as "do not propose alternatives".
The reference build loses on all five. Read it for layout, motion, hierarchy and
copy; write the implementation in this repo's stack.

`design/tokens.css` in this folder is the visual system already expressed the
way this repo wants it — CSS custom properties, ready to wire into the Tailwind
theme.

### 4. Mapbox versus Leaflet

A Mapbox style is published (`mapbox://styles/chargeworthy/cmtcw48t4002401s146owc0tv`)
and the reference build uses Mapbox GL JS. This repo uses Leaflet.

Running both means two mapping bills and roughly 500 KB of duplicated bundle.
**Pick one.** Leaflet is already here and already works; the honest default is
to keep Leaflet and rebuild the dark style as a Leaflet-compatible tile source,
treating the Mapbox style as a colour specification rather than a dependency.
Adopt Mapbox only if vector styling or the geocoder earns its cost — and note
that this repo already has its own geocoding cascade, so it probably does not.

### 5. The public flow has no public endpoints

Every assessment route is under `/api/internal/*`, behind console session auth.
`/api/v1/` currently exposes only `/ping`.

A public assessment flow needs public endpoints with rate limiting and abuse
protection. That is backend work and it is on the critical path — the frontend
cannot be finished without it. `AGENTS.md` is explicit that `v1` is a partner
contract, so a third surface may be the right answer rather than widening either
existing one.

### 6. Product model mismatch: verdict versus tier

`POST /api/internal/assess` returns `{site_id, tier, tier_why, teaser,
waitlisted, waitlist_reason, confidence, boundary_ambiguous}`.

The designed flow ends on a **verdict** — BUILD / DON'T BUILD, with return,
payback and downside. The API returns a **tier and a teaser**, with a waitlist
path. These are different products.

Neither is obviously right, and this is a decision for the business, not for an
implementer:

- If the public flow gives a *teaser* and the full verdict is paid or gated,
  the result screen is wrong and must be redesigned around tier + waitlist.
- If the public flow gives a *verdict*, `AssessOut` needs the ROI outputs added.

**Resolve this before building the result screen.** Everything else in the flow
is unaffected.

### 7. Report: 11 sections here, 7 in the repo

`AGENTS.md`: *"Report components mirror the 7 sections one-to-one, so 'the
ledger is wrong' points at exactly one file."*

`reference/chargeworthy-report.tar.gz` has eleven sections. The extra four are
deliberate — *How this site was judged* (thresholds before data), *What would
change this verdict*, *Provenance*, and *Disclosure and independence* — and each
exists to make the document defensible rather than decorative.

They are a proposal, not a fait accompli. If the seven-section structure is
settled, fold the thresholds into section 1 and the disclosure into the footer,
and argue for the other two separately.

Also: the reference report renders from a JSON island via `build-report.mjs`.
This repo persists the payload as JSONB, serves it verbatim from
`GET /api/internal/reports/{id}`, and archives the PDF as immutable bytes.
**The repo's approach is correct and the reference one is not** — a rebuilt
report is not the report that was sent. Use the reference for layout and print
CSS only.

### 8. Money as strings

`report-data.json` carries `"₹34,00,000"` as a display string. This repo keeps
money in paise as integers and formats only in `lib/money.ts`. The reference
data shape is wrong here; take the layout, not the types.

---

## What transfers cleanly

- **`design/tokens.css`** — the palette and type scale as custom properties.
- **The copy** (`brand/copy-pass.md`) — voice rules, the operator definition, and
  the specific fixes. Copy is stack-independent.
- **Print CSS approach** in the reference report: A4 `@page`, `break-inside:
  avoid` on sections, `thead` repeat, provenance on its own page. This repo
  already treats `print.css` as a first-class deliverable; the reference is a
  working example of the rules.
- **The greyscale rule.** Direction markers are a sign plus a word, never a
  coloured dot, because a bank file gets photocopied. This survives any stack.
- **Layout, hierarchy and motion decisions** — documented in the reference build
  and reproducible in Tailwind.
- **The dark map style** as a colour specification, whatever library renders it.

## What to throw away

- The standalone Vite app as an app
- Hash routing
- Inline styles and every raw hex in a component
- `build-report.mjs` and the JSON-island rendering model
- The report's money-as-string data shape
