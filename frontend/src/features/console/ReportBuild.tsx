import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import type { components } from "@/api/schema";

import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/**
 * TRACK B · R12 — the report document's own record, and the last part of it.
 *
 * The Concept panel next door says what the report IS: the product argument,
 * the honesty firewall, why plain language leads. This says what it was
 * BUILT from — twelve sections rebuilt over R0–R11, what each one still
 * needs, what measuring the paper turned up, and which decisions are closed
 * so they are not re-litigated.
 *
 * It exists because that record had become a 37 kB string. Every finding in
 * Track B was appended to the `to_close` field of one milestone in
 * `progress.py` — 494 lines of prose in a field whose job is to name the one
 * thing that closes a milestone. It was in the console, technically, and
 * nobody was ever going to read it. Prose that long is where facts go to be
 * safe from being found.
 *
 * The other half is live, and deliberately so. SECTIONS below is hand-kept
 * and can go stale; what CANNOT is `/api/internal/document`, which reports
 * how much of the document the payload actually stored is able to fill. Every
 * field the rebuild added is optional — a payload from an older economics
 * version renders a complete-looking page while quietly showing less. That is
 * the correct behaviour and it is invisible, so it is measured here.
 *
 * SECTIONS is pinned from the report side: ReportBuild.test.tsx renders
 * <Report/> and asserts these ids match its `data-report-section` attributes,
 * in order. A console describing a document the customer is not receiving is
 * worse than no console page — which is exactly what Concept's section list
 * had become once, between the rebuild and 2026-09-06.
 */

type State = "live" | "open" | "blocked";

type SectionRecord = {
  n: string;
  /** The `data-report-section` id. Pinned against <Report/> by the test. */
  id: string;
  title: string;
  component: string;
  /** Which part of Track B rebuilt it. */
  part: string;
  state: State;
  became: string;
  needs: string;
};

