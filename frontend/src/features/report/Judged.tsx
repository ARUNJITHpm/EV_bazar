import { formatKva, formatUtilisation, kva } from "../../lib/units";
import { HORIZON_YEARS, type ReportPayload, type Verdict } from "./payload";
import { Footnote, Note, Section, TD, TH, Table, ReportScroll } from "./parts";

/**
 * 03 — the rules, stated BEFORE any site data appears. Placement is the
 * point: a standard shown before the evidence visibly was not fitted to the
 * conclusion. These are the assembler's actual rules (assemble.py: the
 * verdict reads P10 against the running-bill breakeven), written out in
 * plain words.
 *
 * TRACK B · R8 CUT THIS TABLE DOWN. It had grown to six rows — two
 * thresholds, three verdicts and the horizon — and a table of six rows
 * carrying three different kinds of thing is not a rule, it is a glossary.
 * R5 put the second breakeven here because nothing else said which line the
 * verdict meant; R7 then gave that line a chart, a formula and a lever of
 * its own. So the thresholds move OUT of the table into the paragraph below
 * it, and the table goes back to being the one thing it is for: three
 * answers, and the rule that produces each.
 *
 * THE RULE WE PRINT IS OURS, NOT THE SAMPLE'S. The sample document measures
 * all three verdicts against its full-cost line. Our engine measures them
 * against the running-bill line and reports the full-cost line separately
 * (R5's decision). Copying the sample's wording would make this section
 * describe a rule the code does not run — which is the exact failure the
 * rebuild exists to remove — so the paragraph says plainly which line the
 * verdict uses and what the other one is for.
 *
 * The verdict names match section 01 exactly. They used to not: this table
 * said "Build — conditional" months after R3 removed that prefix from the
 * verdict block, for the reason R3 recorded — at a glance the first word was
 * the whole word, and the whole word said BUILD.
 */

const RULES: { answer: string; verdict: Verdict; rule: string }[] = [
  {
    answer: "BUILD",
    verdict: "build",
    rule: "The downside case covers the running bills on its own. The site pays its way even in a bad year, so the verdict does not depend on demand landing where we expect.",
  },
  {
    answer: "CONDITIONAL",
    verdict: "conditional",
    rule: "The central case covers the running bills and the downside case does not. Building is a bet on the central case, unless a contract removes the bet.",
  },
  {
    answer: "DON’T BUILD",
    verdict: "dont",
    rule: "Even the central case falls short of the running bills. No plausible level of demand covers the costs at this build cost, tariff and price.",
  },
];

