import { COVERAGE, GROUPS, SITE_LABEL, TOTAL_CHECKS, VERDICT, illustrative } from "./data";
import { useLoopClock } from "./useLoopClock";

/**
 * B - The site, assessed. For the "What a full assessment checks" section.
 *
 * A site plan on the left, the 34 checks on the right, walked one category
 * at a time: road access, demand, grid, plot, market - then the coverage
 * count, the utilisation band against breakeven, and the verdict LAST.
 *
 * The last beat is not negotiable for visual punch. The report leads with
 * its verdict; this is the assessment, and an assessment that announced its
 * answer first would be describing a different product.
 *
 * ONE thing here was deliberately thrown away. A reference build flickered
 * every value through four random alternatives before "settling" on the
 * real one - the slot-machine idiom for computation. Under a headline
 * reading "Nothing here is assumed", that animates the system guessing, and
 * a viewer who watches for six seconds learns the numbers are arbitrary.
 * Rows here arrive already correct, staggered, the way flow/Working.tsx
 * paces the same 34 factors. The motion is arrival, never a dice roll.
 *
 * Copper falls on exactly one row - Grid outage hours, unverified - which
 * is the accent's reserved meaning and the whole argument of the product.
 * The verdict is --cw-positive, semantic, so DON'T BUILD renders in the
 * same composition without contradiction.
 */

/** intro, then one step per category, then the summary. */
const DURATIONS = [900, 2300, 2000, 2400, 1900, 1700, 4200] as const;
const FIRST_GROUP = 1;
const SUMMARY = DURATIONS.length - 1;

/**
 * `headless` drops the eyebrow, heading and intro paragraph.
 *
 * Landing.tsx's WhatWeCheck already says "Nothing here is a guess" over
 * "Each one is measured or sourced, and the unverified ones are marked, not
 * buried" - which is this component's own header, in different words. Two
 * of them stacked would read as a stutter, so the section keeps its copy
 * and this keeps the plan, the category strip and the ledger.
 */
