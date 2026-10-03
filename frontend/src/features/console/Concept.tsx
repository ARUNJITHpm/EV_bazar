import { Link } from "react-router-dom";

import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/**
 * PART C — the site-assessment concept, recorded where operators look.
 *
 * The product decisions behind /assess and /report/:id were made across
 * BRIEF_FOR_FABLE.md, OVERVIEW.md §8 and a sign-off on 2026-08-19, then
 * amended on 2026-09-03 when the report was rebuilt to the twelve-section
 * paper document in design/brand/report-spec.md. A decision that lives only
 * in a chat log or a doc nobody reopens is a decision that gets
 * re-litigated; this panel is the standing record. Curated by hand, like the
 * prose on Progress — the concept is not derivable from a table.
 *
 * REPORT_SECTIONS below must stay in step with features/report/Report.tsx,
 * which renders them in this order. A console that describes a report the
 * customer is not receiving is worse than no console page at all — that is
 * exactly what this list had become between the rebuild and 2026-09-06. It is
 * exported so ReportBuild.test.tsx can pin it against the rendered document
 * rather than against a promise in this comment.
 *
 * What this list is NOT is the build record. It says what each section IS,
 * for someone deciding whether the product is honest; /console/report says
 * what each one was built from, what it still needs, and what the paper
 * turned out to be like. Keep them apart — the day this list starts carrying
 * page heights is the day nobody reads either.
 */

