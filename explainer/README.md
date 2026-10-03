# Chargeworthy explainer

A4 portrait, 16 pages. What the company does, what it checks, and why the
answer can be believed — written for a site owner, not an engineer. Nothing
in it is backend detail.

| File | What it is |
|---|---|
| `chargeworthy-explainer.pdf` | The document. A4, 210 × 297 mm, print at 100% |
| `source/chargeworthy-explainer.html` | The single self-contained source it is rendered from |

## What is in it

```
cover   Will your land pay for a charger?
01      Who we are, in one paragraph — and who this is for
02      How it works — three steps, and we stop at any of them
03      The one number that decides it — breakeven, in plain words
04      The 34 things we check, and what each one does to the answer
05      Choosing who runs it — and why it changes the money
06      What you actually receive — the twelve-part report
07      Why you can believe the answer — eleven structural rules
08      What we do not claim — our own limits, in our own document
09      The words we use
```

Section 04 is the centre of the document: all 34 factors in their five
groups, each with what it does to the verdict. The factor names and the
grouping are `frontend/src/features/animation/data.ts` verbatim — the same
34 the landing page names and the assessment screen walks. **If a factor is
added or renamed there, this document is stale.**

The thresholds quoted in section 04 (100 m / 300 m from a major road, 10,000
and 3,000 district EV registrations, 500 m and 2 km to the nearest charger,
3-within-3 km and 5-within-5 km) are the real ones, from
`app/domain/report/assemble.py`. The ₹2,000/m cabling and ₹2.0 L transformer
figures are `design/DECISIONS.md`'s. The 6.5% deposit rate is
`FIXED_DEPOSIT_PCT` in `features/report/Money.tsx`, indicative and labelled
as such in both places.

## Section 05 — what of it is now real

Added 2026-09-06. It sets out the operator-selection idea: an operator's own
nearby stations split your demand in a way a rival's do not, so the same
neighbouring charger counts differently depending on who you sign with.

Its caution block — "what is counted today, and what is not" — is the part to
keep honest as the capability lands. As of **2026-09-07** it is accurate:

- **Counted.** Station counts per operator, in your district, your state and
  within 3 and 10 km. `app/domain/cpo/presence.py`, live in report section 06.
- **Not counted.** Measured uptime and station usage. Status scraping is a
  deferred later stage; the only station data is what owners upload.
- **Never invented.** Commercial terms. `cpo_terms` does not exist and report
  section 06 still prints its "terms are placeholders" chip.

So the section no longer overstates the product. If status scraping is switched on, or
`cpo_terms` lands, that block is the first thing that goes stale.

The working record while the remaining parts are open is
`CPO_SELECTION_PLAN.md` at the repo root — a temporary file, to be deleted once
it is folded into `PLAN.md` Part 6.

## No bracketed numbers

Unlike the landing page and the brochure, this document contains **no square
brackets** — the same rule the brochure README states ("nothing bracketed
should reach a printer"), applied by leaving the figures out rather than by
filling them in. Where we would have said "[38%] advised against", it says
that we publish the share and why publishing it matters. The one place
brackets are discussed is section 08, which explains what a bracket means on
our own pages.

Adding real figures later is a human step with evidence: fill them into
section 07 ("We publish how often we say no") and section 08's callout, then
re-export.

## Re-exporting

Edit `source/chargeworthy-explainer.html` and re-render with Playwright's
`page.pdf(format="A4", print_background=True)` — the page's own `@page` rule
carries the 18/16/16 mm margins, so pass zero margins to the call. Webfonts
(Source Serif 4, IBM Plex Mono) are progressive enhancement: full fallback
stacks are in the file, and an offline export still lays out correctly.

Print-safety rules already in the source, worth keeping: table heads repeat
across pages (`display: table-header-group`), no table row splits, headings
never end a page, and the palette is the paper half of
`frontend/src/styles/tokens.css`.
