import {
  linearScale,
  numberLabel,
  rowValue,
  valueDomain,
  type ChartAnnotation,
  type ChartReference,
  type ChartRow,
  type ChartType,
} from "./model";

function Marker({ x, y, index }: { x: number; y: number; index: number }) {
  return index % 3 === 0 ? (
    <circle cx={x} cy={y} r={5} />
  ) : index % 3 === 1 ? (
    <rect x={x - 5} y={y - 5} width={10} height={10} />
  ) : (
    <path d={`M${x},${y - 6} l6,12 h-12 Z`} />
  );
}
export function Plot({
  rows,
  type,
  summary,
  annotations = [],
  reference,
  domain = valueDomain(
    reference ? [...rows, { ...rows[0]!, value: reference.value, status: "observed" }] : rows,
  ),
}: {
  rows: readonly ChartRow[];
  type: ChartType;
  summary: string;
  annotations?: readonly ChartAnnotation[];
  reference?: ChartReference;
  domain?: [number, number];
}) {
  const series = [...new Set(rows.map((row) => row.series))];
  if (!rows.length) return <p role="status">No data matches this selection.</p>;
  if (type === "small-multiples")
    return (
      <div className="analytics-multiples">
        {series.map((name) => (
          <section key={name}>
            <h3>{name}</h3>
            <Plot
              rows={rows.filter((row) => row.series === name)}
              type="line"
              summary={`${name}. ${summary}`}
              domain={domain}
              annotations={annotations}
              reference={reference}
            />
          </section>
        ))}
      </div>
    );
  const labels = [...new Set(rows.map((row) => row.label))];
  const horizontal = type === "horizontal-bar";
  const width = 720,
    height = Math.max(320, horizontal ? rows.length * 48 + 70 : 320);
  const left = horizontal ? 170 : 80,
    right = 690,
    top = 24,
    bottom = height - 72;
  const scale = linearScale(
    domain[0],
    domain[1],
    horizontal ? left : bottom,
    horizontal ? right : top,
  );
  const category = (label: string) =>
    left + ((labels.indexOf(label) + 0.5) / labels.length) * (right - left);
  const ticks = Array.from(
    { length: 5 },
    (_, index) => domain[0] + ((domain[1] - domain[0]) * index) / 4,
  );
  return (
    <>
      <div
        className="analytics-plot-scroll"
        role="region"
        aria-label={`Chart graphic: ${summary}`}
        tabIndex={0}
      >
        <svg
          className="analytics-plot"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={summary}
        >
          <title>{summary}</title>
          <desc>
            {rows.map((row) => `${row.series}, ${row.label}: ${rowValue(row)}`).join("; ")}
          </desc>
          {ticks.map((tick) => (
            <g key={tick} className="analytics-axis">
              {horizontal ? (
                <>
                  <line x1={scale(tick)} x2={scale(tick)} y1={top} y2={bottom} />
                  <text x={scale(tick)} y={bottom + 28} textAnchor="middle">
                    {numberLabel(tick)}
                  </text>
                </>
              ) : (
                <>
                  <line x1={left} x2={right} y1={scale(tick)} y2={scale(tick)} />
                  <text x={left - 10} y={scale(tick) + 5} textAnchor="end">
                    {numberLabel(tick)}
                  </text>
                </>
              )}
            </g>
          ))}
          {!horizontal &&
            labels.map((label) => (
              <text
                className="analytics-axis-label"
                key={label}
                x={category(label)}
                y={bottom + 28}
                textAnchor="middle"
              >
                {label.length > 14 ? label.slice(0, 12) + "…" : label}
                <title>{label}</title>
              </text>
            ))}
          {reference && (
            <g className="analytics-reference">
              <title>{`${reference.label}: ${numberLabel(reference.value)}`}</title>
              {horizontal ? (
                <line
                  x1={scale(reference.value)}
                  x2={scale(reference.value)}
                  y1={top}
                  y2={bottom}
                  strokeDasharray="8 4"
                />
              ) : (
                <line
                  x1={left}
                  x2={right}
                  y1={scale(reference.value)}
                  y2={scale(reference.value)}
                  strokeDasharray="8 4"
                />
              )}
            </g>
          )}
          {!horizontal &&
            type === "line" &&
            annotations
              .filter((m) => labels.includes(m.date.slice(0, 7)))
              .map((m, i) => (
                <g key={i} className="analytics-axis">
                  <title>{`${m.date}: ${m.label}. Dates are context, not evidence of causation.`}</title>
                  <line
                    x1={category(m.date.slice(0, 7))}
                    x2={category(m.date.slice(0, 7))}
                    y1={top}
                    y2={bottom}
                    strokeDasharray="3 5"
                  />
                </g>
              ))}
          {series.map((name, seriesIndex) => {
            const group = rows.filter((row) => row.series === name);
            // Separate paths at every null so missing observations never become zero or an interpolated line.
            const segments: ChartRow[][] = [[]];
            group.forEach((row) =>
              row.value == null ? segments.push([]) : segments[segments.length - 1]!.push(row),
            );
            return (
              <g key={name} className={`analytics-series analytics-series-${seriesIndex % 3}`}>
                {type === "line" &&
                  segments
                    .filter((segment) => segment.length > 1)
                    .map((segment, index) => (
                      <g key={index}>
                        {segment.every((row) => row.status === "estimate") && (
                          <path
                            className="analytics-range-band"
                            d={`M${segment.map((row) => `${category(row.label)},${scale(row.p90!)}`).join(" L")} L${[
                              ...segment,
                            ]
                              .reverse()
                              .map((row) => `${category(row.label)},${scale(row.p10!)}`)
                              .join(" L")} Z`}
                          />
                        )}
                        <path
                          fill="none"
                          strokeDasharray={
                            seriesIndex % 3 === 1
                              ? "8 5"
                              : seriesIndex % 3 === 2
                                ? "2 5"
                                : undefined
                          }
                          d={`M${segment.map((row) => `${category(row.label)},${scale(row.value!)}`).join(" L")}`}
                        />
                      </g>
                    ))}
                {group.map((row, index) => {
                  const rowIndex = rows.indexOf(row);
                  const x =
                    category(row.label) +
                    (type === "bar" || type === "range"
                      ? (seriesIndex - (series.length - 1) / 2) *
                        Math.min(18, ((right - left) / labels.length / series.length) * 0.6)
                      : 0);
                  const y = top + ((rowIndex + 0.5) / rows.length) * (bottom - top);
                  if (row.value == null)
                    return (
                      <g key={index} className="analytics-gap">
                        <text
                          x={horizontal ? left + 10 : x}
                          y={horizontal ? y : bottom - 12}
                          textAnchor={horizontal ? "start" : "middle"}
                        >
                          No data<title>{`${row.label}: Not enough data yet`}</title>
                        </text>
                        {horizontal && (
                          <text x={left - 12} y={y} textAnchor="end">
                            {row.label.length > 14 ? `${row.label.slice(0, 12)}…` : row.label}
                            <title>{row.label}</title>
                          </text>
                        )}
                      </g>
                    );
                  return (
                    <g key={index}>
                      <title>{`${row.series}, ${row.label}: ${rowValue(row)}`}</title>
                      {horizontal ? (
                        <>
                          <text
                            className="analytics-axis-label"
                            x={left - 12}
                            y={y + 5}
                            textAnchor="end"
                          >
                            {row.label.length > 14 ? `${row.label.slice(0, 12)}…` : row.label}
                            <title>{row.label}</title>
                          </text>
                          <rect
                            x={Math.min(scale(0), scale(row.value))}
                            y={y - 10}
                            width={Math.abs(scale(row.value) - scale(0))}
                            height={20}
                          />
                        </>
                      ) : type === "bar" ? (
                        <rect
                          x={x - 7}
                          y={Math.min(scale(0), scale(row.value))}
                          width={14}
                          height={Math.abs(scale(row.value) - scale(0))}
                        />
                      ) : (
                        <Marker x={x} y={scale(row.value)} index={seriesIndex} />
                      )}
                      {row.status === "estimate" &&
                        (horizontal ? (
                          <g className="analytics-whisker">
                            <line x1={scale(row.p10!)} x2={scale(row.p90!)} y1={y} y2={y} />
                            <line x1={scale(row.p10!)} x2={scale(row.p10!)} y1={y - 6} y2={y + 6} />
                            <line x1={scale(row.p90!)} x2={scale(row.p90!)} y1={y - 6} y2={y + 6} />
                          </g>
                        ) : (
                          <g className="analytics-whisker">
                            <line x1={x} x2={x} y1={scale(row.p10!)} y2={scale(row.p90!)} />
                            <line x1={x - 6} x2={x + 6} y1={scale(row.p10!)} y2={scale(row.p10!)} />
                            <line x1={x - 6} x2={x + 6} y1={scale(row.p90!)} y2={scale(row.p90!)} />
                          </g>
                        ))}
                      {(horizontal || type === "bar") && (
                        <Marker
                          x={horizontal ? scale(row.value) : x}
                          y={horizontal ? y : scale(row.value)}
                          index={seriesIndex}
                        />
                      )}
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>
      <ul className="analytics-chart-legend" aria-label="Series legend">
        {reference && (
          <li>
            <svg
              className="analytics-reference"
              width="24"
              height="12"
              viewBox="0 0 24 12"
              aria-hidden="true"
            >
              <line x1="0" x2="24" y1="6" y2="6" strokeDasharray="8 4" />
            </svg>{" "}
            Reference: {reference.label}, {numberLabel(reference.value)}
          </li>
        )}
        {series.map((name, index) => (
          <li key={name}>
            <span className={`analytics-series-key analytics-series-${index % 3}`}>
              {["●", "■", "▲"][index % 3]}
            </span>{" "}
            {name}
          </li>
        ))}
      </ul>
      {rows.some((row) => row.value == null) && (
        <p>Gaps: Not enough data yet. Missing and suppressed observations are never zero.</p>
      )}
    </>
  );
}