export const REPORT_SECTIONS: { name: string; what: string }[] = [
  {
    name: "01 · Verdict",
    what: "One word on a full-width dark block — BUILD / CONDITIONAL / DON’T BUILD — with a plain subtitle under it, then one sentence of reason, then a paragraph saying in plain language what the word means for the reader’s money. Then THE MAIN REASON TO KEEP READING, chosen from the payload rather than written per site, and a YOUR NEXT MOVE instruction. Always derived from P10, the cautious end, never P50. All three verdicts sit on the same dark ground: the word decides, colour never does.",
  },
  {
    name: "02 · What this means for your money",
    what: "TWO VOCABULARIES, on purpose (R6). First money: setup budget, cash left each month, time to recover the setup cost — then a four-row table of the same across downside / central / upside, so a landowner can read the whole page without meeting a financial term. Then finance: the effective annual return set directly beside a fixed-deposit rate on the same money, which R5 kept rather than replaced, because the accountant reads the same page. The FD rate stays a PERCENTAGE and is never multiplied into rupees here — that would stamp an invented bank rate into a figure that reads like the engine’s. Closes on a READ THIS BEFORE SIGNING caution naming what the budget leaves out: land, the DISCOM security deposit, GST, financing, contingency, ramp-up working capital.",
  },
  {
    name: "03 · How this site was judged",
    what: "The rules, printed BEFORE any site data. Placement is the argument: a standard shown before the evidence visibly was not fitted to the conclusion. R8 CUT THE TABLE FROM SIX ROWS TO THREE — two thresholds, three verdicts and a horizon row is a glossary, not a rule — so the thresholds moved into the paragraph below and the table is three answers and the rule producing each. THE RULE PRINTED IS OURS, NOT THE SAMPLE’S: the sample measures all three verdicts against its full-cost line, our engine measures them against the running-bill line and reports the other separately, and copying its wording would make this section describe a rule the code does not run. The paragraph says which line the verdict uses and that a site can clear it and still be short over ten years. Then THE CONCEPT PLOT (R8): inline SVG, no key, prints as vector — MAIN ROAD → ACCESS LANE → PLOT, one bay per connector each with its OWN charger, all cabled to ONE grid connection, which is our configuration rather than the sample’s shared charger. It makes 05’s sanctioned-load lever visible two sections before it is quantified. Both Mapbox images stay in 04.",
  },
  {
    name: "04 · The site",
    what: "Two Mapbox Static images (the plot from above, the 3 / 5 / 10 km catchment), then every check NUMBERED and grouped under three questions — Can drivers get in and out? / Customers, and electricity. / A place people will choose. — each group its own table and its own closing footnote. Three columns: the check, what we found (with its source), and WHAT IT MEANS — one plain sentence per check, from SiteFact.means, written once per check rather than once per site. Four states, not three: + favours / = neutral / − against / ? unverified, where unverified REPLACES the direction because a check nobody has confirmed has not argued anything yet. Checks that argue FOR the site are shown as openly as the ones against, and counted at equal weight in the balance line.",
  },
  {
    name: "05 · Financial working",
    what: "THE SECTION SHOWS ITS WORKING (R6), in the order an owner would ask for it: the one-time budget line by line (the subsidy its own row, because a subsidy refused is how a build budget usually moves); the per-unit chain as a sentence — price minus electricity minus every cut equals what is left; the bills that arrive whether or not a unit is sold. Then a steady year across the three cases, then TEN YEARS OF RUNNING TOTAL against the setup cost — the clearest thing in the sample document and we had nothing like it. Then the finance table (NPV, return, payback), the fleet-anchor note, sanctioned-load options and price sensitivity at ±₹2. The three breakdowns are the ENGINE’s and each sums exactly to a headline printed beside it; engine.py enforces that rather than the component trusting it, because a printed sum that does not add up costs more than it explains.",
  },
  {
    name: "06 · Operator comparison",
    what: "The same site under each operating arrangement, ranked by the central-case return — chargeMOD listed ‘our network’ under the same rules as everyone else. TWO TABLES SINCE R9, not one. The money table now carries CASH PER YEAR beside the return, because a return is comparable but abstract and cash is the number the owner feels; the network-and-service table carries district / state reach, the operator’s own stations at 3 km AND 10 km as separate columns, roaming, and — once cpo_terms exists — repair target and tie-in. They are two tables because the halves are never blended into a score: the sample puts them in one grid and then has to write ‘there is no combined score’ underneath to undo the impression the grid just made. Splitting says it structurally, and keeps the section printable, since operators as columns would be cut off on paper the day a fifth one appears. THE RADIUS DECISION IS MADE: 3 km near and 10 km wide, both shown, no 5 km. 3 km is the ring domain/demand/synthetic.py already deducts volume for, so the report never carries two meanings of ‘near’. Prose is counted, not asserted — how many arrangements return the build cost, who leaves the most (or loses the least), and the trade between cash and repair speed, which is named and left to the owner.",
  },
  {
    name: "07 · Competitors",
    what: "Who else is charging nearby, with measured distances. Existence and specs today; measured busyness attaches when the poller has a record.",
  },
  {
    name: "08 · What would change this verdict",
    what: "A LEVER TABLE (R7): a short noun phrase, the sentence carrying the number, and where it stands today — the gap is what a reader scans for. Every figure comes from the payload. THE BUILD-COST LINE IS A LEVER HERE, which it was not before: on the BUILD fixture the downside case clears the bills line and is still ₹1.94 L short over ten years, and that belongs on this page as a condition rather than four pages later as a surprise. A contract row carries the warning the sample gives a lever of its own — volume that is not ADDITIONAL to the forecast buys nothing and feels like it bought everything. Closes on what is still unverified on THIS site, which is what section 01's YOUR NEXT MOVE promises when it sends the reader here.",
  },
  {
    name: "09 · Statistical basis",
    what: "The one chart, for the accountant — the P10–P90 band against TWO rules now (R7). The bills line is solid and heavy because the verdict is measured against it; the build-cost line is dashed and lighter because no verdict is, and drawing them alike would invent a rule the engine does not apply. Neither uses colour — this page gets photocopied into a bank file. Below it BOTH DIVISIONS ARE PRINTED IN FULL, closing on ‘one extra term is the whole difference between the two rules’, which is the reconciliation R5 promised and never printed; engine.py publishes the recovery term so no component has to derive it. NO PRICE-SENSITIVITY STRIP HERE, though the sample has one: R6 already left one at the foot of 05, and printing the same three numbers twice teaches the reader that our sections are not about different things.",
  },
  {
    name: "10 · Assumptions ledger",
    what: "TWO LEDGERS, and R10 is when the second one finally reached a page. The input table comes first — every figure, where it came from, and whether anyone confirmed it, with unverified rows carrying the caution chip; value and basis now share one cell (the sample’s shape), because “₹22.00/kWh” says nothing and “₹22.00/kWh assumed, a decision variable rather than an observation” says everything. Then WHAT THE MODEL ASSUMED: engine.py’s own RoiResult.assumptions, verbatim. Its docstring had claimed since it was written that ‘the report’s assumption ledger consumes it verbatim’ and that was FALSE — the engine’s list went into the database inside the stored result and never onto a page, so only it could go stale unnoticed. ECONOMICS_VERSION is 0.5.0 because of that: the wording is part of the deliverable now. The three inherited jobs closed here — R6’s full-cost line, R7’s recovery figure (now a term in the engine’s own sentence, one number one origin), and R9’s ‘every operator priced at the same volume’.",
  },
  {
    name: "11 · Provenance",
    what: "Which data, which versions (economics, model, renderer, schema), which dates produced this exact payload — so an old report can defend itself. R10 gave it the two things that were missing. A DOCUMENT RECORD: id, date, how many checks the report actually carries, engine version — the document had NO DATE anywhere before that, not on the cover, not in the chrome, which is a strange gap in the one section whose job is self-defence. The date is baked in at assembly, never read at render time, because the payload is served verbatim and a date filled in on the way out is the date of the reading. And WHAT THIS WAS NOT BUILT FROM: no site visit, survey, bill, lease, supply quotation, outage log or signed terms — most of section 04 is measured off a map, and a map cannot see a transformer with no spare capacity or four hours of power cuts a day. The sample lists where evidence WOULD come from; ours says what is missing, because the sources are already in the table above. Starts a new page in print, and shares one closing sheet with section 12 again since R11 stopped holding it whole.",
  },
  {
    name: "12 · Disclosure and independence",
    what: "The commercial conflict, stated: we earn on operator matching, the assessment fee is the same either way, and the share of sites refused is printed. Naming the conflict converts the largest credibility risk into the strongest trust signal. R10 MADE IT AS BLUNT AS THE SAMPLE. Describing a conflict does not resolve it — we are paid more when a site is built and section 06 ranks the operators who would pay us, so fee neutrality is a mitigation and not independence, and no independence claim here has been verified by anyone outside this company. The bracketed rejection counts are now labelled as NOT a track record, with forecast accuracy named as not yet measurable at all; a bracket alone was too easy to miss and the paragraph read as a record. And what must be disclosed before a real client sees this is a LIST — the fee actually charged and by whom, every referral or success fee and who pays it, any relationship with the operators in 06, and who commissioned the report. Prose is where obligations go to be skimmed.",
  },
];