export function Judged({ payload }: { payload: ReportPayload }) {
  const { breakeven, hardware, financials, verdict } = payload;
  const sl = financials.sanctioned_load;
  const twoLines = breakeven.full_cost_utilisation != null && breakeven.full_cost_kwh_day != null;

  return (
    <Section
      num="03"
      title="How this site was judged"
      heading="Same rules. Every site."
      standfirst="These three rules are written into the engine before any pin is placed, and they are the same for every site Chargeworthy assesses. The verdict reads the downside case, never the central one — a site is only as good as its bad year."
      id="judged"
    >
      <Table minWidth="30rem" zebra={false}>
        <thead>
          <tr>
            <th className={TH}>Answer</th>
            <th className={TH}>The rule that produces it</th>
          </tr>
        </thead>
        <tbody>
          {RULES.map((r) => (
            <tr key={r.answer}>
              <td className={`${TD} w-[10rem] font-cw-mono text-[15px] whitespace-nowrap`}>
                {r.answer}
                {r.verdict === verdict.value && (
                  <span className="mt-1 block text-[13px] font-normal text-cw-paper-muted">
                    this site
                  </span>
                )}
              </td>
              <td className={`${TD} text-[15px] text-cw-paper-muted`}>{r.rule}</td>
            </tr>
          ))}
        </tbody>
      </Table>

      <div className="mt-6">
        <p className="m-0 font-cw-mono text-[13px] tracking-[0.12em] text-cw-paper-slate uppercase">
          Two thresholds, and the rules above use the first
        </p>
        <p className="mt-2 mb-0 max-w-[72ch] text-[17px] leading-[1.65]">
          The <strong className="font-medium">running-bill breakeven</strong> —{" "}
          <span className="font-cw-mono tabular-nums">
            {formatUtilisation(breakeven.utilisation)}
          </span>
          , about <span className="font-cw-mono tabular-nums">{breakeven.kwh_day}</span> units a day
          — is what must be sold before the site stops losing money month to month. The build cost
          is not in it.
          {twoLines &&
            breakeven.full_cost_utilisation != null &&
            breakeven.full_cost_kwh_day != null && (
              <>
                {" "}
                The <strong className="font-medium">full-cost breakeven</strong> —{" "}
                <span className="font-cw-mono tabular-nums">
                  {formatUtilisation(breakeven.full_cost_utilisation)}
                </span>
                , about{" "}
                <span className="font-cw-mono tabular-nums">{breakeven.full_cost_kwh_day}</span>{" "}
                units a day — also recovers the setup cost over {HORIZON_YEARS} years, at the same
                rate the value column discounts at, so a site sitting exactly on it has a{" "}
                {HORIZON_YEARS}-year value of zero.{" "}
                <strong className="font-medium">
                  A site can clear the first line, earn a BUILD, and still be short over{" "}
                  {HORIZON_YEARS} years.
                </strong>{" "}
                Section 09 draws both.
              </>
            )}
        </p>
        <Footnote>
          {/* Counted, not assumed. A payload without the second threshold
              printed "Neither line…" under a paragraph carrying one — the
              same trap R7 found in section 09's provenance note. */}
          {twoLines
            ? "Neither line includes tax or financing costs, and neither counts a fleet or campus contract: both ask how busy walk-in trade has to be."
            : "This line includes no tax or financing costs, and does not count a fleet or campus contract: it asks how busy walk-in trade has to be."}
        </Footnote>
      </div>

      <div className="mt-8">
        <p className="m-0 font-cw-mono text-[13px] tracking-[0.12em] text-cw-paper-slate uppercase">
          A small first phase, not an oversized station
        </p>
        {/* A `figure` so the drawing cannot be cut across a page: section
            03 is now taller than one, and print.css protects figures rather
            than whole sections. */}
        <figure className="m-0">
          <ConceptPlot
            bays={hardware.connectors}
            kwEach={hardware.rated_kw_each}
            supplyKva={sl.recommended_kva}
          />
        </figure>
        <Note className="mt-3">
          Concept only. Not a survey, route map or approved layout, and not to scale — it is what
          the money in section 05 is costed against, drawn before any measurement of this site
          appears. Each bay has its own{" "}
          <span className="font-cw-mono text-cw-ink tabular-nums">{hardware.rated_kw_each} kW</span>{" "}
          charger; the grid connection is sized at{" "}
          <span className="font-cw-mono text-cw-ink tabular-nums">
            {formatKva(kva(sl.recommended_kva))}
          </span>{" "}
          rather than{" "}
          <span className="font-cw-mono text-cw-ink tabular-nums">
            {formatKva(kva(sl.full_kva))}
          </span>{" "}
          on the assumption that the peak is managed, so two vehicles charging at once do not each
          get the full rate. Supply is subject to electrical design and DISCOM approval.
        </Note>
      </div>
    </Section>
  );
}

/*
 * The concept, as a plan.
 *
 * Inline SVG rather than an image: it needs no key, never fails to load,
 * prints as vector, and claims nothing about the ground. The two Mapbox
 * pictures in section 04 are evidence about THIS plot; this one is a
 * statement of what is being costed, which is why it belongs before the site
 * data rather than among it.
 *
 * IT DRAWS OUR CONFIGURATION, NOT THE SAMPLE'S. The sample shows one 60 kW
 * charger shared across two outlets. Our engine models one charger per bay
 * and shares the GRID CONNECTION instead — `sanctioned_load` recommends a
 * connection smaller than the sum of the chargers, on the assumption the
 * peak is managed. Drawing the sample's arrangement would have put a
 * configuration on the page that no number in the document was computed
 * from; drawing ours makes section 05's sanctioned-load lever visible two
 * sections before it is quantified.
 *
 * Everything is stroked, nothing is filled: this page is photocopied.
 */

const PLOT = { x: 60, y: 118, w: 640, h: 216 };
const BAY = { y: 166, h: 68, gap: 24, inset: 50 };
const BUS_Y = 258;
const SUPPLY = { y: 276, h: 44, w: 132 };

