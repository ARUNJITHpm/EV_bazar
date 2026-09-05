import { SITE_LABEL } from "./data";

/**
 * A - Route to charge. The landing hero's right panel. 11s loop, no JS.
 *
 * The sequence is the argument, and its order is load-bearing: several
 * candidate locations are compared, ONE is chosen, and only then does a
 * vehicle reach it, charge, and throw a catchment. Chargeworthy does not
 * sell charging; it sells the choice, so the choice happens first and the
 * charging is its consequence.
 *
 * No candidate carries a score. An earlier draft scored them 74 / 81 / 76
 * against a winning 92, which invented both the numbers and the metric -
 * the report payload has no site-fit score at all. Comparison reads without
 * one: three pins are examined, two recede, one is kept.
 *
 * Copper appears only where tokens.css already licenses it - the map pin,
 * and the charge that the pin's site delivers. Everything else is slate,
 * line and surface. Keyframes live in styles/animation.css; there is no
 * animation library and no script, per design/IMPLEMENT.md:65-68.
 */

/** The corridor. Shared verbatim with .cwa-car's offset-path in the CSS -
 *  edit one and you must edit the other, or the car leaves the road. */
const ROAD =
  "M 30 566 C 172 566 232 502 302 466 C 382 424 430 376 500 338 C 566 302 622 250 700 232";

/** Charger head to the parked car's port, in the same user space. */
const CABLE = "M 788 228 C 762 228 748 240 722 236";

/** The chosen site. The catchment rings and the pin share this centre. */
const SITE = { x: 807, y: 197 };

/** Two locations that were assessed and set aside. */
const REJECTED = [
  { x: 250, y: 210 },
  { x: 470, y: 486 },
];

/** A map pin, drawn about its own point. */
const PIN = "M0 0 C -13 -16 -19 -24 -19 -33 A 19 19 0 1 1 19 -33 C 19 -24 13 -16 0 0 Z";

