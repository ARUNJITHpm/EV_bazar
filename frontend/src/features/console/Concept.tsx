import { Link } from "react-router-dom";

import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/**
 * PART C — the site-assessment concept, recorded where operators look.
 *
 * The product decisions behind /assess and /report/:id were made across
 * BRIEF_FOR_FABLE.md, OVERVIEW.md §8 and a sign-off on 2026-08-19. A decision
 * that lives only in a chat log or a doc nobody reopens is a decision that
 * gets re-litigated; this panel is the standing record. Curated by hand, like
 * the prose on Progress — the concept is not derivable from a table.
 */

const REPORT_SECTIONS: { name: string; what: string }[] = [
  {
    name: "1 · The number",
    what: "Breakeven utilisation, large. The P10–P90 band drawn against the breakeven threshold on one scale — whether the band clears the rule IS the verdict, readable in one second without a word.",
  },
  {
    name: "2 · Verdict",
    what: "Build / Conditional / Don't build — small, beneath the number, as confirmation. Always derived from P10, the cautious end, never P50.",
  },
  {
    name: "3 · Site profile",
    what: "Road class and measured distance, junctions, dwell anchors, district EV growth, competitors with distances. Every fact carries its source inline; anything unverified carries the single warn accent.",
  },
  {
    name: "4 · Financials",
    what: "Scenario table per percentile, fleet-anchor note (what changes the answer), sanctioned-load options, price sensitivity at ±₹2. Every rupee from the ROI engine.",
  },
  {
    name: "5 · CPO comparison",
    what: "The same site under each operating arrangement, ranked by IRR — financial terms and qualitative terms side by side. chargeMOD is listed '(our network)' under the same rules as everyone else.",
  },
  {
    name: "6 · Assumption ledger",
    what: "Every assumption in one table: value, source, verified or not. The reader should be able to attack the report and find it already admits its weak points.",
  },
  {
    name: "7 · Provenance",
    what: "Which data, which versions (economics, model, renderer, schema), which dates produced this exact payload — so an old report can defend itself.",
  },
];

const FIREWALL: { rule: string; why: string }[] = [
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
        note="The site-assessment product in one page: what the report is, why the number comes first, the rules that keep it honest, and where every data layer comes from. This is the standing record of decisions signed off on 2026-08-19 — the source documents are BRIEF_FOR_FABLE.md, OVERVIEW.md §8 and STACK.md §7."
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
        <SectionTitle>Number first — the signed-off hero decision</SectionTitle>
        <p className="max-w-prose text-[13px] text-ink-muted">
          Clients are putting real money in, so the report leads with the number, not a verdict
          word. A verdict up top is an app telling them what to think; the chart with the threshold
          line lets them reach the same conclusion themselves in two seconds, which is more
          persuasive and less insulting. The verdict word sits immediately underneath — small, as
          confirmation. Visual language: colder and quieter. An instrument panel, not a dashboard:
          hairline rules instead of cards, serif text and mono data, and ONE accent colour reserved
          exclusively for the unverified-assumption state, so warn marks cannot be decoration.
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
            what="The full seven-section document below, generated once, stored as JSONB, served verbatim. The report is the deliverable AND the sales artifact — its honesty is the differentiator against every consultant's optimistic PDF."
          />
          <FunnelStep
            n="3"
            name="CPO handoff — where revenue lives"
            what="The comparison table ranks operating arrangements; a customer choosing one is a lead, and proving that lead came from us is Part 7's attribution chain (schema decided by the 0.3 conversations). Ladder: audits → institutional subscriptions → commissions."
          />
        </ol>
      </section>

      <section className="mt-8 max-w-3xl">
        <SectionTitle>Report anatomy — in reading order</SectionTitle>
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
