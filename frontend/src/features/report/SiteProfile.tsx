import { formatKw } from "../../lib/units";
import { kw } from "../../lib/units";
import type { ReportPayload } from "./payload";

/**
 * Section 3 — archetype, road and access, demand in the district, and the
 * competitor picture. Facts carry their source inline; anything manual or
 * pending gets the single warn accent, same rule as the ledger.
 *
 * The sketch is a hand-drawn SVG schematic, not a map tile: the public report
 * carries no mapping library (routes.tsx), and a schematic states only what
 * we actually know — the road, the pin, and measured competitor distances.
 */
export function SiteProfile({ payload }: { payload: ReportPayload }) {
  const { site, site_facts, competitors } = payload;
  return (
    <section data-report-section="profile" className="border-b border-rule py-8">
      <h2 className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
        3 · Site profile
      </h2>
      <p className="mt-2 text-[1.125rem] leading-tight">
        {site.name} — <span className="text-ink-muted">{site.line}</span>
      </p>
      <p className="num mt-1 text-[13px] text-ink-faint">
        {site.lat.toFixed(3)}, {site.lng.toFixed(3)} · LGD {site.lgd_district_code} · archetype{" "}
        {site.archetype} · tier {site.data_tier}
      </p>

      <div className="mt-6 grid gap-8 md:grid-cols-[1fr_1fr]">
        <dl className="self-start border-t border-rule">
          {site_facts.map((f) => (
            <div key={f.label} className="flex justify-between gap-4 border-b border-rule py-1.5">
              <dt className="font-ui text-[13px] text-ink-muted">{f.label}</dt>
              <dd className="text-right">
                <span className="num block text-[13px]">{f.value}</span>
                <span
                  className={
                    f.unverified
                      ? "bg-warn-ground px-1 font-data text-[11px] text-warn"
                      : "font-data text-[11px] text-ink-faint"
                  }
                >
                  {f.source}
                </span>
              </dd>
            </div>
          ))}
        </dl>

        <figure>
          <svg
            viewBox="0 0 340 220"
            role="img"
            aria-label="Schematic of the site: NH-66 divided carriageway, the candidate pin, and the nearest competing stations with distances"
            className="w-full border border-rule bg-ground-sunk"
          >
            {/* NH-66, divided */}
            <line x1="-10" y1="176" x2="350" y2="64" className="stroke-ink-muted" strokeWidth="7" />
            <line
              x1="-10"
              y1="176"
              x2="350"
              y2="64"
              className="stroke-ground-sunk"
              strokeWidth="1.5"
              strokeDasharray="7 6"
            />
            <text x="14" y="158" className="fill-ink-muted font-data text-[10px]">
              NH-66
            </text>

            {/* candidate site */}
            <line x1="170" y1="118" x2="170" y2="94" className="stroke-ink" strokeWidth="1.5" />
            <circle cx="170" cy="88" r="5" className="fill-ink" />
            <text x="180" y="92" className="fill-ink font-data text-[10px] font-bold">
              site
            </text>

            {/* nearest competitors, radial from the site, distance to scale (~28px/km) */}
            {payload.competitors.nearest.slice(0, 4).map((c, i) => {
              const angle = [-2.4, -0.7, 0.55, 2.0][i] ?? 0;
              const r = 12 + (c.distance_m / 1000) * 28;
              const cx = 170 + Math.cos(angle) * r;
              const cy = 88 + Math.sin(angle) * r * 0.9;
              return (
                <g key={c.name}>
                  <circle cx={cx} cy={cy} r="3.5" className="fill-ink-faint" />
                  <text x={cx + 6} y={cy + 3} className="fill-ink-muted font-data text-[9px]">
                    {(c.distance_m / 1000).toFixed(1)} km · {formatKw(kw(c.max_power_kw))}
                  </text>
                </g>
              );
            })}
          </svg>
          <figcaption className="mt-1 font-data text-[11px] text-ink-faint">
            schematic — distances measured, geometry indicative
          </figcaption>
        </figure>
      </div>

      <h3 className="mt-8 font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
        Competing stations · {competitors.within_3km} within 3 km, nearest listed
      </h3>
      <div className="overflow-x-auto">
        <table className="mt-2 w-full min-w-[34rem] border-t border-rule text-[13px]">
          <thead>
            <tr className="border-b border-rule text-left font-ui text-[11px] tracking-[0.08em] text-ink-muted uppercase">
              <th className="py-1.5 pr-4 font-bold">Station</th>
              <th className="py-1.5 pr-4 font-bold">Operator</th>
              <th className="py-1.5 pr-4 text-right font-bold">Distance</th>
              <th className="py-1.5 pr-4 text-right font-bold">Max power</th>
              <th className="py-1.5 text-right font-bold">Points</th>
            </tr>
          </thead>
          <tbody>
            {competitors.nearest.map((c) => (
              <tr key={c.name} className="border-b border-rule">
                <td className="py-1.5 pr-4 font-text">{c.name}</td>
                <td className="py-1.5 pr-4">{c.operator}</td>
                <td className="py-1.5 pr-4 text-right">{c.distance_m} m</td>
                <td className="py-1.5 pr-4 text-right">{formatKw(kw(c.max_power_kw))}</td>
                <td className="py-1.5 text-right">{c.points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-1.5 font-data text-[11px] text-ink-faint">
        {competitors.source} · inventory and specs, not occupancy — observed occupancy joins when
        the poller runs
      </p>
    </section>
  );
}