export function RouteToCharge({ label = SITE_LABEL }: { label?: string }) {
  return (
    // The border matters: the substrate is --cw-ground, the same colour as
    // the page, so without a frame this reads as loose shapes floating in
    // the layout rather than a panel. HeroMap, which this replaces in the
    // landing hero, was framed the same way.
    <div className="cwa-route relative border border-cw-line">
      <svg
        className="block h-auto w-full"
        viewBox="0 0 1000 620"
        role="img"
        aria-label={`Three candidate locations are compared on a map. One is selected, a vehicle drives the highway corridor to it, connects and charges, and the three, five and ten kilometre catchment rings expand around the chosen site.`}
      >
        <defs>
          <linearGradient id="cwaBeam" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--cw-accent)" stopOpacity="0.5" />
            <stop offset="100%" stopColor="var(--cw-accent)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="cwaUnit" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--cw-surface-2)" />
            <stop offset="100%" stopColor="var(--cw-surface)" />
          </linearGradient>
        </defs>

        {/* Substrate. Flat and unglamorous on purpose - a survey plan, not a
            games map. It never animates, so the loop never blanks the frame. */}
        <rect width="1000" height="620" fill="var(--cw-ground)" />
        <g stroke="var(--cw-line)" strokeWidth="1" opacity="0.5">
          <path d="M0 120 H1000 M0 300 H1000 M0 470 H1000" />
          <path d="M170 0 V620 M420 0 V620 M640 0 V620 M860 0 V620" />
        </g>
        <g fill="var(--cw-surface)">
          <rect x="60" y="150" width="90" height="120" />
          <rect x="200" y="60" width="180" height="40" />
          <rect x="460" y="490" width="150" height="90" />
          <rect x="680" y="380" width="120" height="60" />
          <rect x="220" y="330" width="70" height="110" />
        </g>

        {/* The corridor draws itself, then the lane markings fade up. They
            cannot share one animation: a CSS stroke-dasharray would
            overwrite the dash attribute and render the lane solid. */}
        <path
          className="cwa-road"
          d={ROAD}
          fill="none"
          stroke="var(--cw-surface-2)"
          strokeWidth="26"
          strokeLinecap="round"
        />
        <path
          className="cwa-centre"
          d={ROAD}
          fill="none"
          stroke="var(--cw-slate)"
          strokeWidth="1.5"
          strokeDasharray="10 14"
        />

        {/* Candidates set aside. They stay on the map at low opacity - the
            comparison happened, and hiding the losers would erase it. */}
        {REJECTED.map((p, i) => (
          <g
            key={`${p.x}-${p.y}`}
            className={`cwa-candidate cwa-candidate--${i + 1}`}
            transform={`translate(${p.x} ${p.y})`}
          >
            <path d={PIN} fill="none" stroke="var(--cw-muted)" strokeWidth="2" />
            <circle cx="0" cy="-33" r="6" fill="none" stroke="var(--cw-muted)" strokeWidth="1.75" />
          </g>
        ))}

        {/* Catchment, 3 / 5 / 10 km, drawn under the site furniture. */}
        <g fill="none" stroke="var(--cw-accent)" strokeWidth="1.25">
          <circle className="cwa-catch" cx={SITE.x} cy={SITE.y} r="58" />
          <circle className="cwa-catch cwa-catch--2" cx={SITE.x} cy={SITE.y} r="102" />
          <circle className="cwa-catch cwa-catch--3" cx={SITE.x} cy={SITE.y} r="148" />
        </g>

        {/* The chosen one. Copper here is the map pin tokens.css names.
            The placement and the animation MUST live on different elements:
            a CSS transform overrides an SVG transform attribute outright,
            so a scale keyframe on this group would drop the pin at 0,0. */}
        <g transform={`translate(${SITE.x} 126)`}>
          <g className="cwa-chosen">
            <path d={PIN} fill="var(--cw-ground)" stroke="var(--cw-accent)" strokeWidth="2.5" />
            <circle cx="0" cy="-33" r="6.5" fill="var(--cw-accent)" />
          </g>
        </g>

        <g className="cwa-site">
          {/* Parking bay */}
          <rect
            x="648"
            y="200"
            width="104"
            height="72"
            fill="none"
            stroke="var(--cw-line)"
            strokeWidth="1.5"
          />
          <path
            d="M674 200 V272 M700 200 V272 M726 200 V272"
            stroke="var(--cw-line)"
            strokeWidth="1"
          />

          {/* The charger. Original artwork - pedestal, lit screen, holstered
              connector, and an LED strip that doubles as the charge meter. */}
          <g>
            <rect x="786" y="254" width="42" height="8" rx="2" fill="var(--cw-line)" />
            <rect
              x="788"
              y="140"
              width="38"
              height="114"
              rx="8"
              fill="url(#cwaUnit)"
              stroke="var(--cw-line)"
              strokeWidth="1.5"
            />
            <rect
              x="795"
              y="150"
              width="24"
              height="28"
              rx="3"
              fill="var(--cw-ground)"
              stroke="var(--cw-line)"
              strokeWidth="1"
            />
            <rect x="799" y="157" width="16" height="2.5" fill="var(--cw-slate)" opacity="0.85" />
            <rect x="799" y="163" width="10" height="2.5" fill="var(--cw-slate)" opacity="0.5" />
            <rect
              x="794"
              y="186"
              width="14"
              height="18"
              rx="3"
              fill="var(--cw-ground)"
              stroke="var(--cw-line)"
              strokeWidth="1"
            />
            <circle
              cx="801"
              cy="193"
              r="2.6"
              fill="none"
              stroke="var(--cw-muted)"
              strokeWidth="1"
            />

            {/* Charge meter: track, then the copper fill climbing it. One
                element, one meaning - not a status ring floating in space. */}
            <line
              x1="818"
              y1="238"
              x2="818"
              y2="190"
              stroke="var(--cw-line)"
              strokeWidth="5"
              strokeLinecap="round"
            />
            <line
              className="cwa-meter"
              x1="818"
              y1="238"
              x2="818"
              y2="190"
              stroke="var(--cw-accent)"
              strokeWidth="5"
              strokeLinecap="round"
            />
          </g>

          {/* Cable reaches out, then the charge pulses along it. */}
          <path
            className="cwa-cable"
            d={CABLE}
            fill="none"
            stroke="var(--cw-line)"
            strokeWidth="4"
            strokeLinecap="round"
          />
          <path
            className="cwa-pulse"
            d={CABLE}
            fill="none"
            stroke="var(--cw-accent)"
            strokeWidth="4"
            strokeLinecap="round"
          />
        </g>

        {/* The vehicle, top-down, because the surface is a map. */}
        <g className="cwa-car">
          <g transform="translate(-20 -10)">
            <path className="cwa-beam" d="M40 3 L74 -8 L74 28 L40 17 Z" fill="url(#cwaBeam)" />
            <rect x="0" y="0" width="40" height="20" rx="5" fill="var(--cw-text)" />
            <rect
              x="10"
              y="3.5"
              width="17"
              height="13"
              rx="3"
              fill="var(--cw-ground)"
              opacity="0.82"
            />
            <rect x="30" y="4" width="3" height="3" rx="1.5" fill="var(--cw-accent)" />
            <rect x="30" y="13" width="3" height="3" rx="1.5" fill="var(--cw-accent)" />
          </g>
        </g>
      </svg>

      {/* The only number that moves anywhere on the public surface, and it is
          a state of the animation - a fictional car's charge level - not a
          statistic about the business. The bracketed figures elsewhere stay
          still, deliberately.

          Sized in cqw against .cwa-route's container, NOT in px. This is
          HTML over an SVG that scales with its column, so fixed pixels are
          correct at one width and wrong everywhere else - at hero width the
          px version swamped the map it was sitting on. */}
      <div
        className="cwa-readout absolute top-[3.5cqw] left-[3.5cqw] min-w-[17cqw] border border-cw-line bg-cw-ground/85 px-[2cqw] py-[1.5cqw]"
        aria-hidden="true"
      >
        <div className="font-cw-mono text-[clamp(8px,1.15cqw,12px)] tracking-[0.16em] text-cw-muted uppercase">
          Charging
        </div>
        <div className="cwa-pct font-cw-mono text-[clamp(19px,3cqw,32px)] leading-[1.2] font-medium tracking-[-0.02em] text-cw-accent tabular-nums" />
        <div className="mt-[0.6cqw] font-cw-mono text-[clamp(8px,1.15cqw,12px)] tracking-[0.16em] text-cw-muted uppercase">
          {label}
        </div>
      </div>
    </div>
  );
}

export default RouteToCharge;