export const SECTIONS: SectionRecord[] = [
  {
    n: "01",
    id: "verdict",
    title: "Verdict",
    component: "Verdict.tsx",
    part: "R3",
    state: "live",
    became:
      "A full-width dark block carrying one word, then one sentence of reason, then what the word means for the reader's money — with THE MAIN REASON TO KEEP READING chosen from the payload and a YOUR NEXT MOVE instruction under it. All three verdicts sit on the same dark ground: the word decides, colour never does. Read from P10, never P50.",
    needs: "Nothing. It closes page 1 on its own sheet at all three verdicts.",
  },
  {
    n: "02",
    id: "money",
    title: "What this means for your money",
    component: "Money.tsx",
    part: "R6",
    state: "live",
    became:
      "Two vocabularies on purpose. Money first — setup budget, cash left each month, time to recover — then the same three cases as a table a landowner can read without meeting a financial term. Then finance: the effective return set directly beside a fixed-deposit rate on the same money, which R5 kept rather than replaced. Closes on READ THIS BEFORE SIGNING, naming what the budget leaves out.",
    needs:
      "Nothing in the section. The FD rate stays a percentage and is never multiplied into rupees here — that would stamp an invented bank rate into a figure that reads like the engine's.",
  },
  {
    n: "03",
    id: "judged",
    title: "How this site was judged",
    component: "Judged.tsx",
    part: "R8",
    state: "open",
    became:
      "The rules, printed before any site data — placement is the argument. R8 cut the table from six rows to three (two thresholds and three verdicts is a glossary, not a rule) and moved the thresholds into the paragraph. The rule printed is OURS, not the sample's: our verdict is measured against the running-bill line, and the full-cost line is reported separately. Then the concept plot — inline SVG, no key, prints as vector.",
    needs:
      "PLAN 2.5: favours / neutral / against thresholds for the OPERATOR factors, which belong on this page ahead of section 06. They need numbers signed off by a human and were deliberately not invented.",
  },
  {
    n: "04",
    id: "site",
    title: "The site",
    component: "Site.tsx",
    part: "R4",
    state: "open",
    became:
      "Two Mapbox Static images, then every check numbered and grouped under three plain questions, each group its own table and its own closing footnote. Three columns, the third being WHAT IT MEANS — one sentence per check, a property of the factor rather than of this site. Four states, not three: unverified REPLACES the direction, because a check nobody has confirmed has not argued anything yet. FILLED OUT TO 39 CHECKS on 2026-09-09, owner's call — including the fifth group, 'Site and amenities', which the chapter map had always expected and the assembler had never put a single row into.",
    needs:
      "A SOURCE FOR 25 OF THE 39. They are named, grouped and on the page, and every one of them prints UNVERIFIED rather than a direction — so the section is full-length without a single guess dressed as a measurement. The list of what would close each is below. This is still the largest piece of backend work left.",
  },
  {
    n: "05",
    id: "financials",
    title: "Financial working",
    component: "Financials.tsx",
    part: "R6",
    state: "live",
    became:
      "The section shows its working, in the order an owner would ask for it: the one-time budget line by line (the subsidy its own row), the per-unit chain as a sentence, the bills that arrive whether or not a unit is sold. Then a steady year across three cases, then ten years of running total against the setup cost. The finance table moved BELOW that, so the plain-money build-up runs uninterrupted.",
    needs:
      "Nothing. Each of the three breakdowns sums exactly to a headline printed beside it, and engine.py enforces that rather than the component trusting it.",
  },
  {
    n: "06",
    id: "operators",
    title: "Operator comparison",
    component: "Operators.tsx",
    part: "R9",
    state: "blocked",
    became:
      "Two tables since R9, not one. Money — the return AND cash per year, because a return is comparable but abstract and cash is the number the owner feels. Then network and service — district and state reach, the operator's own stations at 3 km and at 10 km as separate columns, roaming. They are two tables because the halves are never blended into a score: the sample puts them in one grid and then has to write 'there is no combined score' underneath to undo the impression the grid just made.",
    needs:
      "PLAN 2.3 `cpo_terms` for the repair-target and tie-in columns, and the poller for measured uptime. Both columns are DROPPED rather than filled with dashes — a column of repeated placeholder is furniture.",
  },
  {
    n: "07",
    id: "competitors",
    title: "Competitors",
    component: "Competitors.tsx",
    part: "R2",
    state: "blocked",
    became:
      "The least-changed section in the document: it took R2's section head and shared parts and needed nothing else. Who else is charging nearby, with measured distances, plus the wider rings and the DC-fast count. Counted operator-blind here — section 06 recounts the same neighbours once per operator, because a rival's charger is competition while your own operator's is competition AND a split.",
    needs:
      "The poller (PLAN 0.1) for measured busyness. Existence and specs are all this section can honestly claim today, and it says so.",
  },
  {
    n: "08",
    id: "change",
    title: "What would change this verdict",
    component: "ChangeVerdict.tsx",
    part: "R7",
    state: "live",
    became:
      "A lever table: a short noun phrase, the sentence carrying the number, and where it stands today — the gap is what a reader scans for. The build-cost line is a lever here, which it was not before: the BUILD fixture clears the bills line and is still ₹1.94 L short over ten years, and that belongs on this page as a condition rather than four pages later as a surprise. Closes on what is still unverified on THIS site.",
    needs:
      "Nothing. It is what makes a reader trust a no: every lever is checkable and every figure comes from the payload.",
  },
  {
    n: "09",
    id: "statistical",
    title: "Statistical basis",
    component: "Statistical.tsx",
    part: "R7",
    state: "live",
    became:
      "The one chart, for the accountant — the P10–P90 band against two rules. The bills line is solid and heavy because the verdict is measured against it; the build-cost line is dashed and lighter because no verdict is, and drawing them alike would invent a rule the engine does not apply. Neither uses colour: this page gets photocopied into a bank file. Both divisions are printed in full below it.",
    needs:
      "Nothing. No price-sensitivity strip here, though the sample has one — R6 already left one at the foot of 05, and printing the same three numbers twice teaches the reader that our sections are not about different things.",
  },
  {
    n: "10",
    id: "ledger",
    title: "Assumptions ledger",
    component: "Ledger.tsx",
    part: "R10",
    state: "live",
    became:
      "Two ledgers, and R10 is when the second one finally reached a page. Value and basis share one cell (the sample's shape): '₹22.00/kWh' says nothing, '₹22.00/kWh assumed, a decision variable rather than an observation' says everything. Then WHAT THE MODEL ASSUMED — engine.py's own RoiResult.assumptions, verbatim. Its docstring had claimed since it was written that the report consumed them verbatim, and that was false.",
    needs:
      "Nothing. ECONOMICS_VERSION went to 0.5.0 for it, because the wording is part of the deliverable now rather than a comment in the engine.",
  },
  {
    n: "11",
    id: "provenance",
    title: "Provenance",
    component: "Provenance.tsx",
    part: "R10",
    state: "live",
    became:
      "Which data, which versions, which dates produced this exact payload — so an old report can defend itself. R10 added a DOCUMENT RECORD (the document had no date anywhere before that, not on the cover, not in the chrome) and WHAT THIS WAS NOT BUILT FROM: no site visit, survey, bill, lease, supply quotation, outage log or signed terms. The date is baked in at assembly, never read at render time.",
    needs:
      "Nothing. The demo's render is archived and renderer_version carries the real stamp — a Vite build hash and a Chromium build — read off the page that was actually printed.",
  },
  {
    n: "12",
    id: "disclosure",
    title: "Disclosure and independence",
    component: "Disclosure.tsx",
    part: "R10",
    state: "open",
    became:
      "The commercial conflict, stated as bluntly as the sample states it. Describing a conflict does not resolve it — we are paid more when a site is built, and section 06 ranks the operators who would pay us — so fee neutrality is a mitigation and not independence, and no independence claim here has been verified by anyone outside this company. What must be disclosed before a real client sees it is a LIST, not prose: prose is where obligations go to be skimmed.",
    needs:
      "Real volume. The refusal share is a bracketed count labelled as NOT a track record, and forecast accuracy is named as not yet measurable at all — both stay that way until reports and predictions have arrived and been scored.",
  },
];

