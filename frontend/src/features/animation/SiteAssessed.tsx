import { COVERAGE, GROUPS, SITE_LABEL, TOTAL_CHECKS, VERDICT, illustrative } from "./data";
import { useLoopClock } from "./useLoopClock";

/**
 * B - The site, assessed. For the "What a full assessment checks" section.
 *
 * Ported from Designv3/candidate-site-assessment.html: the framed sheet with
 * its corner brackets, the survey plan with layers that lift as their
 * category is read, the category strip, the two-column ledger, the coverage
 * counts, the utilisation band against breakeven, and the verdict LAST.
 *
 * The last beat is not negotiable. The report leads with its verdict; this
 * is the assessment, and an assessment that announced its answer first would
 * be describing a different product.
 *
 * ONE thing in the reference was deliberately thrown away. It flickered every
 * value through four random alternatives before "settling" on the real one -
 * the slot-machine idiom for computation. Under a headline reading "Nothing
 * here is assumed", that animates the system guessing, and a viewer who
 * watches for six seconds learns the numbers are arbitrary. Rows here arrive
 * already correct, staggered, the way flow/Working.tsx paces the same 34
 * factors. The motion is arrival, never a dice roll.
 *
 * Copper falls on exactly one row - Grid outage hours, unverified - which is
 * the accent's reserved meaning and the whole argument of the product. The
 * verdict is --cw-positive, semantic, so DON'T BUILD renders in the same
 * composition without contradiction.
 */