export function SiteAssessed({ headless = false }: { headless?: boolean } = {}) {
  const [ref, step] = useLoopClock<HTMLDivElement>(DURATIONS);
  const groupIndex = step - FIRST_GROUP;
  /* Undefined on the intro and summary steps, which is the point - those two
     have no category, and the panel below renders something else entirely. */
  const group = GROUPS[groupIndex];
  const stage = step === 0 ? "intro" : step === SUMMARY ? "summary" : (group?.key ?? "intro");

  return (
    <div
      ref={ref}
      data-stage={stage}
      className="cwa-assess grid items-start gap-[clamp(28px,4vw,64px)]"
      style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 340px), 1fr))" }}
    >
      <SitePlan />

      <div className="flex min-w-0 flex-col">
        {!headless && (
          <>
            <div className="font-cw-mono text-[13px] tracking-[0.16em] text-cw-muted uppercase">
              {TOTAL_CHECKS} assessment checks · {SITE_LABEL}
            </div>
            <h3 className="mt-3.5 text-[clamp(24px,3vw,32px)] leading-[1.15] font-medium">
              Nothing here is assumed.
            </h3>
            <p className="mt-3 text-cw-muted">
              Every factor is measured or sourced. Anything we could not verify is marked, never
              quietly filled in.
            </p>
          </>
        )}

        {/* Five categories, and how far through them the assessment is. */}
        <ol
          className={`grid grid-cols-5 gap-px border border-cw-line bg-cw-line ${
            headless ? "" : "mt-7"
          }`}
        >
          {GROUPS.map((g, i) => (
            <li
              key={g.key}
              data-state={
                step === SUMMARY || i < groupIndex
                  ? "done"
                  : i === groupIndex
                    ? "active"
                    : "waiting"
              }
              className="cwa-cat bg-cw-ground px-2 py-2.5 text-center"
            >
              <div className="font-cw-mono text-[15px] leading-none font-medium tabular-nums">
                {String(g.checks.length).padStart(2, "0")}
              </div>
              <div className="mt-1.5 font-cw-mono text-[10px] tracking-[0.12em] uppercase">
                {g.short}
              </div>
            </li>
          ))}
        </ol>

        {/* Fixed height: the panel must not resize the page as it cycles. */}
        <div className="relative mt-6 min-h-[330px]">
          {step === 0 && (
            <p className="cwa-fade font-cw-mono text-[13px] tracking-[0.14em] text-cw-muted uppercase">
              Connecting sources…
            </p>
          )}

          {group && step > 0 && step < SUMMARY && (
            /* Keyed on the category so React remounts the list and the CSS
               stagger replays for each panel without a JS timeline. */
            <div key={group.key}>
              <div className="flex items-baseline justify-between gap-4 border-b border-cw-line pb-2 font-cw-mono text-[11px] tracking-[0.14em] text-cw-muted uppercase">
                <span>{group.name}</span>
                <span className="tabular-nums">
                  {String(group.checks.length).padStart(2, "0")} checks
                </span>
              </div>
              <dl className="m-0">
                {group.checks.map((c, i) => (
                  <div
                    key={c.label}
                    className="cwa-check flex items-baseline gap-3.5 border-b border-cw-line py-[9px]"
                    style={{ animationDelay: `${i * 70}ms` }}
                  >
                    <dt className="min-w-0 flex-auto text-[15px]">{c.label}</dt>
                    <dd
                      className={`m-0 font-cw-mono text-[14px] whitespace-nowrap tabular-nums ${
                        c.unverified ? "text-cw-accent" : "text-cw-muted"
                      }`}
                    >
                      {c.unverified ? c.value : illustrative(c.value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {step === SUMMARY && <Summary />}
        </div>
      </div>
    </div>
  );
}

function Summary() {
  return (
    <div className="cwa-fade">
      <div className="flex items-baseline justify-between gap-4 border-b border-cw-line pb-2 font-cw-mono text-[11px] tracking-[0.14em] text-cw-muted uppercase">
        <span>Assessment complete</span>
        <span className="tabular-nums">
          {TOTAL_CHECKS} / {TOTAL_CHECKS}
        </span>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-px border border-cw-line bg-cw-line">
        {COVERAGE.map((c) => (
          <div key={c.label} className="bg-cw-ground px-3 py-3.5">
            <div
              className={`font-cw-mono text-[26px] leading-none font-medium tabular-nums ${
                "unverified" in c && c.unverified ? "text-cw-accent" : "text-cw-text"
              }`}
            >
              {String(c.count).padStart(2, "0")}
            </div>
            <div className="mt-2 font-cw-mono text-[10px] tracking-[0.12em] text-cw-muted uppercase">
              {c.label}
            </div>
          </div>
        ))}
      </div>

      {/* A range against a threshold, never a single number - the report
          makes the same shape in Statistical.tsx. */}
      <div className="mt-7">
        <div className="font-cw-mono text-[11px] tracking-[0.14em] text-cw-muted uppercase">
          12-month utilisation, against breakeven
        </div>
        <div className="relative mt-3 h-2.5 border border-cw-line bg-cw-surface-2">
          <div className="cwa-band absolute top-0 bottom-0 left-[38%] bg-cw-slate" />
          <div className="cwa-threshold absolute top-[-5px] bottom-[-5px] left-[52%] w-0.5 bg-cw-text" />
        </div>
        <div className="mt-2.5 flex justify-between gap-3 font-cw-mono text-[11px] tracking-[0.06em] text-cw-muted tabular-nums">
          <span>P10 {illustrative(VERDICT.p10)}</span>
          <span>Breakeven {illustrative(VERDICT.breakeven)}</span>
          <span>P90 {illustrative(VERDICT.p90)}</span>
        </div>
      </div>

      <div className="cwa-verdict mt-6 border-t-2 border-cw-line pt-[18px]">
        <div className="font-cw-mono text-[clamp(22px,3vw,30px)] leading-[1.15] font-medium tracking-[0.04em] text-cw-positive uppercase">
          {VERDICT.word}
        </div>
        <p className="mt-1.5 text-cw-muted">{VERDICT.copy}</p>
      </div>
    </div>
  );
}

/**
 * The parcel, drawn as a survey plan. Each layer lifts as its category is
 * read - the drawing and the ledger are the same assessment, not a picture
 * beside a list.
 */
function SitePlan() {
  return (
    <svg
      className="block h-auto w-full max-w-[520px]"
      viewBox="0 0 480 520"
      role="img"
      aria-label="A candidate parcel: highway frontage and entry, traffic direction, an off-site transformer connection, charging bays under a canopy, and competitor rings at three, five and ten kilometres."
    >
      <defs>
        <pattern id="cwaPlanGrid" width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M24 0H0V24" fill="none" stroke="var(--cw-line)" strokeWidth="1" opacity="0.55" />
        </pattern>
        <linearGradient id="cwaSurveyTrail" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--cw-accent)" stopOpacity="0" />
          <stop offset="100%" stopColor="var(--cw-accent)" stopOpacity="0.12" />
        </linearGradient>
        <clipPath id="cwaParcelClip">
          <path d="M70 60 L388 42 L432 178 L400 420 L126 444 L54 310 Z" />
        </clipPath>
        {/* The sheet edge. Everything is clipped to it, so the highway can
            run off the plan the way it does on a real drawing. */}
        <clipPath id="cwaPlanFrame">
          <rect x="24" y="22" width="432" height="458" />
        </clipPath>
      </defs>

      <rect
        x="24"
        y="22"
        width="432"
        height="458"
        fill="var(--cw-ground)"
        stroke="var(--cw-line)"
      />
      <rect x="24" y="22" width="432" height="458" fill="url(#cwaPlanGrid)" />

      <g clipPath="url(#cwaPlanFrame)">
        <path
          d="M70 60 L388 42 L432 178 L400 420 L126 444 L54 310 Z"
          fill="var(--cw-surface)"
          opacity="0.55"
        />
        {/* The parcel is the frame, not the subject - held back so the layer
            being read is the brightest thing on the plan. */}
        <path
          className="cwa-parcel"
          d="M70 60 L388 42 L432 178 L400 420 L126 444 L54 310 Z"
          fill="none"
          stroke="var(--cw-slate)"
          strokeWidth="1.5"
          opacity="0.5"
        />
        <path
          d="M88 82 L373 66 L408 184 L380 398 L139 420 L78 300 Z"
          fill="none"
          stroke="var(--cw-line)"
          strokeWidth="1"
          strokeDasharray="4 5"
        />

        {/* Road access & geometry */}
        <g className="cwa-layer" data-layer="road">
          <path
            d="M-15 471 C95 435 206 468 303 451 C382 437 425 416 500 398"
            fill="none"
            stroke="var(--cw-surface-2)"
            strokeWidth="26"
            strokeLinecap="round"
          />
          <path
            d="M-15 471 C95 435 206 468 303 451 C382 437 425 416 500 398"
            fill="none"
            stroke="var(--cw-slate)"
            strokeWidth="1.25"
            strokeDasharray="9 12"
            opacity="0.7"
          />
          <path
            d="M345 443 C344 407 331 376 306 351 L280 328"
            fill="none"
            stroke="var(--cw-slate)"
            strokeWidth="1.75"
            strokeDasharray="5 4"
          />
          <path d="M274 327 L290 320 L286 337 Z" fill="var(--cw-slate)" />
          <PlanBadge x={316} y={444} w={112} label={`${illustrative("8.2 m")} entry`} />
        </g>

        {/* Demand & mobility */}
        <g className="cwa-layer" data-layer="demand">
          <path d="M74 447 l19 -4 l-10 16z" fill="var(--cw-muted)" />
          <path d="M161 451 l19 -1 l-12 14z" fill="var(--cw-muted)" />
          <PlanBadge x={70} y={380} w={128} label={`AADT ${illustrative("18,400/day")}`} />
        </g>

        {/* Grid, tariff & policy */}
        <g className="cwa-layer" data-layer="grid">
          <rect
            x="17"
            y="92"
            width="47"
            height="54"
            rx="4"
            fill="var(--cw-surface-2)"
            stroke="var(--cw-line)"
          />
          <text
            x="40.5"
            y="124"
            textAnchor="middle"
            fontFamily="var(--cw-mono)"
            fontSize="13"
            fill="var(--cw-muted)"
          >
            TX
          </text>
          <path
            d="M64 119 H102 V174 H146 V208"
            fill="none"
            stroke="var(--cw-slate)"
            strokeWidth="1.5"
          />
          <rect
            x="132"
            y="194"
            width="29"
            height="34"
            rx="3"
            fill="var(--cw-surface-2)"
            stroke="var(--cw-line)"
          />
          <PlanBadge x={70} y={146} w={92} label={`${illustrative("140 m")} to grid`} />
        </g>

        {/* Plot readiness */}
        <g className="cwa-layer" data-layer="plot">
          <rect
            x="126"
            y="196"
            width="294"
            height="158"
            rx="5"
            fill="var(--cw-surface)"
            stroke="var(--cw-line)"
          />
          {[133, 201, 286, 354].map((x, i) => (
            <rect
              key={x}
              x={x}
              y="218"
              width={i === 3 ? 59 : 65}
              height="118"
              rx="3"
              fill="none"
              stroke="var(--cw-line)"
              strokeWidth="1.25"
            />
          ))}
          {[199, 352].map((x) => (
            <g key={x} transform={`translate(${x} 206)`}>
              <rect
                x="-15"
                y="-12"
                width="30"
                height="24"
                rx="4"
                fill="var(--cw-surface-2)"
                stroke="var(--cw-line)"
              />
              <rect x="-8" y="-9" width="16" height="18" rx="3" fill="var(--cw-ground)" />
              <path d="M2 -6 L-4 1 H0 L-2 6 L5 -2 H2Z" fill="var(--cw-slate)" />
            </g>
          ))}
          <text
            x="273"
            y="374"
            textAnchor="middle"
            fontFamily="var(--cw-mono)"
            fontSize="10.5"
            letterSpacing="1.2"
            fill="var(--cw-muted)"
          >
            {illustrative("2 × 30 kW DC · 4 connectors")}
          </text>
        </g>

        {/* Commercial landscape */}
        <g className="cwa-layer" data-layer="commercial" transform="translate(344 112)">
          <circle r="23" fill="none" stroke="var(--cw-line)" strokeWidth="1.25" />
          <circle r="41" fill="none" stroke="var(--cw-line)" strokeWidth="1.25" />
          <circle r="57" fill="none" stroke="var(--cw-line)" strokeWidth="1.25" />
          <circle r="4" fill="var(--cw-accent)" />
          <circle cx="-12" cy="-31" r="3" fill="var(--cw-muted)" />
          <circle cx="35" cy="19" r="3" fill="var(--cw-muted)" />
          <circle cx="-44" cy="30" r="3" fill="var(--cw-muted)" />
          <text
            x="0"
            y="-66"
            textAnchor="middle"
            fontFamily="var(--cw-mono)"
            fontSize="10.5"
            letterSpacing="1.2"
            fill="var(--cw-muted)"
          >
            3 / 5 / 10 km
          </text>
        </g>

        {/* The survey sweep - the assessment happening, clipped to the parcel
          so it reads as a scan of THIS plot, not a sci-fi flourish. */}
        <g clipPath="url(#cwaParcelClip)">
          <g className="cwa-survey">
            <rect x="40" y="-32" width="410" height="32" fill="url(#cwaSurveyTrail)" />
            <rect x="40" y="0" width="410" height="1.5" fill="var(--cw-accent)" opacity="0.55" />
          </g>
        </g>
      </g>
    </svg>
  );
}

function PlanBadge({ x, y, w, label }: { x: number; y: number; w: number; label: string }) {
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height="22"
        rx="2"
        fill="var(--cw-ground)"
        stroke="var(--cw-line)"
      />
      <text
        x={x + w / 2}
        y={y + 15}
        textAnchor="middle"
        fontFamily="var(--cw-mono)"
        fontSize="10.5"
        letterSpacing="0.8"
        fill="var(--cw-muted)"
      >
        {label}
      </text>
    </g>
  );
}

export default SiteAssessed;