/**
 * What has no source behind it yet — owner's call on 2026-09-09: fill the
 * report out now, default what has no feed, and record it here.
 *
 * Every one of these is on the page as a named check that says UNVERIFIED
 * in place of a direction, which is the fourth state section 04 has had
 * since R4. So the page is honest and full at the same time. What it is NOT
 * is finished, and this table is the difference — a placeholder nobody is
 * counting is a placeholder that ships for ever. `/api/internal/document`
 * counts them live, so the number below cannot quietly go stale.
 */
const DEFAULTED: { group: string; checks: string; closes: string }[] = [
  {
    group: "Access and geometry",
    checks:
      "Median access · Sub-road access · Sight line · Turning radius · Entry and exit width · Frontage width",
    closes:
      "Measured from imagery, or a survey for the two that decide whether a car can physically make the turn. Nothing in the repo fetches any of them today.",
  },
  {
    group: "Access and geometry",
    checks: "AADT traffic count · Dominant flow direction · Peak hour timing",
    closes:
      "No free AADT source exists for India — the report proxies traffic from road class, junctions and dwell instead, and says so. A paid feed (TomTom, HERE) would close all three at once, and must be metered first (rule 10).",
  },
  {
    group: "Demand",
    checks: "Fleet operators within 10 km · Distance to nearest city",
    closes:
      "A fleet registry we do not hold, and a settlement layer. Both are single fetches once a source is chosen.",
  },
  {
    group: "Power and tariff",
    checks: "Transformer distance · Transformer spare capacity · Grid outage hours",
    closes:
      "The discom, and only the discom. Spare capacity is the one that can move the budget by lakhs — a transformer with none means a new one. Outage hours are invisible to every map and to the poller.",
  },
  {
    group: "Power and tariff",
    checks: "Sanctioned load · New connection cost · State subsidy applicability",
    closes:
      "These carry a real figure from the archetype rather than 'not assessed' — the engine already prices them — but nobody has confirmed them FOR THIS SITE, so they stay unverified. The subsidy is the one that moves a build budget most often, because it is applied for and refused.",
  },
  {
    group: "Site and amenities",
    checks:
      "Plot area · Parking bays · Canopy feasibility · Mobile network coverage · Night lighting",
    closes:
      "The customer, for the first three — they are facts about land nobody has walked. Coverage needs a drive test; lighting needs an evening visit. 'Amenities within walking distance' in this group is REAL: the POI fetch already counted it and was never printing it.",
  },
  {
    group: "Site and amenities",
    checks: "Land or lease cost",
    closes:
      "The archetype's rent assumption, shown as a monthly figure. Real for the model, unconfirmed for the site — and rent arrives whether or not a unit is sold.",
  },
  {
    group: "Competition",
    checks: "Announced stations",
    closes:
      "No announcement feed exists anywhere. A station announced but not built is an intention, and it changes the answer the day it opens.",
  },
  {
    group: "Operator comparison (06)",
    checks: "Repair target · Tie-in years · Measured uptime",
    closes:
      "`cpo_terms` (PLAN 2.3) and the poller. NOT defaulted, deliberately, and this is the one exception to the call above: CpoRow has no per-cell unverified flag, so an invented repair target would print beside a real company name with nothing marking it — and section 06 RANKS operators, so it would change what the report recommends rather than only what it shows. The columns stay dropped until the table exists.",
  },
  {
    group: "Competitors (07)",
    checks: "Measured busyness at every neighbour",
    closes:
      "The poller (PLAN 0.1). Existence and specs are all this section can honestly claim today.",
  },
];