const FIREWALL: { rule: string; why: string }[] = [
  {
    rule: "The judging thresholds are printed before the site data.",
    why: "Section 03 states breakeven, the P10 rule and what each verdict word requires — ahead of section 04's facts. A standard shown before the evidence visibly was not fitted to the conclusion; shown after, it can never prove it was not.",
  },
  {
    rule: "Every factor is shown, including the ones that favour the site.",
    why: "Each site fact carries a direction marker (favours / neutral / against) from fixed thresholds set in assemble.py before any pin was placed. Reporting only the factors that support the verdict is how an advisory becomes a funnel; a reader who can count both sides stops looking for the agenda.",
  },
  {
    rule: "Operator fit sits beside the money, never blended into it.",
    why: "Section 06 runs the engine once per operator AND shows how much of that operator's own network already sits around the site. The two are never combined into one score: trading a better return against better reach is the site owner's weighting, and a single number would quietly make that choice for them.",
  },
  {
    rule: "A nearby station is counted again, once per operator.",
    why: "Section 07 counts neighbouring chargers once, operator-blind — the right count for 'how crowded is this place'. But a rival's charger is competition, while a charger run by the operator you sign with is competition AND a split: their app now has two places to send the same drivers. So the same neighbour means a different thing per operator, and section 06 recounts it. An operator we cannot name reports as unknown, never as zero.",
  },
  {
    rule: "No model outputs a financial number.",
    why: "Models predict only kWh per connector-day; every rupee comes from the pure ROI engine. Nothing can reach in and bend a money figure.",
  },
  {
    rule: "Every prediction is a P10–P90 band; the verdict reads P10.",
    why: "A single number would claim a precision nobody has earned. The cautious end decides, so an optimistic model cannot flip a verdict.",
  },
  {
    rule: "Synthetic values are hatched and tagged, never dressed as measurements.",
    why: "Until the poller's occupancy record exists, demand is a versioned heuristic — shown as such. Solid ink is reserved for facts.",
  },
  {
    rule: "Missing inputs WIDEN the band.",
    why: "Not knowing something makes the answer less certain, never more convenient: an unanswered input widens the report's demand band, and on the /assess teaser it falls to the labelled archetype default — shown as 'not provided' — never a quiet guess that flatters the site.",
  },
  {
    rule: "A tap that moves cost, not the number, says so.",
    why: "The /assess taps feed the ROI engine for real, but only 'how much space' — more plugs spreading the fixed costs over a larger ceiling — moves the breakeven figure. Transformer size and distance move a report's payback; each tap echoes that it did NOT touch this number, instead of borrowing its authority.",
  },
  {
    rule: "The report is stored JSONB, served verbatim.",
    why: "GET /api/internal/reports/{id} re-reads the stored row and never recomputes — the customer sees exactly what was generated, forever.",
  },
  {
    rule: "The rendered PDF is archived as bytes, never re-rendered to answer a dispute.",
    why: "The payload answers “what did you tell me”. It cannot answer “this is not what my report LOOKED like”, because a browser render is not reproducible: R11 measured the same payload printing to 21 pages on one Chromium and 22 on another, and to a different length again depending on whether the fonts had finished loading. So app/pdf/render.py freezes the bytes at generation time into report_pdfs — insert-only by database rule, a demo may be re-rendered and a customer report never — and stamps renderer_version with BOTH the Vite build hash and the Chromium build, because either alone survives the wrong kind of change.",
  },
  {
    rule: "Every prediction is logged append-only with actual_kwh NULL.",
    why: "When reality arrives, the model's error is measurable, not deniable. Demo runs are flagged, never skipped.",
  },
];

