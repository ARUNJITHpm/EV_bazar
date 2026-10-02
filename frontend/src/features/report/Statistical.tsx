import { formatRupeesCompact, formatRupeesPrecise } from "../../lib/money";
import { formatPercentagePoints, formatUtilisation } from "../../lib/units";
import { HORIZON_YEARS, type ReportPayload, type Verdict } from "./payload";
import { Chip, Figure, Note, Section, ReportScroll } from "./parts";

/**
 * 09 — for the accountant and the credit officer. The confidence band is the
 * ONLY chart in the document: the P10–P90 range as a hatched bar, the
 * central case as a thin tick, and the thresholds it has to clear as
 * vertical rules. Whether the bar clears them IS the verdict — it must read
 * in one second without a word, and every value is written as text too so
 * the figure survives a photocopier.
 *
 * Hand-drawn SVG, not a chart library. The band is hatched because it is
 * modelled (synthetic_v0), not measured — solid ink is reserved for facts.
 *
 * TWO RULES, NOT ONE (Track B · R7). R5 gave the engine a second breakeven
 * and R6 printed ten years of running total against the build cost; this
 * chart went on drawing one line, so a reader could watch the band clear
 * "breakeven" and never see the harder standard it misses. The bills line is
 * SOLID and heavy because it is the rule the verdict is measured against.
 * The build-cost line is DASHED and lighter because no verdict is measured
 * against it — it is the answer to a different question, and drawing them
 * identically would have invented a second rule the engine does not apply.
 * Neither carries colour: this page gets photocopied into a bank file.
 *
 * AND THE SUM IS PRINTED, NOT ASSERTED. The two lines differ by exactly one
 * term — the build cost spread over the horizon — and printing both
 * divisions is the only way that fact is visible rather than claimed. Every
 * term comes off the payload (`engine.py` publishes the recovery figure for
 * this); nothing here is arithmetic.
 *
 * WHAT THIS SECTION DELIBERATELY DOES NOT CARRY: the price-sensitivity strip
 * the sample document puts here. R6 already put one at the foot of section
 * 05, in the same units, one section earlier — and a document that prints
 * the same three numbers twice teaches the reader that its sections are not
 * about different things. A clause points there instead.
 */

const X0 = 24;
const X1 = 736;
//: The axis adapts to the numbers: a 2% band against a 4% threshold must
//: fill the figure, not huddle at the left edge of a fixed scale. The ladder
//: keeps the ceiling a round number a reader can anchor on.
const SCALE_LADDER = [0.05, 0.1, 0.2, 0.4, 0.6, 1.0];

/** Where the band sits against the line the VERDICT uses. */
const PLAIN: Record<Verdict, string> = {
  build: "Even the downside case clears the point where the site covers its running bills.",
  conditional:
    "The likely range straddles the bills line: the central case clears it, the downside does not.",
  dont: "Even the central case runs below the point where the site covers its running bills.",
};

/**
 * And where the same band sits against the harder line — chosen from the
 * data rather than from the verdict, because no verdict is measured against
 * this line and a sentence keyed on one would be asserting a rule the engine
 * does not apply.
 */
function fullCostSentence(p: ReportPayload, fc: number): string {
  const { p10, p50, p90 } = p.predicted;
  if (p10 >= fc) {
    return `Every case pictured also clears the build-cost line, so the setup cost comes back inside ${HORIZON_YEARS} years even at the low end.`;
  }
  if (p50 >= fc) {
    return `The build-cost line falls inside the band: the central case returns the setup cost over ${HORIZON_YEARS} years, the downside case does not.`;
  }
  if (p90 >= fc) {
    return `Only the upside case clears the build-cost line. The central case covers its bills and still does not return the setup cost over ${HORIZON_YEARS} years.`;
  }
  return `No case pictured clears the build-cost line — even the upside case leaves part of the setup cost unrecovered after ${HORIZON_YEARS} years.`;
}