/** R0 → R12, one line each. The full argument for every one of them is in
 *  CPO_SELECTION_PLAN.md Track B; this is the index to it. */
const PARTS: { part: string; what: string; when: string }[] = [
  {
    part: "R0",
    what: "Three fixture payloads at /report/sample/{build,moderate,dont} — unlinked, no database, so the document can be judged on a NO as well as a yes.",
    when: "07 Sep",
  },
  {
    part: "R1",
    what: "Page chrome: a running head and foot on every printed page, from a real <thead> and <tfoot>.",
    when: "07 Sep",
  },
  {
    part: "R2",
    what: "The section head — a mono eyebrow over a large serif sentence — plus dark table heads, zebra rows, and StatCard / Callout / Footnote in parts.tsx.",
    when: "07 Sep",
  },
  { part: "R3", what: "Section 01, around a full-width dark verdict block.", when: "07 Sep" },
  {
    part: "R4",
    what: "Section 04, around the WHAT IT MEANS column and the fourth state.",
    when: "07 Sep",
  },
  {
    part: "R5",
    what: "The money vocabulary — three decisions taken, and the one that was also code shipped with it.",
    when: "07 Sep",
  },
  {
    part: "R6",
    what: "Sections 02 and 05, the largest single piece of work in the track. Economics 0.2.0 → 0.3.0.",
    when: "07 Sep",
  },
  {
    part: "R7",
    what: "Sections 08 and 09, and the threshold chart. Economics → 0.4.0.",
    when: "07 Sep",
  },
  { part: "R8", what: "Section 03, cut to three rules, and the concept plot.", when: "07 Sep" },
  {
    part: "R9",
    what: "Section 06, split into two tables and given a cash column.",
    when: "08 Sep",
  },
  { part: "R10", what: "Sections 10, 11 and 12 — the tail. Economics → 0.5.0.", when: "08 Sep" },
  {
    part: "R11",
    what: "The print pass, and app/pdf/render.py — the renderer behind rule 9, which did not exist.",
    when: "09 Sep",
  },
  { part: "R12", what: "This panel, and the milestone beside it on Progress.", when: "09 Sep" },
];

/** What measuring turned up that reading could not. Each of these cost a
 *  measurement to learn and would cost the same one again. */
const FINDINGS: { finding: string; detail: string; part: string }[] = [
  {
    part: "R1",
    finding: "print.css had never reached a page.",
    detail:
      "It was not imported by index.css. Not the A4 setup, not the section breaks, not the repeating table head — none of it had ever applied, and the document had been printing without any of the rules written for it.",
  },
  {
    part: "R1",
    finding: "Chromium repeats a running head only from a real <thead>.",
    detail:
      "Measured in this order: @page margin boxes are not implemented at all; position:fixed put the head on 0 pages of 12 and the foot on 1; display:table-header-group on a plain div put it on page 1 alone. So the document is wrapped in a presentation table. Do not tidy it back into divs without re-running that measurement.",
  },
  {
    part: "R2",
    finding: "A4 less 14 mm of margin leaves 688px, and about 1017px of height per page.",
    detail:
      "A table wider than 688px is CUT OFF on paper, not scrolled — which is why section 06 is two stacked tables rather than operators as columns, and why every table carries a minWidth under 42rem.",
  },
  {
    part: "R8",
    finding: "break-inside: avoid is INERT on a block taller than a page.",
    detail:
      "It does not error and it does not warn — it silently does nothing. A section that outgrows a page loses its protection on the edit that made it longer, and the page break it then produces looks like any other.",
  },
  {
    part: "R11",
    finding: "The threshold for holding a section whole is a third of a page, not a page.",
    detail:
      "Holding a section costs, on average, half its own height in blank paper every time it does not happen to fit. change 769px, disclosure 647px and provenance 568px were each buying a whole-section guarantee at the cost of most of a sheet. All three break freely now, which put sections 11 and 12 back on one closing sheet.",
  },
  {
    part: "R11",
    finding: "networkidle plus [data-report-ready] does not mean the fonts are loaded.",
    detail:
      "document.fonts.status was still 'loading' at that point, and Chromium prints whatever it has — so every print measurement from R6 to R10 was laid out in fallback metrics and came out ONE PAGE OPTIMISTIC. Awaiting document.fonts.ready fixes it. The three fixtures print 22 / 23 / 23; the stored demo went from 17 to 26 when it was regenerated on 9 September, because section 04 grew from 16 checks to 39.",
  },
  {
    part: "R11",
    finding: "The page number needs Playwright's footer_template, and costs nothing.",
    detail:
      "counter(page) resolves only inside an @page margin box. Turning display_header_footer on leaves the content box at 1017px and the page count identical, because the templates draw in a page-anchored box rather than out of the flow; 14 mm through 18 mm give identical pagination.",
  },
  {
    part: "R5",
    finding: "The plan's own full-cost formula contradicted the NPV four pages away.",
    detail:
      "'Annual bills + setup / 10 years' was built, then measured against the three sample payloads, and disagreed on two cases out of nine — including the one that prompted the question. What shipped is the steady-state volume at which NPV is exactly zero, at the document's own discount rate. The cost is that it can no longer be checked on the back of an envelope.",
  },
  {
    part: "R9",
    finding: "The fixtures were ranking a 13.6% deal above a free one.",
    detail:
      "Adding the cash column exposed it. The fix was not to retune the numbers: the whole money block is derived from the engine now, and a test pins the zero-terms row to the P50 scenario's own IRR on all three sites. A fixture that contradicts itself teaches the reader to distrust the table, not the fixture.",
  },
];