const DATA_STRATEGY: { layer: string; source: string; status: string; live: boolean }[] = [
  {
    layer: "Roads · junctions · POI dwell",
    source: "OSM Overpass — free, keyless, throttled",
    status: "live in every report",
    live: true,
  },
  {
    layer: "Competitor inventory",
    source: "Open Charge Map — free key",
    status: "live in every report",
    live: true,
  },
  {
    layer: "EV counts & growth",
    source: "VAHAN — our own scraper, nightly job",
    status: "live in every report",
    live: true,
  },
  {
    layer: "Drive-time catchment",
    source: "OpenRouteService — free tier, keyed",
    status: "later: must be metered first",
    live: false,
  },
  {
    layer: "Congestion / traffic flow",
    source: "TomTom or HERE — free tier, keyed",
    status: "later: same metering rule",
    live: false,
  },
  {
    layer: "Road traffic counts (AADT)",
    source: "No free source exists for India",
    status: "proxied: road class + junctions + dwell",
    live: false,
  },
  {
    layer: "Operator presence",
    source: "Derived from the competitor inventory — no new fetch",
    status: "live: 95% of rows named",
    live: true,
  },
  {
    layer: "Measured occupancy",
    source: "The poller — ours alone",
    status: "the moat; not yet running",
    live: false,
  },
];