function pct(fraction: number): string {
  // Rounded before the integer test, not after. `0.75 * 0.2` is
  // 0.15000000000000002 in binary floating point, which printed a tick row
  // reading "0% 5% 10% 15.0% 20%" — one label in a different format from its
  // neighbours is read as a mistake rather than as precision. Found by
  // looking at the axis while R7 rebuilt this section.
  const v = Math.round(fraction * 1000) / 10;
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

/**
 * Every term of the two divisions, or nothing.
 *
 * Half a sum is worse than none: a reader invited to check the arithmetic
 * has to be able to finish it, and a payload stored by economics 0.2.0 or
 * earlier is missing either the bills breakdown, the margin, or the recovery
 * figure. The section then prints the two thresholds and lets section 03's
 * rules table say what they mean.
 */
function terms(p: ReportPayload): {
  billsYear: number;
  marginUnit: number;
  recoveryYear: number;
  fullCostKwhYear: number;
} | null {
  const bills = p.financials.fixed_costs;
  const unit = p.financials.unit_economics;
  const recovery = p.breakeven.full_cost_recovery_paise_year;
  const fullCostKwhYear = p.breakeven.full_cost_kwh_year;
  if (!bills || !unit || recovery == null || fullCostKwhYear == null) return null;
  return {
    billsYear: bills.total_paise_year,
    marginUnit: unit.margin_paise_kwh,
    recoveryYear: recovery,
    fullCostKwhYear,
  };
}

/*
 * THE CHART IS LAID OUT IN ROWS THAT NOTHING CROSSES, and that is not
 * fussiness — the first draft let both rules run the full height and the
 * dashed one printed straight through the word "bills" in the other one's
 * label and through "P10 7.2%" as well. Two labels on separate lines do not
 * collide with each other; a label still collides with the OTHER line. So:
 *
 *   0–46    threshold labels. No line reaches up here.
 *   48–110  the rules, the band, the central tick. No text lives here.
 *   110–150 the axis, its ticks and the unit caption.
 *   160–190 the margin-of-safety dimension, label below its own end caps.
 *
 * The band's P10 and P90 values moved into the figures above the chart when
 * this row scheme went in: inside the plot they were text in the one row
 * that cannot have any.
 */
const PLOT_TOP = 48;
const AXIS_Y = 110;

/** A labelled vertical rule. Flips its label inward near the right edge so a
 *  threshold high on the scale does not print off the page. */
function Threshold({
  x,
  y,
  label,
  dashed = false,
}: {
  x: number;
  y: number;
  label: string;
  dashed?: boolean;
}) {
  const left = x > X1 - 190;
  return (
    <>
      <line
        x1={x}
        y1={PLOT_TOP}
        x2={x}
        y2={AXIS_Y}
        className="stroke-cw-ink"
        strokeWidth={dashed ? 2 : 3}
        strokeDasharray={dashed ? "5 4" : undefined}
      />
      <text
        x={left ? x - 8 : x + 8}
        y={y}
        textAnchor={left ? "end" : "start"}
        className="fill-cw-ink font-cw-mono text-[12px] font-medium"
      >
        {label}
      </text>
    </>
  );
}

export function Statistical({ payload }: { payload: ReportPayload }) {
  const { breakeven, predicted, margin_of_safety_pp, hardware } = payload;
  const fullCost = breakeven.full_cost_utilisation ?? null;

  const top = Math.max(predicted.p90, breakeven.utilisation, fullCost ?? 0) * 1.35;
  const scaleMax = SCALE_LADDER.find((s) => s >= top) ?? 1.0;
  const x = (u: number): number => X0 + (u / scaleMax) * (X1 - X0);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * scaleMax);
  const bx = x(breakeven.utilisation);

  const working = terms(payload);

  return (
    <Section
      num="09"
      title="Statistical basis"
      heading="How sure we are, and why."
      standfirst="Utilisation is energy sold divided by the energy these chargers could deliver if they ran every hour of the year — not the share of time a bay is occupied. A site can look busy and still sell very little."
      id="statistical"
    >
      <div className="flex flex-wrap gap-x-10 gap-y-5">
        <Figure label="Projected utilisation, central" value={formatUtilisation(predicted.p50)} />
        <Figure
          label="Likely range, P10–P90"
          value={`${formatUtilisation(predicted.p10)} – ${formatUtilisation(predicted.p90)}`}
          small
        />
        <Figure
          label="Covers the running bills at"
          value={formatUtilisation(breakeven.utilisation)}
          small
          detail={`about ${breakeven.kwh_day} units a day`}
        />
        {fullCost != null && breakeven.full_cost_kwh_day != null && (
          <Figure
            label="Returns the build cost at"
            value={formatUtilisation(fullCost)}
            small
            detail={`about ${breakeven.full_cost_kwh_day} units a day`}
          />
        )}
      </div>

      {/* A `figure` for the same reason section 03's plot is one: this
          section outgrew a page in R7, and a chart cut in half at the axis
          is worse than a chart on the next page. */}
      <figure className="m-0">
        <ReportScroll label="Utilisation diagram" diagram>
          <svg
            viewBox="0 0 760 196"
            role="img"
            aria-label={`Utilisation scale from 0 to ${pct(scaleMax)} percent. Projected range ${formatUtilisation(
              predicted.p10,
            )} to ${formatUtilisation(predicted.p90)}, central ${formatUtilisation(
              predicted.p50,
            )}. The site covers its running bills at ${formatUtilisation(breakeven.utilisation)}${
              fullCost == null
                ? ""
                : ` and returns its build cost at ${formatUtilisation(fullCost)}`
            }.`}
            className="mt-6 w-full"
          >
            <defs>
              <pattern
                id="modelled"
                width="6"
                height="6"
                patternTransform="rotate(45)"
                patternUnits="userSpaceOnUse"
              >
                <rect width="6" height="6" className="fill-cw-paper" />
                <line x1="0" y1="0" x2="0" y2="6" className="stroke-cw-band" strokeWidth="3" />
              </pattern>
            </defs>

            {/* axis */}
            <line
              x1={X0}
              y1={AXIS_Y}
              x2={X1}
              y2={AXIS_Y}
              className="stroke-cw-rule"
              strokeWidth="1"
            />
            {ticks.map((t) => (
              <g key={t}>
                <line
                  x1={x(t)}
                  y1={AXIS_Y}
                  x2={x(t)}
                  y2={AXIS_Y + 6}
                  className="stroke-cw-rule"
                  strokeWidth="1"
                />
                <text
                  x={x(t)}
                  y="130"
                  textAnchor="middle"
                  className="fill-cw-paper-muted font-cw-mono text-[11px]"
                >
                  {pct(t)}%
                </text>
              </g>
            ))}
            <text
              x={X1}
              y="148"
              textAnchor="end"
              className="fill-cw-paper-muted font-cw-mono text-[11px]"
            >
              utilisation, share of rated capacity
            </text>

            {/* the band: P10 to P90, hatched because modelled */}
            <rect
              x={x(predicted.p10)}
              y="62"
              width={Math.max(x(predicted.p90) - x(predicted.p10), 2)}
              height="34"
              fill="url(#modelled)"
              className="stroke-cw-band"
              strokeWidth="1"
            />
            <line
              x1={x(predicted.p50)}
              y1="58"
              x2={x(predicted.p50)}
              y2="100"
              className="stroke-cw-ink"
              strokeWidth="1.5"
            />

            {/* The two rules, on two rows so their labels cannot collide however
            close the thresholds sit. The dashed one is the harder line and
            the one no verdict is measured against. */}
            {fullCost != null && (
              <Threshold
                x={x(fullCost)}
                y={14}
                label={`build cost back ${formatUtilisation(fullCost)}`}
                dashed
              />
            )}
            <Threshold
              x={bx}
              y={36}
              label={`covers the bills ${formatUtilisation(breakeven.utilisation)}`}
            />

            {/* Margin of safety as a dimension line, P10 → the bills line. Its
            label sits BELOW its own end caps: the caps are vertical and the
            sentence is wider than a narrow span, so a centred label on the
            same row printed straight through both of them. */}
            <line
              x1={x(predicted.p10)}
              y1="166"
              x2={bx}
              y2="166"
              className="stroke-cw-paper-muted"
              strokeWidth="1"
            />
            <line
              x1={x(predicted.p10)}
              y1="161"
              x2={x(predicted.p10)}
              y2="171"
              className="stroke-cw-paper-muted"
              strokeWidth="1"
            />
            <line
              x1={bx}
              y1="161"
              x2={bx}
              y2="171"
              className="stroke-cw-paper-muted"
              strokeWidth="1"
            />
            <text
              x={(x(predicted.p10) + bx) / 2}
              y="188"
              textAnchor="middle"
              className="fill-cw-ink font-cw-mono text-[11px]"
            >
              {formatPercentagePoints(margin_of_safety_pp)} at the downside
            </text>
          </svg>
        </ReportScroll>
      </figure>

      <p className="mt-3.5 mb-0 max-w-[64ch] text-[17px] text-cw-paper-muted">
        {PLAIN[payload.verdict.value]} {fullCost != null && fullCostSentence(payload, fullCost)}
      </p>

      {working && (
        <div className="mt-5">
          <p className="m-0 font-cw-mono text-[13px] tracking-[0.12em] text-cw-paper-slate uppercase">
            Where the two lines come from
          </p>
          <p className="mt-2 mb-0 max-w-[74ch] text-[17px] leading-[1.65]">
            <span className="font-cw-mono tabular-nums">
              {formatRupeesCompact(working.billsYear)}
            </span>{" "}
            of bills a year ÷{" "}
            <span className="font-cw-mono tabular-nums">
              {formatRupeesPrecise(working.marginUnit)}
            </span>{" "}
            left on each unit ={" "}
            <span className="font-cw-mono font-medium tabular-nums">
              {Math.round(breakeven.kwh_year).toLocaleString("en-IN")}
            </span>{" "}
            units a year — the bills line, about{" "}
            <span className="font-cw-mono tabular-nums">{breakeven.kwh_day}</span> a day.
          </p>
          <p className="mt-2.5 mb-0 max-w-[74ch] text-[17px] leading-[1.65]">
            Add the build cost, spread over {HORIZON_YEARS} years at the same rate this document
            discounts at —{" "}
            <span className="font-cw-mono tabular-nums">
              {formatRupeesCompact(working.recoveryYear)}
            </span>{" "}
            a year — and the same division gives{" "}
            <span className="font-cw-mono font-medium tabular-nums">
              {Math.round(working.fullCostKwhYear).toLocaleString("en-IN")}
            </span>{" "}
            units a year: the build-cost line, about{" "}
            <span className="font-cw-mono tabular-nums">{breakeven.full_cost_kwh_day}</span> a day.
            One extra term is the whole difference between the two rules.
          </p>
        </div>
      )}

      <Note className="mt-4">
        Model: <span className="font-cw-mono">{predicted.model_version}</span>. The band is modelled
        from the site’s archetype, district EV density and competitor density; it widens for every
        input we could not verify.{" "}
        {/* Counted from what is actually drawn. A payload with one threshold
            printed "Both lines hold the price fixed" under a chart carrying
            one line — the document arguing with its own picture. */}
        {fullCost == null
          ? "The line holds the price and the fees fixed — what happens to it"
          : "Both lines hold the price and the fees fixed — what happens to them"}{" "}
        when the price moves is at the foot of section 05.{" "}
        {predicted.modelled_not_measured && <Chip>modelled, not measured</Chip>}{" "}
        <a href="#ledger" className="underline underline-offset-2">
          See the assumptions ledger.
        </a>
      </Note>

      <Note className="mt-2.5">
        “Rated capacity” is {hardware.connectors} × {hardware.rated_kw_each} kW running every hour
        of the year. No plausible site sells that, which is why these percentages are small and why
        the thresholds are too.
      </Note>
    </Section>
  );
}
