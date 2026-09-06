import { HERO_METRICS, SITE_LABEL, TOTAL_CHECKS, illustrative } from "./data";

/**
 * A - Route to charge. The landing hero's right panel. 18s loop, no JS.
 *
 * Ported from Designv3/route-to-charge.html: the same street network, the
 * same corridor, the same vehicle, the same beats. Two things did not come
 * across, and both are deliberate.
 *
 * The candidate score pills (74 / 81 / 76 against a winning 92) and the
 * card's SITE FIT 92/100 are gone. The report payload has no site-fit field
 * (app/domain/report/payload.py), so a headline score would market a number
 * the product cannot deliver. The counter that made that beat work is kept
 * and pointed at something real: the 34 checks, counting in. Everything
 * else - the block hierarchy, the roundabouts, the drawn corridor, the
 * top-down car, the recommended pin, the catchment, the result card - is
 * the reference drawing.
 *
 * Colour is this site's, not the reference's. Designv3 runs green on near
 * black; this surface runs on --cw-ground with slate structure, and copper
 * appears only where tokens.css licenses it: the map pin, its catchment,
 * and the tail lights of the car arriving at it.
 *
 * Keyframes live in styles/animation.css. There is no animation library and
 * no script, per design/IMPLEMENT.md:65-68 - the reference drove the car
 * with requestAnimationFrame and getPointAtLength; offset-path walks the
 * same path for nothing.
 */

/** The corridor. Shared verbatim with .cwa-car's offset-path in the CSS -
 *  edit one and you must edit the other, or the car leaves the road. */
const ROUTE =
  "M -35 568 C 120 562 205 520 244 448 C 288 367 356 402 451 354 C 540 309 539 235 640 205 C 735 177 850 206 932 127";

/** The chosen site. Pin, rings and label all hang off this point. */
const SITE = { x: 932, y: 127 };

/** Locations that were assessed and set aside. They stay on the map. */
const CANDIDATES = [
  { x: 178, y: 106 },
  { x: 493, y: 111 },
  { x: 292, y: 386 },
];

const CANDIDATE_PIN =
  "M0 -17 C-10 -17 -16 -10 -16 -1 C-16 10 0 25 0 25 C0 25 16 10 16 -1 C16 -10 10 -17 0 -17Z";
const BEST_PIN =
  "M0 -28 C-17 -28 -29 -17 -29 0 C-29 20 0 45 0 45 C0 45 29 20 29 0 C29 -17 17 -28 0 -28Z";
const BOLT = "M3 -14 L-10 3 H-2 L-6 15 L11 -6 H3Z";

/** Street network. Two weights, because a map with no hierarchy reads as a
 *  diagram - which is exactly what the earlier grid of straight lines did. */
const MAJOR_ROADS = [
  "M-25 108 C93 38 185 48 269 112 S423 190 523 121 S734 38 1028 84",
  "M-20 252 C95 228 137 180 184 109 S278 40 332 -24",
  "M118 -25 C170 82 185 170 178 264 S150 415 66 474",
  "M290 -25 C314 83 369 137 458 148 S586 167 649 240 S782 333 1025 296",
  "M431 -24 C457 85 466 131 452 204 S409 307 331 349 S204 427 -26 454",
  "M581 -24 C605 89 638 150 699 176 S833 192 1026 158",
  "M767 -24 C781 89 760 170 710 231 S638 358 664 645",
  "M883 -24 C861 91 875 176 930 242 S985 400 1010 645",
  "M-28 540 C118 530 238 501 361 456 S607 364 748 389 S900 492 1028 536",
  "M238 645 C267 536 302 463 369 414 S525 362 577 291 S651 182 761 147",
];

const MINOR_ROADS = [
  "M18 337 L138 299 L258 304 L340 251 L421 243",
  "M204 208 L281 280 L331 349 L426 398",
  "M505 77 L557 157 L577 291 L535 428",
  "M683 57 L699 176 L829 269 L930 242",
  "M748 389 L821 326 L907 365 L978 450",
  "M66 474 L140 555 L190 628",
  "M53 183 L158 165 L247 193 L339 172",
  "M801 62 L829 150 L913 196 L993 220",
];

/** City blocks, drawn as rings (outer minus inner, evenodd) so they read as
 *  built frontage rather than filled slabs. */