/** The decisions Track B reserved for a human. All five are answered; they
 *  are kept here so they are not asked again. */
const DECISIONS: { question: string; answer: string; when: string }[] = [
  {
    question: "R5 · Does IRR survive the plain-money rewrite?",
    answer:
      "Kept everywhere, as before — so R6 was ADDITIVE. Section 02 keeps the return-vs-fixed-deposit comparison and gains cash and recovery time; section 05 keeps NPV and gains the ten-year table. Both sections got longer.",
    when: "07 Sep",
  },
  {
    question: "R5 · Is full-cost breakeven a second number or a relabelling?",
    answer:
      "A second number in the engine. A site can clear the running-bill line, print BUILD, and still be short over ten years — the build fixture does exactly that.",
    when: "07 Sep",
  },
  {
    question: "R5 · Is the middle verdict still called 'conditional'?",
    answer:
      "Yes. R3 had already removed the misleading 'BUILD —' prefix, which was the real problem; 'moderate' would have been a third vocabulary for the same three numbers.",
    when: "07 Sep",
  },
  {
    question: "R8 · The drawn schematic, or the maps?",
    answer:
      "Keep both. The plot goes into section 03 and makes 05's sanctioned-load lever visible two sections before it is quantified; both Mapbox images stay in 04.",
    when: "07 Sep",
  },
  {
    question: "R9 · Which radius does section 06 count an operator's own stations at?",
    answer:
      "3 km and 10 km, both, as two columns — no 5 km. 3 km is the ring the demand model already deducts volume for, so the report never carries two meanings of 'near'.",
    when: "08 Sep",
  },
];

const BADGE: Record<State, string> = {
  live: "bg-ok-ground text-ok",
  open: "bg-info-ground text-info",
  blocked: "bg-warn-ground text-warn",
};

/**
 * Taken from the generated OpenAPI types rather than hand-written like the
 * rest of the console's response shapes. This panel exists because records
 * drift, so it does not get to rely on nobody renaming a field: a backend
 * rename becomes a compile error here instead of an `undefined` where a page
 * count should be. `npm run api:generate` regenerates it and CI fails if the
 * committed copy is stale.
 */
type DocumentOut = components["schemas"]["DocumentOut"];

