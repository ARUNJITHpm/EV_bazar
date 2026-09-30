import type { StationHome } from "./state";
import { WHOLE } from "./ui";

/**
 * Monthly kWh against months since the station opened (not calendar months).
 *
 * Hand-drawn SVG. Each series has its own marker SHAPE as well as its own
 * colour, so the chart reads without colour:
 *
 *   your bills          filled circle, joined by a line
 *   next-month forecast diamond with a P10-P90 whisker (copper: the forecast only)
 *   similar stations    square on the median, shaded P10-P90 band (10+ stations only)
 *   model estimate      triangle on a dashed line, shown INSTEAD of the peers
 *                       when there are too few real ones, and labelled as such
 */

const W = 720;
const H = 340;
const M = { l: 64, r: 24, t: 24, b: 56 };

function niceStep(raw: number): number {
  const pow = 10 ** Math.floor(Math.log10(raw));
  const f = raw / pow;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pow;
}

export function TrendChart({ home }: { home: StationHome }) {
  const { series, forecast, peer } = home;
  const peerPts = peer.available ? peer.band : [];
  const modelPts = peer.available ? [] : peer.model_curve;

  const xs = [
    ...series.map((p) => p.month_of_operation),
    ...(forecast ? [forecast.month_of_operation] : []),
    ...peerPts.map((p) => p.month_of_operation),
    ...modelPts.map((p) => p.month_of_operation),
  ];
  const xMax = Math.max(2, ...xs);
  const yMaxRaw = Math.max(
    1,
    ...series.map((p) => p.kwh),
    ...(forecast ? [forecast.band.p90_kwh] : []),
    ...peerPts.map((p) => p.band.p90_kwh),
    ...modelPts.map((p) => p.band.p90_kwh),
  );
  const yStep = niceStep(yMaxRaw / 4);
  const yMax = Math.ceil(yMaxRaw / yStep) * yStep;

  const x = (m: number) => M.l + ((m - 1) / (xMax - 1)) * (W - M.l - M.r);
  const y = (v: number) => H - M.b - (v / yMax) * (H - M.t - M.b);
  const xStep = Math.max(1, Math.ceil(xMax / 8));
  const xTicks = Array.from(
    { length: Math.floor((xMax - 1) / xStep) + 1 },
    (_, i) => 1 + i * xStep,
  );
  const yTicks = Array.from({ length: Math.round(yMax / yStep) + 1 }, (_, i) => i * yStep);

  const line = (pts: { m: number; v: number }[]) =>
    pts.map((p, i) => `${i ? "L" : "M"}${x(p.m).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  const band = (pts: { m: number; lo: number; hi: number }[]) =>
    pts.length < 2
      ? ""
      : `${pts.map((p, i) => `${i ? "L" : "M"}${x(p.m).toFixed(1)},${y(p.hi).toFixed(1)}`).join(" ")} ${[
          ...pts,
        ]
          .reverse()
          .map((p) => `L${x(p.m).toFixed(1)},${y(p.lo).toFixed(1)}`)
          .join(" ")} Z`;

  const peerBand = peerPts.map((p) => ({
    m: p.month_of_operation,
    lo: p.band.p10_kwh,
    hi: p.band.p90_kwh,
    mid: p.band.p50_kwh,
  }));
  const modelBand = modelPts.map((p) => ({
    m: p.month_of_operation,
    lo: p.band.p10_kwh,
    hi: p.band.p90_kwh,
    mid: p.band.p50_kwh,
  }));

  return (
    <div className="flex flex-col gap-4">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Monthly kWh by months since opening. ${series.length} of your bills${
          forecast ? ", and next month's forecast range" : ""
        }.`}
        className="h-auto w-full"
      >
        {yTicks.map((t) => (
          <g key={t}>
            <line
              x1={M.l}
              x2={W - M.r}
              y1={y(t)}
              y2={y(t)}
              className="stroke-cw-line"
              strokeWidth={1}
            />
            <text
              x={M.l - 10}
              y={y(t) + 5}
              textAnchor="end"
              className="fill-cw-muted font-cw-mono text-[13px]"
            >
              {WHOLE.format(t)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text
            key={t}
            x={x(t)}
            y={H - M.b + 24}
            textAnchor="middle"
            className="fill-cw-muted font-cw-mono text-[13px]"
          >
            {t}
          </text>
        ))}
        <text
          x={(M.l + W - M.r) / 2}
          y={H - 8}
          textAnchor="middle"
          className="fill-cw-muted text-[14px]"
        >
          Months since opening
        </text>
        <text
          transform={`translate(16 ${(M.t + H - M.b) / 2}) rotate(-90)`}
          textAnchor="middle"
          className="fill-cw-muted text-[14px]"
        >
          kWh per month
        </text>

        {peerBand.length > 1 && (
          <path d={band(peerBand)} className="fill-cw-slate" fillOpacity={0.18} />
        )}
        {peerBand.length > 0 && (
          <>
            <path
              d={line(peerBand.map((p) => ({ m: p.m, v: p.mid })))}
              className="fill-none stroke-cw-slate"
              strokeWidth={2}
            />
            {peerBand.map((p) => (
              <rect
                key={p.m}
                x={x(p.m) - 4.5}
                y={y(p.mid) - 4.5}
                width={9}
                height={9}
                className="fill-cw-slate"
              />
            ))}
          </>
        )}

        {modelBand.length > 1 && (
          <path d={band(modelBand)} className="fill-cw-muted" fillOpacity={0.1} />
        )}
        {modelBand.length > 0 && (
          <>
            <path
              d={line(modelBand.map((p) => ({ m: p.m, v: p.mid })))}
              className="fill-none stroke-cw-muted"
              strokeWidth={2}
              strokeDasharray="6 5"
            />
            {modelBand.map((p) => (
              <path
                key={p.m}
                d={`M${x(p.m)},${y(p.mid) - 6} l6,11 h-12 Z`}
                className="fill-cw-muted"
              />
            ))}
          </>
        )}

        {series.length > 0 && (
          <path
            d={line(series.map((p) => ({ m: p.month_of_operation, v: p.kwh })))}
            className="fill-none stroke-cw-text"
            strokeWidth={2}
          />
        )}
        {series.map((p) => (
          <circle
            key={p.period}
            cx={x(p.month_of_operation)}
            cy={y(p.kwh)}
            r={5.5}
            className="fill-cw-text stroke-cw-ground"
            strokeWidth={2}
          />
        ))}

        {forecast && (
          <g>
            <line
              x1={x(forecast.month_of_operation)}
              x2={x(forecast.month_of_operation)}
              y1={y(forecast.band.p90_kwh)}
              y2={y(forecast.band.p10_kwh)}
              className="stroke-cw-accent"
              strokeWidth={3}
            />
            {[forecast.band.p10_kwh, forecast.band.p90_kwh].map((v) => (
              <line
                key={v}
                x1={x(forecast.month_of_operation) - 8}
                x2={x(forecast.month_of_operation) + 8}
                y1={y(v)}
                y2={y(v)}
                className="stroke-cw-accent"
                strokeWidth={3}
              />
            ))}
            <path
              d={`M${x(forecast.month_of_operation)},${y(forecast.band.p50_kwh) - 9} l9,9 l-9,9 l-9,-9 Z`}
              className="fill-cw-accent stroke-cw-ground"
              strokeWidth={2}
            />
          </g>
        )}
      </svg>

      <ul className="flex flex-wrap gap-x-7 gap-y-2 text-[15px] text-cw-muted" aria-label="Legend">
        <Key shape="circle" label="Your bills" />
        {forecast && <Key shape="diamond" label="Next month, likely range" copper />}
        {peerPts.length > 0 && <Key shape="square" label="Similar stations, middle 80%" />}
        {modelPts.length > 0 && <Key shape="triangle" label="Model estimate, not measured" />}
      </ul>

      <details className="text-[15px] text-cw-muted">
        <summary className="inline-flex min-h-[44px] cursor-pointer items-center">
          See the numbers
        </summary>
        <table className="mt-2 w-full font-cw-mono tabular-nums">
          <thead>
            <tr className="text-left">
              <th className="py-1 font-normal">Month of operation</th>
              <th className="py-1 text-right font-normal">kWh</th>
            </tr>
          </thead>
          <tbody>
            {series.map((p) => (
              <tr key={p.period}>
                <td className="py-1">{p.month_of_operation}</td>
                <td className="py-1 text-right">{WHOLE.format(p.kwh)}</td>
              </tr>
            ))}
            {forecast && (
              <tr>
                <td className="py-1">{forecast.month_of_operation} (forecast)</td>
                <td className="py-1 text-right">
                  {WHOLE.format(forecast.band.p10_kwh)} to {WHOLE.format(forecast.band.p90_kwh)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </details>
    </div>
  );
}

function Key({
  shape,
  label,
  copper,
}: {
  shape: "circle" | "diamond" | "square" | "triangle";
  label: string;
  copper?: boolean;
}) {
  const fill = copper
    ? "fill-cw-accent"
    : shape === "circle"
      ? "fill-cw-text"
      : shape === "square"
        ? "fill-cw-slate"
        : "fill-cw-muted";
  return (
    <li className="flex items-center gap-2.5">
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        {shape === "circle" && <circle cx="9" cy="9" r="6" className={fill} />}
        {shape === "diamond" && <path d="M9,1 L17,9 L9,17 L1,9 Z" className={fill} />}
        {shape === "square" && <rect x="3" y="3" width="12" height="12" className={fill} />}
        {shape === "triangle" && <path d="M9,2 L16,15 H2 Z" className={fill} />}
      </svg>
      {label}
    </li>
  );
}