const BLOCKS = [
  "M63 61h82v53H63z M72 70h64v35H72z",
  "M302 68h91v49H302z M311 77h73v31H311z",
  "M526 47h85v54H526z M535 56h67v36H535z",
  "M77 343h73v74H77z M86 352h55v56H86z",
  "M259 510h110v49H259z M268 519h92v31H268z",
  "M512 462h88v66H512z M521 471h70v48H521z",
  "M805 397h105v53H805z M814 406h87v35H814z",
];

export function RouteToCharge({ label = SITE_LABEL }: { label?: string }) {
  return (
    // The border matters: the substrate is --cw-ground, the same colour as
    // the page, so without a frame this reads as loose shapes floating in
    // the layout rather than a panel.
    <div className="cwa-route relative overflow-hidden border border-cw-line">
      <svg
        className="block h-auto w-full"
        viewBox="0 0 1000 620"
        role="img"
        aria-label="Candidate locations are compared across a street network. One is recommended, the corridor to it draws itself, a vehicle drives it, and the catchment rings expand around the chosen site."
      >
        <defs>
          <pattern id="cwaGrid" width="38" height="38" patternUnits="userSpaceOnUse">
            <path
              d="M38 0H0V38"
              fill="none"
              stroke="var(--cw-line)"
              strokeWidth="1"
              opacity="0.34"
            />
          </pattern>

          <radialGradient id="cwaHalo">
            <stop offset="0%" stopColor="var(--cw-accent)" stopOpacity="0.26" />
            <stop offset="45%" stopColor="var(--cw-accent)" stopOpacity="0.11" />
            <stop offset="100%" stopColor="var(--cw-accent)" stopOpacity="0" />
          </radialGradient>

          <linearGradient id="cwaBody" x1="0" y1="-1" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--cw-text)" />
            <stop offset="55%" stopColor="var(--cw-text)" stopOpacity="0.86" />
            <stop offset="100%" stopColor="var(--cw-muted)" />
          </linearGradient>

          <linearGradient id="cwaGlass" x1="0" y1="-1" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--cw-surface-2)" />
            <stop offset="100%" stopColor="var(--cw-ground)" />
          </linearGradient>

          <clipPath id="cwaFrame">
            <rect width="1000" height="620" />
          </clipPath>

          {/* One authoritative path: the plain road, the highlighted
              corridor and the car's motion all read from this element. */}
          <path id="cwaRoutePath" pathLength="1" d={ROUTE} />
        </defs>

        {/* Substrate. It never animates, so the loop never blanks the frame. */}
        <rect width="1000" height="620" fill="var(--cw-ground)" />
        <rect width="1000" height="620" fill="url(#cwaGrid)" />

        <g clipPath="url(#cwaFrame)">
          {/* Blocks sit beneath the streets - the map hierarchy is what
              makes this read as a place rather than a diagram. */}
          <g fill="var(--cw-surface)" stroke="var(--cw-line)" strokeWidth="1" opacity="0.62">
            {BLOCKS.map((d) => (
              <path key={d} d={d} fillRule="evenodd" />
            ))}
          </g>

          <g fill="none" strokeLinecap="round" strokeLinejoin="round">
            {MINOR_ROADS.map((d) => (
              <path key={d} d={d} stroke="var(--cw-surface-2)" strokeWidth="5" />
            ))}
            {MAJOR_ROADS.map((d) => (
              <path key={d} d={d} stroke="var(--cw-line)" strokeWidth="10" opacity="0.9" />
            ))}
            <circle
              cx="458"
              cy="148"
              r="49"
              stroke="var(--cw-line)"
              strokeWidth="10"
              opacity="0.9"
            />
            <circle
              cx="710"
              cy="231"
              r="59"
              stroke="var(--cw-line)"
              strokeWidth="10"
              opacity="0.9"
            />
            <use href="#cwaRoutePath" stroke="var(--cw-line)" strokeWidth="10" opacity="0.9" />
          </g>

          {/* Candidates assessed and set aside. They carry no score: the
              report has no site-fit metric, so a number here would invent
              both the figure and the thing it measures. */}
          <g className="cwa-candidates">
            {CANDIDATES.map((p) => (
              <g key={`${p.x}-${p.y}`} transform={`translate(${p.x} ${p.y})`}>
                <path
                  d={CANDIDATE_PIN}
                  fill="var(--cw-ground)"
                  stroke="var(--cw-muted)"
                  strokeWidth="2.5"
                  vectorEffect="non-scaling-stroke"
                />
                <circle
                  cx="0"
                  cy="-1"
                  r="5"
                  fill="none"
                  stroke="var(--cw-muted)"
                  strokeWidth="2"
                  vectorEffect="non-scaling-stroke"
                />
              </g>
            ))}
          </g>

          {/* The chosen location, before it is recommended - the same grey
              pin as the others, so the choice is visibly a choice. */}
          <g className="cwa-shortlist" transform={`translate(${SITE.x} ${SITE.y})`}>
            <path
              d={CANDIDATE_PIN}
              fill="var(--cw-ground)"
              stroke="var(--cw-muted)"
              strokeWidth="2.5"
              vectorEffect="non-scaling-stroke"
            />
            <circle
              cx="0"
              cy="-1"
              r="5"
              fill="none"
              stroke="var(--cw-muted)"
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            />
          </g>

          {/* The corridor, drawn. pathLength="1" above is what lets the dash
              be written as a single unit rather than a measured guess. */}
          <use
            className="cwa-route-edge"
            href="#cwaRoutePath"
            fill="none"
            stroke="var(--cw-surface-2)"
            strokeWidth="36"
            strokeLinecap="round"
          />
          <use
            className="cwa-route-line"
            href="#cwaRoutePath"
            fill="none"
            stroke="var(--cw-slate)"
            strokeWidth="28"
            strokeLinecap="round"
            opacity="0.42"
          />

          {/* Catchment, drawn under the site furniture. */}
          <circle
            className="cwa-catch"
            cx={SITE.x}
            cy={SITE.y}
            r="72"
            fill="none"
            stroke="var(--cw-accent)"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />
          <circle
            className="cwa-catch cwa-catch--2"
            cx={SITE.x}
            cy={SITE.y}
            r="126"
            fill="none"
            stroke="var(--cw-accent)"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />

          {/* The recommended site. Copper here is the map pin tokens.css
              names. Placement and animation MUST stay on different
              elements: a CSS transform overrides an SVG transform attribute
              outright, and a scale keyframe on the outer group would drop
              the pin at 0,0. */}
          <g transform={`translate(${SITE.x} ${SITE.y})`}>
            <g className="cwa-best">
              <path
                d={BEST_PIN}
                fill="var(--cw-accent)"
                stroke="var(--cw-accent)"
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
              />
              <circle cx="0" cy="0" r="18" fill="var(--cw-ground)" />
              <path d={BOLT} fill="var(--cw-accent)" />
              <g transform="translate(-57 55)">
                <rect
                  width="114"
                  height="27"
                  rx="2"
                  fill="var(--cw-ground)"
                  stroke="var(--cw-accent)"
                  strokeWidth="1"
                  vectorEffect="non-scaling-stroke"
                />
                <text
                  x="57"
                  y="18"
                  textAnchor="middle"
                  fontFamily="var(--cw-mono)"
                  fontSize="12"
                  fontWeight="600"
                  letterSpacing="1.2"
                  fill="var(--cw-text)"
                >
                  RECOMMENDED
                </text>
              </g>
            </g>
          </g>

          {/* The vehicle, top-down, because the surface is a map. Drawn
              about its own origin facing +x, which is what offset-rotate
              expects - no centring wrapper. */}
          <g className="cwa-car">
            <circle className="cwa-halo" cx="0" cy="0" r="69" fill="url(#cwaHalo)" />
            <g>
              <rect x="-23" y="-20" width="14" height="4" rx="2" fill="var(--cw-ground)" />
              <rect x="11" y="-20" width="14" height="4" rx="2" fill="var(--cw-ground)" />
              <rect x="-23" y="16" width="14" height="4" rx="2" fill="var(--cw-ground)" />
              <rect x="11" y="16" width="14" height="4" rx="2" fill="var(--cw-ground)" />
              <path
                d="M-30 -14 Q-25 -19 -16 -19 H18 Q28 -17 32 -9 V9 Q28 17 18 19 H-16 Q-25 19 -30 14 Q-33 8 -33 0 Q-33 -8 -30 -14Z"
                fill="url(#cwaBody)"
                stroke="var(--cw-muted)"
                strokeWidth="1"
              />
              <path d="M-12 -15 H11 L20 -8 H-16Z" fill="url(#cwaGlass)" />
              <path d="M-16 8 H20 L11 15 H-12Z" fill="url(#cwaGlass)" />
              <rect
                x="-16"
                y="-6"
                width="36"
                height="12"
                rx="3"
                fill="var(--cw-surface-2)"
                stroke="var(--cw-line)"
                strokeWidth="0.8"
              />
              <path
                d="M-23 -13 L-17 -7 V7 L-23 13 M25 -11 V11 M-11 -6 V6 M16 -6 V6 M-29 0 H31"
                fill="none"
                stroke="var(--cw-muted)"
                strokeWidth="1"
                opacity="0.7"
              />
              <path
                d="M-8 -20 h7 v3 h-7z M-8 17 h7 v3 h-7z"
                fill="var(--cw-text)"
                stroke="var(--cw-muted)"
                strokeWidth="0.6"
              />
              <circle cx="-30" cy="-9" r="2" fill="var(--cw-accent)" />
              <circle cx="-30" cy="9" r="2" fill="var(--cw-accent)" />
              <rect x="28" y="-10" width="3" height="6" rx="1" fill="var(--cw-text)" />
              <rect x="28" y="4" width="3" height="6" rx="1" fill="var(--cw-text)" />
            </g>
          </g>
        </g>
      </svg>

      {/* The result card. Sized in cqw against .cwa-route, NOT in px: this
          is HTML over an SVG that scales with its column, so fixed pixels
          are correct at one width and wrong everywhere else.

          Where the reference put SITE FIT 92 / 100 this counts the checks
          in. The counter is the same device; what it counts is a number the
          product actually produces. */}
      <div
        className="cwa-card absolute top-[6%] left-[4.5%] w-[clamp(164px,32cqw,300px)] border border-cw-line bg-cw-ground/92 px-[2.2cqw] py-[2cqw]"
        aria-hidden="true"
      >
        <div className="font-cw-mono text-[clamp(8px,1.15cqw,12px)] font-semibold tracking-[0.14em] text-cw-accent uppercase">
          Recommended site
        </div>

        <div className="mt-[1.4cqw] mb-[1.8cqw] flex items-baseline gap-[0.8cqw]">
          <span className="mr-auto font-cw-mono text-[clamp(9px,1.35cqw,15px)] tracking-[0.08em] text-cw-text uppercase">
            Assessed
          </span>
          <span className="cwa-count font-cw-mono text-[clamp(20px,3.6cqw,40px)] leading-none font-medium tracking-[-0.02em] text-cw-text tabular-nums" />
          <span className="font-cw-mono text-[clamp(8px,1.15cqw,12px)] text-cw-muted">
            /{TOTAL_CHECKS}
          </span>
        </div>

        <dl className="m-0 border-y border-cw-line">
          {HERO_METRICS.map((m, i) => (
            <div
              key={m.label}
              className={`flex items-baseline justify-between gap-[1.4cqw] py-[0.9cqw] font-cw-mono text-[clamp(7px,1.05cqw,11px)] tracking-[0.05em] text-cw-muted uppercase ${
                i > 0 ? "border-t border-cw-line" : ""
              }`}
            >
              <dt>{m.label}</dt>
              <dd className="m-0 font-medium whitespace-nowrap text-cw-text tabular-nums">
                {illustrative(m.value)}
              </dd>
            </div>
          ))}
        </dl>

        <div className="mt-[1.2cqw] font-cw-mono text-[clamp(6px,0.86cqw,9px)] tracking-[0.11em] text-cw-muted uppercase">
          {label} · illustrative
        </div>
      </div>

      <div
        className="absolute right-[2.8%] bottom-[3.5%] font-cw-mono text-[clamp(7px,1cqw,11px)] tracking-[0.13em] text-cw-muted uppercase opacity-60"
        aria-hidden="true"
      >
        Site viability · route access
      </div>
    </div>
  );
}

export default RouteToCharge;