export function Concept() {
  return (
    <>
      <PanelHeader
        title="Concept"
        note="The site-assessment product in one page: what the report is, why plain language leads it, the rules that keep it honest, and where every data layer comes from. This is the standing record — signed off 2026-08-19, and amended on 2026-09-03 when the report was rebuilt to twelve sections. Source documents: design/brand/report-spec.md, design/DECISIONS.md, BRIEF_FOR_FABLE.md, OVERVIEW.md §8 and STACK.md §7."
      />
      <Glossary
        terms={["Breakeven utilisation", "Occupancy", "Tier", "Append-only", "CPO", "Paise"]}
      />

      <section className="max-w-3xl">
        <SectionTitle>The product in one sentence</SectionTitle>
        <p className="max-w-prose border-l-2 border-rule-strong bg-ground-sunk px-3 py-2 text-[13px]">
          Drop a pin, get the utilisation this EV charging site must reach to break even, and an
          honest banded estimate of whether it will get there — with every assumption on the table.
          Telling someone their site is bad IS the product: the first demo pin (
          <Link to="/report/KL-TVM-DEMO-001" className="underline underline-offset-2">
            KL-TVM-DEMO-001
          </Link>
          , Kazhakkoottam NH-66) came out <em>don&apos;t build</em> at −3.5 pp because eight real
          competitors sit within 3 km, and that verdict shipped unedited.
        </p>
      </section>

      <section className="mt-8 max-w-3xl">
        <SectionTitle>Plain language decides, statistics verify — amended 2026-09-03</SectionTitle>
        <p className="max-w-prose text-[13px] text-ink-muted">
          <strong className="font-medium">The 2026-08-19 call was number-first</strong>: the
          breakeven chart at the top, the verdict word small underneath as confirmation, on the
          argument that a reader who reaches the conclusion themselves is more persuaded than one
          who is told it. Owner&apos;s call on 2026-09-03 reversed it, and this panel records the
          reversal rather than quietly overwriting it.
        </p>
        <p className="mt-2 max-w-prose text-[13px] text-ink-muted">
          <strong className="font-medium">What ships now</strong>: the verdict word first, then one
          sentence of reason, then what it means for the reader&apos;s money — and the chart falls
          to section 09, for the accountant. The reason is the reader. The document is read by a
          private investor before it is read by their CA: making the investor decode a percentile
          band to learn the answer is a technical audience&apos;s idea of respect. The band still
          decides the verdict (P10 against breakeven, in the engine); it simply no longer has to be
          the thing that communicates it.
        </p>
        <p className="mt-2 max-w-prose text-[13px] text-ink-muted">
          Visual language is unchanged and is now a paper document rather than a screen: hairline
          rules instead of cards, serif prose and monospace figures, print CSS that keeps a table
          head with its rows and gives provenance its own page — and colour ONLY where it carries
          meaning, with direction markers reading sign-plus-word so nothing is meaning-bearing by
          colour alone.
        </p>
      </section>

      <section className="mt-8 max-w-3xl">
        <SectionTitle>The funnel</SectionTitle>
        <ol className="border-t border-rule">
          <FunnelStep
            n="1"
            name="/assess — the free teaser"
            what="Breakeven utilisation from pure arithmetic in 30 seconds, before any model — the certain number, sellable on day one. A pin dropped on the published Chargeworthy map, then the design flow's four taps — how much space, whether a transformer is near and how big, how far it is, and what the site is for — wired into the ROI engine for real: only 'how much space' (2 / 4 / 6 plugs) moves the number, and each tap echoes what it did, or that it moved a report's payback and not this figure. A pin outside Kerala/Tamil Nadu joins the district waitlist — capture, not failure: the queue decides which state's tariffs load next."
          />
          <FunnelStep
            n="2"
            name="/report/:id — the paid assessment"
            what="The full twelve-section document below, generated once, stored as JSONB, served verbatim. The report is the deliverable AND the sales artifact — its honesty is the differentiator against every consultant's optimistic PDF."
          />
          <FunnelStep
            n="3"
            name="CPO handoff — where revenue lives"
            what="The comparison table ranks operating arrangements AT THIS SITE — the same engine per operator, beside how much of each operator's own network already sits within 3 km, because that is what splits the demand they would send. A customer choosing one is a lead, and proving that lead came from us is Part 7's attribution chain (schema decided by the 0.3 conversations). Ladder: audits → institutional subscriptions → commissions. What is built and what is not: /console/operators."
          />
        </ol>
      </section>

      <section className="mt-8 max-w-3xl">
        <SectionTitle>Report anatomy — in reading order</SectionTitle>
        <p className="mb-2 max-w-prose font-data text-[11px] text-ink-faint">
          What each section is. What each one was BUILT from — the parts that rebuilt it, what it
          still needs, and how much of it the stored payload can actually fill — is on{" "}
          <Link to="/console/report" className="underline underline-offset-2">
            Report
          </Link>
          .
        </p>
        <dl className="border-t border-rule">
          {REPORT_SECTIONS.map((s) => (
            <div key={s.name} className="border-b border-rule py-2">
              <dt className="font-ui text-[13px]">{s.name}</dt>
              <dd className="mt-0.5 max-w-prose text-[12px] text-ink-muted">{s.what}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="mt-8 max-w-3xl">
        <SectionTitle>The honesty firewall</SectionTitle>
        <p className="mb-2 max-w-prose font-data text-[11px] text-ink-faint">
          The rules that make the report defensible. Each one is enforced in code or by the
          database, not by good intentions.
        </p>
        <dl className="border-t border-rule">
          {FIREWALL.map((f) => (
            <div key={f.rule} className="border-b border-rule py-2">
              <dt className="max-w-prose font-ui text-[13px]">{f.rule}</dt>
              <dd className="mt-0.5 max-w-prose text-[12px] text-ink-muted">{f.why}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="mt-8 max-w-3xl">
        <SectionTitle>Location data — free first, metered when keyed</SectionTitle>
        <table className="w-full border-t border-rule text-left">
          <thead>
            <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
              <th className="py-1 pr-3 font-medium">Layer</th>
              <th className="py-1 pr-3 font-medium">Source</th>
              <th className="py-1 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {DATA_STRATEGY.map((d) => (
              <tr key={d.layer} className="border-t border-rule align-top">
                <td className="py-1.5 pr-3 text-[13px]">{d.layer}</td>
                <td className="py-1.5 pr-3 font-data text-[12px] text-ink-muted">{d.source}</td>
                <td
                  className={
                    d.live
                      ? "py-1.5 font-data text-[12px]"
                      : "py-1.5 font-data text-[12px] text-ink-faint"
                  }
                >
                  {d.status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
          What v0 deliberately does NOT claim: which side of a divided road the site sits on (needs
          carriageway-pair matching — wrong side loses roughly half the traffic), drive-time
          catchments, and measured competitor busyness. Each shows as &ldquo;not assessed&rdquo; in
          the ledger rather than a guess — the report&apos;s credibility rests on the difference.
        </p>
      </section>

      <section className="mt-8 max-w-3xl">
        <SectionTitle>Reference — the original visual concept</SectionTitle>
        <p className="max-w-prose text-[13px] text-ink-muted">
          The first mockup of the report + funnel (2026-08-19), preserved verbatim:{" "}
          <a
            href="/reference/site-assessment-concept.html"
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-2"
          >
            site-assessment-concept.html →
          </a>
        </p>
        <p className="mt-1 max-w-prose font-data text-[11px] text-ink-faint">
          A single self-contained page, light/dark by system theme, with illustrative Ernakulam
          NH-544 sample data. It predates the sign-off — the shipped report went number-first,
          colder and quieter, on the repo&apos;s own token system — but it documents the visual
          direction the decisions were made against, so keep it as a reference, never as a spec.
        </p>
      </section>
    </>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-2 font-ui text-[10px] font-bold tracking-[0.08em] text-ink-faint uppercase">
      {children}
    </h2>
  );
}

function FunnelStep({ n, name, what }: { n: string; name: string; what: string }) {
  return (
    <li className="flex gap-3 border-b border-rule py-2">
      <span className="font-data text-[11px] text-ink-faint tabular-nums">{n}</span>
      <div>
        <p className="font-ui text-[13px]">{name}</p>
        <p className="mt-0.5 max-w-prose text-[12px] text-ink-muted">{what}</p>
      </div>
    </li>
  );
}