export function ReportBuild() {
  const q = useQuery({
    queryKey: ["document"],
    queryFn: async () => {
      const res = await fetch("/api/internal/document", { credentials: "include" });
      if (!res.ok) throw new Error(`document returned ${res.status}`);
      return (await res.json()) as DocumentOut;
    },
  });

  const dropped = new Map((q.data?.sections ?? []).map((s) => [s.id, s.dropped]));
  // A stored payload behind the engine explains most of the gaps below on its
  // own, and saying so is the difference between "this is old" and "this was
  // never built" — which are not the same problem and do not have the same fix.
  const behind =
    q.data != null &&
    q.data.economics_version != null &&
    q.data.economics_version !== q.data.engine_economics_version;

  return (
    <>
      <PanelHeader
        title="Report"
        note="The twelve-section document at /report/:id — what each section became over R0–R11, what each one still needs, and what the paper turned out to be like once it was measured. The prose here is hand-kept; the coverage readout is not, because a payload stored by an older economics version renders a complete-looking page while quietly showing less."
      />
      <Glossary terms={["Breakeven utilisation", "Confidence", "Paise", "Append-only"]} />

      <section className="mb-8 max-w-3xl border border-rule bg-ground-sunk px-3 py-2">
        <SectionTitle>Where the document stands</SectionTitle>
        <p className="max-w-prose text-[12px] text-ink-muted">
          All twelve sections are rebuilt and the renderer exists — R0–R11, 7 to 9 September 2026.
          No decision is left open. What remains is backend data the sections are already shaped to
          receive, and two writes to the live database that are not the code&apos;s to take. The
          ordered record is <code className="font-data">CPO_SELECTION_PLAN.md</code> at the repo
          root — a temporary file, to be folded into <code className="font-data">PLAN.md</code> Part
          6 and deleted. This panel is what survives it.
        </p>
        <p className="mt-2 max-w-prose text-[12px] text-ink-muted">
          Look at the document itself:{" "}
          <Link to="/report/KL-TVM-DEMO-001" className="underline underline-offset-2">
            the stored demo
          </Link>
          , or the three fixtures at{" "}
          <Link to="/report/sample/build" className="underline underline-offset-2">
            build
          </Link>{" "}
          /{" "}
          <Link to="/report/sample/moderate" className="underline underline-offset-2">
            moderate
          </Link>{" "}
          /{" "}
          <Link to="/report/sample/dont" className="underline underline-offset-2">
            don&apos;t build
          </Link>
          . The product argument behind it is on{" "}
          <Link to="/console/concept" className="underline underline-offset-2">
            Concept
          </Link>
          .
        </p>
      </section>

      <section className="mb-8 max-w-3xl border border-rule px-3 py-2">
        <SectionTitle>Rule 9 is closed — 9 September 2026</SectionTitle>
        <p className="max-w-prose text-[12px] text-ink-muted">
          Migration 0013 is applied, the demo is regenerated against economics 0.5.0, and its render
          is archived as bytes. The archive block below reads the row, so it says what is actually
          there rather than what was intended.
        </p>
        <p className="mt-2 max-w-prose text-[12px] text-ink-muted">
          <b>Archive from a BUILT frontend, never the dev server.</b>{" "}
          <code className="font-data">npm run build</code> then{" "}
          <code className="font-data">npm run preview</code> (port 4173, which proxies the API), and
          point <code className="font-data">--base</code> at that. The renderer reads the Vite hash
          off the page it loaded rather than off the disk, so a dev render stamps{" "}
          <code className="font-data">unbuilt</code> and the script refuses to archive it. The two
          renders look identical and are 141 bytes apart — an archive that answers &ldquo;this is
          not what I received&rdquo; may not be one build out.
        </p>
      </section>

      {q.isPending && <p className="font-data text-[13px] text-ink-faint">…</p>}
      {q.isError && (
        <p className="mb-8 max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          Could not read the document record.
        </p>
      )}

      {q.data && (
        <>
          <section className="mb-8 max-w-3xl">
            <SectionTitle>The newest stored payload</SectionTitle>
            {q.data.report_id == null ? (
              <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
                No report has been generated yet —{" "}
                <code>python -m scripts.generate_demo_report --write</code> creates the first. Until
                then the coverage lines below have nothing to measure against.
              </p>
            ) : (
              <>
                <div className="flex flex-wrap gap-x-8 gap-y-2 border-t border-rule pt-2">
                  <Figure label="Report" value={q.data.report_id} />
                  <Figure label="Generated" value={q.data.generated_at ?? "no date in payload"} />
                  <Figure label="Economics" value={q.data.economics_version ?? "—"} warn={behind} />
                  <Figure label="Engine today" value={q.data.engine_economics_version} />
                  <Figure label="Model" value={q.data.model_version ?? "—"} />
                  <Figure
                    label="Renderer"
                    value={q.data.renderer_version ?? "never rendered"}
                    warn={q.data.renderer_version == null}
                  />
                  <Figure
                    label="Site checks"
                    value={`${q.data.site_facts} · ${q.data.site_facts_unverified} unverified`}
                    warn={q.data.site_facts_unverified > 0}
                  />
                  <Figure label="Operator rows" value={String(q.data.cpo_rows)} />
                </div>
                {behind && (
                  <p className="mt-2 max-w-prose bg-warn-ground px-2 py-1 text-[12px] text-warn">
                    This payload was stored by economics {q.data.economics_version} and the engine
                    is at {q.data.engine_economics_version}. Most of what the sections report as
                    missing below is therefore explained by the report being OLD, not by anything
                    being unbuilt — and the two are completely different pieces of news.{" "}
                    {q.data.demo
                      ? "It is a demo, so it may be regenerated in place: `python -m scripts.generate_demo_report --write`."
                      : "It is a customer report, so it is never regenerated — a correction is a new report id, and the old one stays retrievable."}
                  </p>
                )}
                <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
                  Read from the newest <code>reports</code> row, which is the demo until a customer
                  report exists. The versions are columns rather than a JSON scan, but the payload
                  remains the authority — it is served verbatim and never recomputed.
                </p>
              </>
            )}
          </section>

          <section className="mb-8 max-w-3xl">
            <SectionTitle>The archived render — rule 9&apos;s other half</SectionTitle>
            <p className="max-w-prose text-[12px] text-ink-muted">
              The payload answers <em>what did you tell me</em>. It cannot answer{" "}
              <em>this is not what my report looked like</em>, because a browser render is not
              reproducible — the same payload prints to a different length on a different Chromium,
              and to a different length again depending on whether the fonts had finished loading.
              So the bytes are frozen at generation time.
            </p>
            <dl className="mt-2 border-t border-rule">
              <Row
                label="report_pdfs exists"
                value={q.data.archive.table_exists ? "yes" : "no — migration 0013 not applied"}
                warn={!q.data.archive.table_exists}
              />
              <Row
                label="Archived"
                value={
                  q.data.archive.archived
                    ? `${q.data.archive.pages} pages · ${Math.round(
                        (q.data.archive.byte_size ?? 0) / 1024,
                      )} KB`
                    : "nothing archived yet"
                }
                warn={!q.data.archive.archived}
              />
              {q.data.archive.renderer_version != null && (
                <Row label="Rendered by" value={q.data.archive.renderer_version} />
              )}
              {q.data.archive.rendered_at != null && (
                <Row label="Rendered at" value={q.data.archive.rendered_at} />
              )}
            </dl>
          </section>
        </>
      )}

      <section className="mb-8 max-w-3xl">
        <SectionTitle>The twelve sections</SectionTitle>
        <p className="mb-2 max-w-prose font-data text-[11px] text-ink-faint">
          In reading order, pinned against <code>features/report/Report.tsx</code> by a test.{" "}
          <span className="text-ink-muted">Not printing</span> is measured against the payload
          above, never asserted: every field the rebuild added is optional, so a section drops the
          block rather than inventing one — correct behaviour, and invisible from the page.
        </p>
        <dl className="border-t border-rule">
          {SECTIONS.map((s) => {
            const missing = dropped.get(s.id) ?? [];
            return (
              <div key={s.id} className="border-b border-rule py-2">
                <dt className="flex flex-wrap items-baseline gap-2">
                  <span className={`px-1 font-data text-[11px] ${BADGE[s.state]}`}>{s.state}</span>
                  <span className="font-ui text-[13px]">
                    {s.n} · {s.title}
                  </span>
                  <span className="font-data text-[10px] text-ink-faint">
                    {s.component} · {s.part}
                  </span>
                </dt>
                <dd className="mt-0.5 max-w-prose text-[12px] text-ink-muted">{s.became}</dd>
                <dd className="mt-1 max-w-prose text-[12px] text-ink-muted">
                  <span className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                    Still needs{" "}
                  </span>
                  {s.needs}
                </dd>
                {missing.length > 0 && (
                  <dd className="mt-1.5 max-w-prose bg-ground-sunk px-2 py-1">
                    <p className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                      Not printing on {q.data?.report_id ?? "the stored payload"}
                    </p>
                    <ul>
                      {missing.map((m) => (
                        <li key={m} className="font-data text-[11px] text-ink-muted">
                          — {m}
                        </li>
                      ))}
                    </ul>
                  </dd>
                )}
              </div>
            );
          })}
        </dl>
      </section>

      <section className="mb-8 max-w-3xl">
        <SectionTitle>What is defaulted, and what closes it</SectionTitle>
        <p className="mb-2 max-w-prose text-[12px] text-ink-muted">
          Owner&apos;s call, 9 September 2026: fill the report out now, default what has no feed
          behind it, set the real sources up later. Every defaulted check is on the page as a named
          row that prints <b>UNVERIFIED</b> instead of a direction — the fourth state section 04 has
          had since R4 — so the document is full-length without a single guess dressed as a
          measurement. It is honest. It is not finished, and that is what this table is for.
        </p>
        <table className="w-full border-t border-rule text-left">
          <thead>
            <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
              <th className="py-1 pr-3 font-medium">Group</th>
              <th className="py-1 pr-3 font-medium">Checks with nothing behind them</th>
              <th className="py-1 font-medium">What closes them</th>
            </tr>
          </thead>
          <tbody>
            {DEFAULTED.map((d) => (
              <tr key={d.group + d.checks} className="border-t border-rule align-top">
                <td className="py-1.5 pr-3 text-[12px] whitespace-nowrap">{d.group}</td>
                <td className="py-1.5 pr-3 font-data text-[11px] text-ink-muted">{d.checks}</td>
                <td className="max-w-prose py-1.5 text-[12px] text-ink-muted">{d.closes}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
          The live count is in section 04&apos;s line above, read from the stored payload rather
          than from this table — so if someone closes one of these and forgets to edit here, the
          number still moves.
        </p>
      </section>

      <section className="mb-8 max-w-3xl">
        <SectionTitle>What measuring turned up</SectionTitle>
        <p className="mb-2 max-w-prose font-data text-[11px] text-ink-faint">
          Each of these cost a measurement to learn and would cost the same one again. They are why
          print.css and Report.tsx carry comments telling you not to tidy them away.
        </p>
        <dl className="border-t border-rule">
          {FINDINGS.map((f) => (
            <div key={f.finding} className="border-b border-rule py-2">
              <dt className="flex items-baseline gap-2">
                <span className="font-data text-[11px] text-ink-faint">{f.part}</span>
                <span className="max-w-prose font-ui text-[13px]">{f.finding}</span>
              </dt>
              <dd className="mt-0.5 max-w-prose text-[12px] text-ink-muted">{f.detail}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="mb-8 max-w-3xl">
        <SectionTitle>Decisions closed — do not reopen</SectionTitle>
        <dl className="border-t border-rule">
          {DECISIONS.map((d) => (
            <div key={d.question} className="border-b border-rule py-2">
              <dt className="flex items-baseline gap-2">
                <span className="font-data text-[11px] text-ink-faint tabular-nums">{d.when}</span>
                <span className="max-w-prose font-ui text-[13px]">{d.question}</span>
              </dt>
              <dd className="mt-0.5 max-w-prose text-[12px] text-ink-muted">{d.answer}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="max-w-3xl">
        <SectionTitle>The parts, in the order they were built</SectionTitle>
        <table className="w-full border-t border-rule text-left">
          <thead>
            <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
              <th className="py-1 pr-3 font-medium">Part</th>
              <th className="py-1 pr-3 font-medium">What shipped</th>
              <th className="py-1 font-medium">When</th>
            </tr>
          </thead>
          <tbody>
            {PARTS.map((p) => (
              <tr key={p.part} className="border-t border-rule align-top">
                <td className="py-1.5 pr-3 font-data text-[13px]">{p.part}</td>
                <td className="max-w-prose py-1.5 pr-3 text-[12px] text-ink-muted">{p.what}</td>
                <td className="py-1.5 font-data text-[12px] whitespace-nowrap text-ink-faint">
                  {p.when}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}

function Row({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-4 border-b border-rule py-1.5">
      <dt className="font-ui text-[13px]">{label}</dt>
      <dd
        className={
          warn ? "bg-warn-ground px-1 font-data text-[12px] text-warn" : "font-data text-[12px]"
        }
      >
        {value}
      </dd>
    </div>
  );
}

function Figure({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div>
      <div className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">{label}</div>
      <div
        className={
          warn ? "bg-warn-ground px-1 font-data text-[15px] text-warn" : "font-data text-[15px]"
        }
      >
        {value}
      </div>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-2 font-ui text-[10px] font-bold tracking-[0.08em] text-ink-faint uppercase">
      {children}
    </h2>
  );
}
