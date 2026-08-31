# Chargeworthy — Site Report UI Prompt

For the brand name rationale, colour palette, and typography, see
`claude/chargeworthy-visual-system.md`. This prompt references palette
tokens by name so the same spec works if the palette is retuned.

---

## Site report UI prompt (for a UI-generating AI)

**Version 2** — layered for two readers, and restructured so that the breadth of inputs does the work of proving impartiality.

```
Build a single-page investment assessment report for CHARGEWORTHY, an
independent EV-charging site advisory. The page is one site's verdict on
whether to build a charging station there.

READER
Two people read this document, in this order:
  1. A 35–55 year old private investor deciding whether to commit
     ₹20–40 lakh. Financially literate, not an EV-industry person.
     Benchmarks everything against fixed deposits and rental yield.
  2. Their chartered accountant and their bank's credit officer, who
     will check the working.
Plain language decides. Statistics verify. Order the page accordingly.
They will print this and read it slowly. It is a document, not a
dashboard. No marketing, no persuasion, no urgency.

CREDIBILITY IS THE DESIGN PROBLEM
The report's job is to be visibly unbiased. Achieve this structurally,
not with claims: state the judging thresholds before showing the data,
show every factor assessed including those that favour the site, count
favourable and unfavourable factors openly, mark what was measured
versus estimated, and disclose commercial relationships. A reader who
sees the full working stops looking for the agenda.

VISUAL SYSTEM
Use the Chargeworthy report palette supplied separately, by token name:
`paper` background, `ink` text, `slate` section headers and brand mark,
`rule` hairlines, `muted` secondary text, `band` confidence bar,
`verdict-positive`, `verdict-negative`, `caution` and `caution-tint`.
Colour appears ONLY where it carries meaning.

Typography: serif (Source Serif 4 / Lora) for headings, verdicts and all
prose. Monospace with tabular figures (JetBrains Mono / IBM Plex Mono)
for EVERY number, so digits align in columns. Body minimum 17px at 1.6
line-height. No font weight below 400. Nothing under 13px except
provenance, which may go to 12px.

STRUCTURE — in this exact order

MASTHEAD — "CHARGEWORTHY" small in slate; site identifier
("NH-66, Kasaragod — northbound carriageway") large in serif; heavy 3px
ink rule. Right-aligned: report number, assessment date, assessor name.

1. VERDICT — "DON'T BUILD" large in `verdict-negative` (or "BUILD" in
   `verdict-positive`, or "BUILD — CONDITIONAL" in `caution`) over a
   heavy `ink` rule. Below it,
   ONE serif sentence at ~20px giving the reason in language a
   non-specialist understands on first read.

2. WHAT THIS MEANS FOR YOUR MONEY — the section the reader came for.
   Give it room. Large monospace figures with serif labels:
     · Capital required
     · Payback period in years, or "does not pay back"
     · Effective annual return, set directly beside a current fixed
       deposit rate for comparison — this comparison is the single
       most legible fact on the page
     · Downside case
   Then one plain sentence using natural frequencies, e.g. "Of 100 sites
   with this profile, 4 break even within five years." This number must
   come from the model, never be chosen for effect.

3. HOW THIS SITE WAS JUDGED — the thresholds, stated BEFORE any site
   data appears: breakeven utilisation, minimum acceptable payback
   period, minimum sanctioned load, maximum acceptable competitor
   density. A short line noting these criteria are fixed and applied to
   every site Chargeworthy assesses. This placement matters: it proves
   the standard was not fitted to the conclusion.

4. SITE FACTORS — the evidence, and the longest section on the page.
   Open with a balance line in monospace:
     "34 factors assessed — 13 favourable, 16 unfavourable, 5 neutral"
   Then hairline-ruled rows grouped under serif subheadings. Each row
   carries: factor name (serif), measured value (monospace), source, and
   a direction marker — favourable, unfavourable, or neutral. Favourable
   factors on a rejected site MUST be shown at equal weight; suppressing
   them is the bias the whole section exists to disprove. Mark estimated
   values distinctly from measured ones.

   ACCESS & GEOMETRY — road class; distance from main road; sub-road
   approach and its condition; carriageway direction served; whether a
   median blocks entry from the opposite direction; sight line in metres;
   turning radius at entry and exit; frontage width; AADT traffic count;
   dominant flow direction and peak hours.

   DEMAND — district EV registrations 17,895 (+33.5% YoY); registration
   mix across 2W/3W/4W/commercial; corridor through-traffic versus local;
   fleet and cab operator presence within 10 km; distance to nearest
   city.

   POWER & TARIFF — applicable EV tariff with the order number; demand
   and fixed charges; sanctioned load available against load required;
   distance to nearest transformer and its spare capacity; estimated new
   connection cost; recorded grid outage hours; applicable state subsidy.

   SITE & AMENITIES — plot area; parking bays achievable; canopy
   feasibility; amenities within walking distance (toilet, food, retail)
   with distances, since these govern dwell time; mobile network coverage
   by operator, which determines whether the CMS and payments work at all;
   lighting and night safety; lease or land cost.

   COMPETITION — nearest charger at 246 m with operator and connector
   count; counts within 3 km, 5 km and 10 km; observed utilisation where
   available; announced or under-construction stations.

5. FINANCIALS — dense monospace table of capex, opex and margin in ₹.
   Every figure tabular and right-aligned. Indian numbering (lakh/crore).

6. COMPETITORS — the 8 nearest stations by distance: distance, operator,
   connector count, charger type, observed utilisation if known.

7. WHAT WOULD CHANGE THIS VERDICT — two to four specific, checkable
   conditions that would flip the decision, each with the threshold it
   must cross. e.g. "District EV registrations above 41,000 (currently
   17,895)". This section proves the verdict is conditional on evidence
   rather than on disposition, and it is the reason a reader trusts a no.

8. STATISTICAL BASIS — for the accountant and the credit officer.
   Projected utilisation as a monospace figure, with a horizontal
   confidence band: a `band` bar spanning P10 to P90 and a solid `ink`
   tick at the breakeven threshold, labelled "P10 0.9%", "P90 2.4%",
   "breakeven 4.3%". Beneath it, one muted sentence in plain English —
   "Even in the optimistic case this site runs below the point where it
   covers its costs." Name the model and the number of simulation runs.

9. ASSUMPTIONS LEDGER — every assumption as a row. Verified ones plain;
   unverified ones carry an "UNVERIFIED" chip in `caution-tint` with
   `caution` text. Visible completeness is the point — this section should look
   thorough, not defensive.

10. PROVENANCE — faint monospace list of every source: tariff order
    number, VAHAN snapshot date, OSM extract date, survey date, traffic
    count method and date.

11. DISCLOSURE & INDEPENDENCE — a short plain-language statement:
    Chargeworthy is not a charge point operator, holds no stake in any
    station, and earns a fee when a site proceeds to installation with a
    partner operator. State plainly that assessment fees are not
    contingent on a positive verdict, and give the proportion of assessed
    sites that received a DON'T BUILD verdict. Small type, quiet
    placement, no defensiveness. Disclosing the conflict is what
    neutralises it.

RULES
- The confidence band in section 8 is the ONLY chart on the page. No pie
  charts, gauges, sparklines, icons or illustrations.
- Numbers always monospace and tabular. Prose always serif.
- Generous vertical rhythm; this is read slowly, not scanned.
- Must print to A4 in black and white and remain fully legible, with the
  verdict readable once colour is stripped. Direction markers in the
  factors table must therefore not rely on colour alone.
- Self-contained HTML, all CSS inline, light mode only.
- No animation, hover effects, gradients, shadows, rounded cards, or any
  dashboard styling.
- No calls to action, contact buttons, or partner logos.

The test: it must look like something a bank would accept as evidence,
and something the reader trusts precisely because it is willing to say
no, shows the factors that argued the other way, and admits what it
stands to gain.
```