/** intro, then one step per category, then the summary. */
const DURATIONS = [900, 3000, 1600, 2400, 2200, 1500, 4200] as const;
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
  const status =
    step === 0
      ? "Connecting sources"
      : step === SUMMARY
        ? "Assessment complete"
        : `Reading ${group?.source ?? ""}`;

  return (
    <div
      ref={ref}
      data-stage={stage}
      className="cwa-assess cwa-frame relative grid items-center gap-[clamp(28px,4vw,64px)] p-[clamp(22px,3.4vw,56px)]"
      style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 340px), 1fr))" }}
    >
      <div className="relative min-w-0">
        {/* What is being read, in words. It is the one thing a viewer cannot
            get from the drawing, and it names a source rather than a
            result - the same string flow/Working.tsx shows a customer. */}
        <div
          key={status}
          className="cwa-tag absolute top-0 left-0 z-10 max-w-[92%] border border-cw-line bg-cw-ground/90 px-2.5 py-2 font-cw-mono text-[10px] tracking-[0.1em] text-cw-muted uppercase"
        >
          <span className="text-cw-slate">{status}</span> · {SITE_LABEL}
        </div>
        <SitePlan />
      </div>

      <div className="flex min-w-0 flex-col">
        {!headless && (
          <>
            <div className="font-cw-mono text-[13px] tracking-[0.16em] text-cw-muted uppercase">
              {TOTAL_CHECKS} assessment checks
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
        <ol className={`grid grid-cols-5 gap-1.5 ${headless ? "" : "mt-7"}`}>
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
              className="cwa-cat min-w-0 bg-cw-surface/70 px-2 py-2.5"
            >
              <div className="font-cw-mono text-[13px] leading-none text-cw-muted tabular-nums">
                {String(g.checks.length).padStart(2, "0")}
              </div>
              <div className="mt-1.5 truncate font-cw-mono text-[clamp(8px,0.78vw,10px)] tracking-[0.08em] text-cw-muted uppercase">
                {g.short}
              </div>
            </li>
          ))}
        </ol>

        {/* Fixed height: the panel must not resize the page as it cycles.
            Two columns above the reference's own breakpoint, one below -
            and the reserved height changes with it, because twelve checks
            stacked are twice as tall as twelve checks paired. */}
        <div className="relative mt-6 min-h-[560px] border-y border-cw-line py-3.5 min-[900px]:min-h-[320px]">
          {step === 0 && (
            /* Centred, with the reference's pulsing rule under it. Left
               aligned at the top of a 320px panel this read as a rendering
               fault rather than a beat. */
            <div className="cwa-fade absolute inset-0 grid place-items-center text-center">
              <div>
                <p className="m-0 font-cw-mono text-[12px] tracking-[0.14em] text-cw-muted uppercase">
                  Connecting verified data sources
                </p>
                <span className="cwa-initialise mx-auto mt-4 block h-0.5 w-40" />
              </div>
            </div>
          )}

          {group && step > 0 && step < SUMMARY && (
            /* Keyed on the category so React remounts the list and the CSS
               stagger replays for each panel without a JS timeline. */
            <div key={group.key}>
              <div className="mb-2.5 flex items-baseline justify-between gap-4 font-cw-mono text-[11px] font-semibold tracking-[0.12em] text-cw-slate uppercase">
                <span className="min-w-0 truncate">{group.name}</span>
                <span className="shrink-0 font-normal text-cw-muted tabular-nums">
                  {String(group.checks.length).padStart(2, "0")} checks
                </span>
              </div>
              <dl className="m-0 grid grid-cols-1 gap-x-[18px] min-[900px]:grid-cols-2">
                {group.checks.map((c, i) => (
                  <div
                    key={c.label}
                    className="cwa-check grid min-h-[43px] grid-cols-[minmax(0,1fr)_auto] items-center gap-2.5 border-t border-cw-line"
                    style={{ animationDelay: `${i * 42}ms` }}
                  >
                    {/* The reference shortened its labels ("Carriageway
                        direction") so they could truncate. These are
                        Landing.tsx's FACTORS verbatim and must stay that
                        way, so the long ones wrap instead - the grid keeps
                        both columns' rules aligned either way. */}
                    <dt className="text-[clamp(12px,1vw,14px)] leading-tight text-cw-muted">
                      {c.label}
                    </dt>
                    <dd
                      className={`m-0 font-cw-mono text-[clamp(11px,0.95vw,13px)] whitespace-nowrap tabular-nums ${
                        c.unverified ? "text-cw-accent" : "text-cw-text"
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

        <p className="mt-4 font-cw-mono text-[10px] tracking-[0.1em] text-cw-muted uppercase">
          Illustrative assessment · replace with live project data
        </p>
      </div>
    </div>
  );
}

function Summary() {
  return (
    <div className="cwa-fade">
      <div className="mb-2.5 flex items-baseline justify-between gap-4 font-cw-mono text-[11px] font-semibold tracking-[0.12em] text-cw-slate uppercase">
        <span>Assessment complete</span>
        <span className="font-normal text-cw-muted tabular-nums">
          {TOTAL_CHECKS} / {TOTAL_CHECKS} checks
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {COVERAGE.map((c) => (
          <div key={c.label} className="border border-cw-line bg-cw-surface px-2.5 py-3">
            <div
              className={`font-cw-mono text-[22px] leading-none font-medium tabular-nums ${
                "unverified" in c && c.unverified ? "text-cw-accent" : "text-cw-text"
              }`}
            >
              {String(c.count).padStart(2, "0")}
            </div>
            <div
              className={`mt-1.5 font-cw-mono text-[9px] tracking-[0.1em] uppercase ${
                "unverified" in c && c.unverified ? "text-cw-accent" : "text-cw-muted"
              }`}
            >
              {c.label}
            </div>
          </div>
        ))}
      </div>

      {/* A range against a threshold, never a single number - the report
          makes the same shape in Statistical.tsx. */}
      <div className="mt-5">
        <div className="flex justify-between gap-4 font-cw-mono text-[10px] tracking-[0.09em] text-cw-muted uppercase">
          <span>12-month utilisation</span>
          <span>Forecast range</span>
        </div>
        <div className="relative mt-2.5 h-4 border border-cw-line bg-cw-surface">
          <div className="cwa-band absolute top-[3px] bottom-[3px] left-[19%] bg-cw-slate" />
          <div className="cwa-threshold absolute top-[-7px] bottom-[-7px] left-[47%] w-0.5 bg-cw-text" />
        </div>
        <div className="mt-[7px] grid grid-cols-3 font-cw-mono text-[10px] text-cw-muted tabular-nums">
          <span>P10 · {illustrative(VERDICT.p10)}</span>
          <span className="text-center text-cw-text">
            Breakeven · {illustrative(VERDICT.breakeven)}
          </span>
          <span className="text-right">P90 · {illustrative(VERDICT.p90)}</span>
        </div>
      </div>

      <div className="cwa-verdict mt-4 grid grid-cols-1 items-center gap-x-[17px] gap-y-2 border-t-2 border-cw-line pt-[15px] min-[560px]:grid-cols-[auto_1fr]">
        <div className="font-cw-mono text-[clamp(20px,2.7vw,30px)] leading-none font-medium tracking-[0.03em] text-cw-positive uppercase">
          {VERDICT.word}
        </div>
        <p className="m-0 text-[clamp(12px,1.05vw,14px)] leading-snug text-cw-muted">
          {VERDICT.copy}
        </p>
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
      className="mx-auto block h-auto w-full max-w-[520px]"
      viewBox="0 0 480 520"
      role="img"
      aria-label="A candidate parcel: highway frontage and entry, traffic direction, an off-site transformer connection, charging bays under a canopy, and competitor rings at three, five and ten kilometres."
    >
      <defs>
        <pattern id="cwaPlanGrid" width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M24 0H0V24" fill="none" stroke="var(--cw-line)" strokeWidth="1" opacity="0.5" />
        </pattern>
        <linearGradient id="cwaSurveyTrail" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--cw-accent)" stopOpacity="0" />
          <stop offset="100%" stopColor="var(--cw-accent)" stopOpacity="0.16" />
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
          fill="var(--cw-slate)"
          opacity="0.07"
        />
        <path
          className="cwa-parcel"
          pathLength="1"
          d="M70 60 L388 42 L432 178 L400 420 L126 444 L54 310 Z"
          fill="none"
          stroke="var(--cw-slate)"
          strokeWidth="2"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        <path
          d="M88 82 L373 66 L408 184 L380 398 L139 420 L78 300 Z"
          fill="none"
          stroke="var(--cw-line)"
          strokeWidth="1"
          strokeDasharray="5 7"
        />

        {/* Access and geometry. The highway is drawn at the reference's
            weight - 48 units across a 480-unit plan - because a frontage
            road that reads as a hairline is not frontage. */}
        <g className="cwa-layer" data-layer="access">
          <path
            d="M-15 471 C95 435 206 468 303 451 C382 437 425 416 500 398"
            fill="none"
            stroke="var(--cw-surface-2)"
            strokeWidth="58"
            strokeLinecap="round"
          />
          <path
            d="M-15 471 C95 435 206 468 303 451 C382 437 425 416 500 398"
            fill="none"
            stroke="var(--cw-line)"
            strokeWidth="48"
            strokeLinecap="round"
          />
          <path
            d="M-15 471 C95 435 206 468 303 451 C382 437 425 416 500 398"
            fill="none"
            stroke="var(--cw-muted)"
            strokeWidth="1.5"
            strokeDasharray="13 14"
            opacity="0.6"
          />
          <path
            d="M345 443 C344 407 331 376 306 351 L280 328"
            fill="none"
            stroke="var(--cw-slate)"
            strokeWidth="9"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path d="M274 327 L289 321 L285 336 Z" fill="var(--cw-slate)" />
          {/* y=450, not the reference's 468: this port clips the layers to
              the sheet edge at y=480 so the highway can run off the drawing,
              and at 468 the clip cut this badge in half. */}
          <PlanBadge x={322} y={450} w={104} label={`${illustrative("8.2 m")} entry`} />

          {/* Traffic count and flow sit in this layer with the source
              grouping: they come off the same OSM road fetch as the
              geometry, so they light with it rather than in their own beat. */}
          <path d="M74 447 l18 -4 l-10 16z" fill="var(--cw-slate)" />
          <path d="M161 451 l18 -1 l-12 14z" fill="var(--cw-slate)" />
          <rect
            x="78"
            y="381"
            width="126"
            height="43"
            rx="3"
            fill="var(--cw-ground)"
            fillOpacity="0.93"
            stroke="var(--cw-slate)"
            strokeOpacity="0.55"
            vectorEffect="non-scaling-stroke"
          />
          <text
            x="91"
            y="398"
            fontFamily="var(--cw-mono)"
            fontSize="10"
            letterSpacing="0.9"
            fill="var(--cw-muted)"
          >
            AADT
          </text>
          <text
            x="91"
            y="416"
            fontFamily="var(--cw-mono)"
            fontSize="12"
            fontWeight="600"
            fill="var(--cw-text)"
          >
            {illustrative("18,400 /day")}
          </text>
        </g>

        {/* Demand is the VAHAN read, which is district-scale - nothing about
            this parcel. It gets the two factors that can be drawn at all:
            the registrations behind it and the city it faces. Placed clear
            of the AADT badge (x 78-204, y 381-424), which belongs to the
            access layer and would otherwise clip these. */}
        <g className="cwa-layer" data-layer="demand">
          <PlanBadge x={216} y={381} w={112} label={`EV ${illustrative("12,540")}`} />
          <PlanBadge x={216} y={407} w={124} label={`city ${illustrative("6.8 km")}`} />
        </g>

        {/* Power and tariff. The transformer is outside the parcel and the
            route to it is what the 140 m badge measures. */}
        <g className="cwa-layer" data-layer="power">
          <rect
            x="17"
            y="92"
            width="47"
            height="54"
            rx="4"
            fill="var(--cw-surface-2)"
            stroke="var(--cw-slate)"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />
          <text
            x="40.5"
            y="113"
            textAnchor="middle"
            fontFamily="var(--cw-mono)"
            fontSize="10"
            letterSpacing="0.9"
            fill="var(--cw-muted)"
          >
            TX
          </text>
          <text
            x="40.5"
            y="133"
            textAnchor="middle"
            fontFamily="var(--cw-mono)"
            fontSize="12"
            fontWeight="600"
            fill="var(--cw-text)"
          >
            180
          </text>
          <path
            d="M64 119 H102 V174 H146 V208"
            fill="none"
            stroke="var(--cw-slate)"
            strokeWidth="2"
            strokeDasharray="7 6"
            vectorEffect="non-scaling-stroke"
          />
          <rect
            x="132"
            y="194"
            width="29"
            height="34"
            rx="3"
            fill="var(--cw-surface-2)"
            stroke="var(--cw-slate)"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />
          <PlanBadge x={74} y={147} w={80} label={`${illustrative("140 m")} grid`} />
        </g>

        {/* Site and amenities. */}
        <g className="cwa-layer" data-layer="site">
          <rect
            x="126"
            y="196"
            width="294"
            height="158"
            rx="6"
            fill="var(--cw-slate)"
            fillOpacity="0.05"
            stroke="var(--cw-slate)"
            strokeWidth="1"
            strokeDasharray="7 6"
            vectorEffect="non-scaling-stroke"
          />
          {[133, 201, 286, 354].map((x, i) => (
            <rect
              key={x}
              x={x}
              y="218"
              width={i === 3 ? 59 : 65}
              height="118"
              rx="4"
              fill="var(--cw-surface-2)"
              fillOpacity="0.78"
              stroke="var(--cw-muted)"
              strokeWidth="1.25"
              vectorEffect="non-scaling-stroke"
            />
          ))}
          <path
            d="M165 218V336 M233 218V336 M318 218V336 M383 218V336"
            stroke="var(--cw-line)"
            strokeWidth="1"
            strokeDasharray="4 5"
            vectorEffect="non-scaling-stroke"
          />
          {/* Two charging islands, each serving a pair of bays. */}
          {[199, 352].map((x) => (
            <g key={x} transform={`translate(${x} 206)`}>
              <rect
                x="-15"
                y="-12"
                width="30"
                height="24"
                rx="5"
                fill="var(--cw-surface-2)"
                stroke="var(--cw-slate)"
                strokeWidth="1.25"
                vectorEffect="non-scaling-stroke"
              />
              <rect
                x="-8"
                y="-9"
                width="16"
                height="18"
                rx="4"
                fill="var(--cw-ground)"
                stroke="var(--cw-slate)"
                strokeWidth="1"
                vectorEffect="non-scaling-stroke"
              />
              <path d="M2 -6 L-4 1 H0 L-2 6 L5 -2 H2Z" fill="var(--cw-slate)" />
              <circle cx="-21" cy="-7" r="3" fill="var(--cw-line)" />
              <circle cx="21" cy="-7" r="3" fill="var(--cw-line)" />
            </g>
          ))}
          <text
            x="273"
            y="372"
            textAnchor="middle"
            fontFamily="var(--cw-mono)"
            fontSize="10"
            letterSpacing="0.9"
            fill="var(--cw-muted)"
          >
            {illustrative("2 × 30 kW DC · 4 connectors")}
          </text>
        </g>

        {/* Competition. */}
        <g className="cwa-layer" data-layer="competition" transform="translate(344 114)">
          <rect
            x="-65"
            y="-67"
            width="130"
            height="134"
            rx="4"
            fill="var(--cw-ground)"
            fillOpacity="0.93"
            stroke="var(--cw-slate)"
            strokeOpacity="0.55"
            vectorEffect="non-scaling-stroke"
          />
          <circle
            r="23"
            fill="none"
            stroke="var(--cw-slate)"
            strokeWidth="1"
            opacity="0.55"
            vectorEffect="non-scaling-stroke"
          />
          <circle
            r="41"
            fill="none"
            stroke="var(--cw-slate)"
            strokeWidth="1"
            opacity="0.55"
            vectorEffect="non-scaling-stroke"
          />
          <circle
            r="57"
            fill="none"
            stroke="var(--cw-slate)"
            strokeWidth="1"
            opacity="0.55"
            vectorEffect="non-scaling-stroke"
          />
          <circle r="4" fill="var(--cw-accent)" />
          <circle cx="-12" cy="-31" r="3" fill="var(--cw-muted)" />
          <circle cx="35" cy="19" r="3" fill="var(--cw-muted)" />
          <circle cx="-44" cy="30" r="3" fill="var(--cw-muted)" />
          <text
            x="0"
            y="-47"
            textAnchor="middle"
            fontFamily="var(--cw-mono)"
            fontSize="10"
            letterSpacing="0.9"
            fill="var(--cw-muted)"
          >
            3 / 5 / 10 km
          </text>
          <text
            x="0"
            y="57"
            textAnchor="middle"
            fontFamily="var(--cw-mono)"
            fontSize="10"
            letterSpacing="0.9"
            fill="var(--cw-muted)"
          >
            {illustrative("3 competitors")}
          </text>
        </g>

        {/* The survey sweep - the assessment happening, clipped to the parcel
            so it reads as a scan of THIS plot, not a sci-fi flourish. */}
        <g clipPath="url(#cwaParcelClip)">
          <g className="cwa-survey">
            <rect x="40" y="-34" width="410" height="34" fill="url(#cwaSurveyTrail)" />
            <rect x="40" y="0" width="410" height="2" fill="var(--cw-accent)" opacity="0.6" />
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
        height="23"
        rx="3"
        fill="var(--cw-ground)"
        fillOpacity="0.93"
        stroke="var(--cw-slate)"
        strokeOpacity="0.55"
        vectorEffect="non-scaling-stroke"
      />
      <text
        x={x + w / 2}
        y={y + 15}
        textAnchor="middle"
        fontFamily="var(--cw-mono)"
        fontSize="10"
        letterSpacing="0.8"
        fill="var(--cw-muted)"
      >
        {label}
      </text>
    </g>
  );
}

export default SiteAssessed;
