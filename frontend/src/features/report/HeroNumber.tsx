import { formatPercentagePoints, formatUtilisation } from "../../lib/units";
import type { ReportPayload } from "./payload";

/**
 * The signature element (STACK.md §7): breakeven utilisation, the P10–P90
 * band, and the margin of safety in one composed unit. A horizontal scale,
 * the breakeven threshold as a hard vertical rule, the prediction band drawn
 * against it. Whether the band clears the rule IS the verdict — it must read
 * in one second without a word.
 *
 * Number first, deliberately: the reader reaches the conclusion themselves
 * from the figure; the verdict word below is confirmation, not instruction.
 *
 * Hand-drawn SVG, not a chart library. The band is hatched because it is
 * modelled (synthetic_v0), not measured — solid ink is reserved for facts.
 */

const X0 = 24;
const X1 = 696;

//: The axis adapts to the numbers: a 2% band against a 4% threshold must fill
//: the figure, not huddle at the left edge of a fixed 0–40% scale. The ladder
//: keeps the ceiling a round number a reader can anchor on.
const SCALE_LADDER = [0.05, 0.1, 0.2, 0.4, 0.6, 1.0];

function pct(fraction: number): string {
  const v = fraction * 100;
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

export function HeroNumber({ payload }: { payload: ReportPayload }) {
  const { breakeven, predicted, margin_of_safety_pp, hardware } = payload;
  const top = Math.max(predicted.p90, breakeven.utilisation) * 1.35;
  const scaleMax = SCALE_LADDER.find((s) => s >= top) ?? 1.0;
  const x = (utilisation: number): number => X0 + (utilisation / scaleMax) * (X1 - X0);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * scaleMax);
  const bx = x(breakeven.utilisation);

  return (
    <section data-report-section="hero" className="border-b border-rule pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-2">
        <div>
          <h2 className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
            Breakeven utilisation
          </h2>
          <p className="num mt-1 text-[2.75rem] leading-none font-bold">
            {formatUtilisation(breakeven.utilisation)}
          </p>
          <p className="num mt-1 text-[13px] text-ink-muted">
            {hardware.connectors} × {hardware.rated_kw_each} kW · ≈ {breakeven.kwh_day} kWh/day to
            clear costs
          </p>
        </div>
        <div className="text-right">
          <h2 className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
            Predicted P10–P90
          </h2>
          <p className="num mt-1 text-[1.75rem] leading-none">
            {formatUtilisation(predicted.p10)} – {formatUtilisation(predicted.p90)}
          </p>
          <p className="num mt-1 text-[13px] text-ink-muted">
            margin of safety {formatPercentagePoints(margin_of_safety_pp)} at P10
          </p>
        </div>
      </div>

      <svg
        viewBox="0 0 720 150"
        role="img"
        aria-label={`Utilisation scale from 0 to 40 percent. Predicted band ${formatUtilisation(
          predicted.p10,
        )} to ${formatUtilisation(predicted.p90)}. Breakeven threshold at ${formatUtilisation(
          breakeven.utilisation,
        )}. The band does not clear the threshold at P10.`}
        className="mt-6 w-full"
      >
        <defs>
          {/* Hatching = modelled, not measured. Solid ink is for facts. */}
          <pattern
            id="modelled"
            width="6"
            height="6"
            patternTransform="rotate(45)"
            patternUnits="userSpaceOnUse"
          >
            <rect width="6" height="6" className="fill-ground" />
            <line x1="0" y1="0" x2="0" y2="6" className="stroke-band" strokeWidth="3" />
          </pattern>
        </defs>

        {/* axis */}
        <line x1={X0} y1="96" x2={X1} y2="96" className="stroke-rule" strokeWidth="1" />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} y1="96" x2={x(t)} y2="102" className="stroke-rule" strokeWidth="1" />
            <text
              x={x(t)}
              y="116"
              textAnchor="middle"
              className="fill-ink-faint font-data text-[11px]"
            >
              {pct(t)}
            </text>
          </g>
        ))}
        <text x={X1} y="134" textAnchor="end" className="fill-ink-faint font-data text-[11px]">
          utilisation, % of rated capacity
        </text>

        {/* prediction band */}
        <rect
          x={x(predicted.p10)}
          y="56"
          width={x(predicted.p90) - x(predicted.p10)}
          height="32"
          fill="url(#modelled)"
          className="stroke-band"
          strokeWidth="1"
        />
        <line
          x1={x(predicted.p50)}
          y1="56"
          x2={x(predicted.p50)}
          y2="88"
          className="stroke-ink-muted"
          strokeWidth="1.5"
        />
        <text
          x={x(predicted.p10)}
          y="48"
          textAnchor="middle"
          className="fill-ink-muted font-data text-[11px]"
        >
          P10
        </text>
        <text
          x={x(predicted.p50)}
          y="48"
          textAnchor="middle"
          className="fill-ink-muted font-data text-[11px]"
        >
          P50
        </text>
        <text
          x={x(predicted.p90)}
          y="48"
          textAnchor="middle"
          className="fill-ink-muted font-data text-[11px]"
        >
          P90
        </text>

        {/* breakeven threshold — the hard rule the band must clear */}
        <line x1={bx} y1="24" x2={bx} y2="96" className="stroke-threshold" strokeWidth="2" />
        <text
          x={bx > 520 ? bx - 6 : bx + 6}
          y="30"
          textAnchor={bx > 520 ? "end" : "start"}
          className="fill-ink font-data text-[12px] font-bold"
        >
          breakeven {formatUtilisation(breakeven.utilisation)}
        </text>

        {/* margin of safety as a technical-drawing dimension line, P10 → threshold */}
        <line
          x1={x(predicted.p10)}
          y1="132"
          x2={bx}
          y2="132"
          className="stroke-ink-muted"
          strokeWidth="1"
        />
        <line
          x1={x(predicted.p10)}
          y1="127"
          x2={x(predicted.p10)}
          y2="137"
          className="stroke-ink-muted"
          strokeWidth="1"
        />
        <line x1={bx} y1="127" x2={bx} y2="137" className="stroke-ink-muted" strokeWidth="1" />
        <text
          x={(x(predicted.p10) + bx) / 2}
          y="128"
          textAnchor="middle"
          className="fill-ink font-data text-[11px]"
        >
          {formatPercentagePoints(margin_of_safety_pp)}
        </text>
      </svg>

      <p className="mt-3 font-data text-[11px]">
        <span className="bg-warn-ground px-1 text-warn">
          band: {predicted.model_version} — modelled, not measured
        </span>
        <a href="#ledger" className="ml-2 text-ink-muted underline underline-offset-2">
          see ledger
        </a>
      </p>
    </section>
  );
}