---

## Design reasoning behind version 2

**The confidence band was demoted, not deleted.** P10/P90 is quant vocabulary; a lay reader skips what they cannot parse, and that band carried the report's most important finding. It now sits in *Statistical Basis* where the CA and credit officer look for it, while the investor gets the same finding in plain language up top.

**The fixed-deposit comparison is the most legible fact on the page.** For a 35–55 year old Indian investor, FD and rental yield are the mental yardsticks for every investment decision. "2.1% versus 7.1%" needs no chart and no explanation.

**Natural frequencies beat percentages.** "4 of 100 sites" is reasoned about far more reliably by non-specialists than "4%" — the same reason clinicians are taught to say "10 in 1,000". The figure must come from the model, never be chosen for effect.

**Breadth of inputs is the anti-bias mechanism.** Thirty-plus disclosed factors, with favourable ones shown at equal weight on a rejected site, removes the suspicion of a predetermined answer far more effectively than any claim of independence.

**Thresholds appear before data.** Stating the judging criteria first proves the standard was not fitted to the conclusion — the design equivalent of pre-registration.

**"What would change this verdict" is why a reader trusts a no.** It demonstrates the verdict is conditional on evidence rather than on disposition.

**Disclosure neutralises the conflict.** Chargeworthy earns on CPO matching; a credit officer will infer this immediately. Stating it first — with the proportion of sites rejected — converts the largest credibility risk into the strongest trust signal.

**Direction markers must not be colour-only.** Printed black and white, which is how a bank file is read, red and green dots become two identical grey dots and the factors table loses its entire function.