function ConceptPlot({
  bays,
  kwEach,
  supplyKva,
}: {
  bays: number;
  kwEach: number;
  supplyKva: number;
}) {
  const n = Math.max(1, Math.min(bays, 6));
  const span = PLOT.w - BAY.inset * 2;
  const width = (span - BAY.gap * (n - 1)) / n;
  const left = PLOT.x + BAY.inset;
  const centres = Array.from({ length: n }, (_, i) => left + i * (width + BAY.gap) + width / 2);
  const mid = PLOT.x + PLOT.w / 2;
  const first = centres[0] ?? mid;
  const last = centres[n - 1] ?? mid;

  return (
    <ReportScroll label="Concept site plan" diagram>
      <svg
        viewBox="0 0 760 344"
        role="img"
        aria-label={`Schematic plan: a main road, an access lane, and a plot holding ${n} charging ${
          n === 1 ? "bay" : "bays"
        } of ${kwEach} kilowatts each, all drawing on one ${supplyKva} kVA grid connection. Concept only, not to scale.`}
        className="mt-4 w-full"
      >
        {/* MAIN ROAD — two edges and a dashed centre line, read as a road. */}
        <line x1="20" y1="18" x2="740" y2="18" className="stroke-cw-ink" strokeWidth="1.5" />
        <line x1="20" y1="62" x2="740" y2="62" className="stroke-cw-ink" strokeWidth="1.5" />
        {/* The centre line starts clear of the label; dashes running behind
          "MAIN ROAD" read as a printing fault, not as a road. */}
        <line
          x1="130"
          y1="40"
          x2="640"
          y2="40"
          className="stroke-cw-rule"
          strokeWidth="1"
          strokeDasharray="12 10"
        />
        <text x="34" y="36" className="fill-cw-paper-muted font-cw-mono text-[11px]">
          MAIN ROAD
        </text>
        <path
          d="M 660 40 L 700 40 M 692 34 L 700 40 L 692 46"
          className="stroke-cw-ink"
          fill="none"
          strokeWidth="1.5"
        />

        {/* ACCESS LANE — from the road down into the plot. */}
        <line x1="190" y1="62" x2="190" y2={PLOT.y} className="stroke-cw-rule" strokeWidth="1.5" />
        <line x1="240" y1="62" x2="240" y2={PLOT.y} className="stroke-cw-rule" strokeWidth="1.5" />
        <path
          d="M 215 74 L 215 106 M 209 98 L 215 106 L 221 98"
          className="stroke-cw-ink"
          fill="none"
          strokeWidth="1.5"
        />
        <text x="256" y="96" className="fill-cw-paper-muted font-cw-mono text-[11px]">
          ACCESS LANE
        </text>

        {/* CONCEPT PLOT */}
        <rect
          x={PLOT.x}
          y={PLOT.y}
          width={PLOT.w}
          height={PLOT.h}
          className="stroke-cw-ink"
          fill="none"
          strokeWidth="1.5"
        />
        <text
          x={PLOT.x + 16}
          y={PLOT.y + 24}
          className="fill-cw-paper-muted font-cw-mono text-[11px]"
        >
          CONCEPT PLOT
        </text>

        {centres.map((cx, i) => (
          <g key={i}>
            <rect
              x={cx - width / 2}
              y={BAY.y}
              width={width}
              height={BAY.h}
              className="stroke-cw-rule"
              fill="none"
              strokeWidth="1.5"
            />
            <text
              x={cx}
              y={BAY.y + 28}
              textAnchor="middle"
              className="fill-cw-ink font-cw-mono text-[12px] font-medium"
            >
              BAY {i + 1}
            </text>
            <text
              x={cx}
              y={BAY.y + 50}
              textAnchor="middle"
              className="fill-cw-paper-muted font-cw-mono text-[11px]"
            >
              {kwEach} kW
            </text>
            {/* the cable down to the shared connection */}
            <line
              x1={cx}
              y1={BAY.y + BAY.h}
              x2={cx}
              y2={BUS_Y}
              className="stroke-cw-rule"
              strokeWidth="1"
            />
          </g>
        ))}
        {n > 1 && (
          <line
            x1={first}
            y1={BUS_Y}
            x2={last}
            y2={BUS_Y}
            className="stroke-cw-rule"
            strokeWidth="1"
          />
        )}
        <line
          x1={mid}
          y1={BUS_Y}
          x2={mid}
          y2={SUPPLY.y}
          className="stroke-cw-rule"
          strokeWidth="1"
        />

        <rect
          x={mid - SUPPLY.w / 2}
          y={SUPPLY.y}
          width={SUPPLY.w}
          height={SUPPLY.h}
          className="stroke-cw-ink"
          fill="none"
          strokeWidth="1.5"
        />
        <text
          x={mid}
          y={SUPPLY.y + 19}
          textAnchor="middle"
          className="fill-cw-ink font-cw-mono text-[12px] font-medium"
        >
          {formatKva(kva(supplyKva))}
        </text>
        <text
          x={mid}
          y={SUPPLY.y + 35}
          textAnchor="middle"
          className="fill-cw-paper-muted font-cw-mono text-[11px]"
        >
          one connection
        </text>
      </svg>
    </ReportScroll>
  );
}
