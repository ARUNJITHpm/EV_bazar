/**
 * RouteToCharge - hero animation A, for the landing hero's right panel.
 *
 * A vehicle drives the corridor, parks in the bay at the assessed site,
 * connects, and charges; only then do the 3 / 5 / 10 km catchment rings
 * expand. The order is the argument: a real location, on a real road,
 * that a real car reaches - the catchment is the consequence, not the
 * opening claim.
 *
 * Decorative and aria-hidden is NOT right here - the sequence carries
 * meaning the copy does not, so it ships as an img role with a label.
 *
 * Copper (--cw-accent) appears three times only - the meter strip, the
 * live cable, the catchment rings - holding the ~5% budget tokens.css
 * describes. Keyframes live in designv2/animations.css; there is no
 * animation library and no JS, per design/IMPLEMENT.md:65-68.
 *
 * Swap-in: this replaces <HeroMap /> in Landing.tsx's Hero, or sits
 * beside it. Unlike HeroMap it carries no Mapbox payload, so it needs no
 * React.lazy boundary.
 */

/** The corridor. Shared verbatim with .cwa-car's offset-path in the CSS -
 *  if you edit one, edit both or the car leaves the road. */
const ROAD =
  "M 30 566 C 172 566 232 502 302 466 C 382 424 430 376 500 338 C 566 302 622 250 700 232";

/** Charger-to-car cable, in the same user space. */
const CABLE = "M 788 228 C 762 228 748 240 722 236";

/** The demo site's pin - KL-TVM-DEMO-001, the same one HeroMap centres on. */
const SITE = { x: 807, y: 198 };

export function RouteToCharge({ siteId = "KL-TVM-DEMO-001" }: { siteId?: string }) {
  return (
    <div className="cwa-route">
      <svg
        className="cwa-route__svg"
        viewBox="0 0 1000 620"
        role="img"
        aria-label="A vehicle drives a highway corridor to a charging site, connects and charges, and the three, five and ten kilometre catchment rings expand around the site."
      >
        <defs>
          <linearGradient id="cwaBeam" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--cw-accent)" stopOpacity="0.55" />
            <stop offset="100%" stopColor="var(--cw-accent)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="cwaUnit" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--cw-surface-2)" />
            <stop offset="100%" stopColor="var(--cw-surface)" />
          </linearGradient>
        </defs>

        {/* Map substrate. Flat and unglamorous on purpose - this is a survey
            plan, not a games map. */}
        <rect width="1000" height="620" fill="var(--cw-ground)" />
        <g stroke="var(--cw-line)" strokeWidth="1" opacity="0.55">
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

        {/* The corridor draws itself, then the lane markings fade up. */}
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

        {/* Catchment, 3 / 5 / 10 km. */}
        <g fill="none" stroke="var(--cw-accent)" strokeWidth="1.25">
          <circle className="cwa-catch" cx={SITE.x} cy={SITE.y} r="58" />
          <circle className="cwa-catch cwa-catch--2" cx={SITE.x} cy={SITE.y} r="102" />
          <circle className="cwa-catch cwa-catch--3" cx={SITE.x} cy={SITE.y} r="148" />
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
          <path d="M674 200 V272 M700 200 V272 M726 200 V272" stroke="var(--cw-line)" strokeWidth="1" />

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
            <circle cx="801" cy="193" r="2.6" fill="none" stroke="var(--cw-muted)" strokeWidth="1" />

            {/* Charge meter: track, then the copper fill climbing it. */}
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
            <rect x="10" y="3.5" width="17" height="13" rx="3" fill="var(--cw-ground)" opacity="0.82" />
            <rect x="30" y="4" width="3" height="3" rx="1.5" fill="var(--cw-accent)" />
            <rect x="30" y="13" width="3" height="3" rx="1.5" fill="var(--cw-accent)" />
          </g>
        </g>
      </svg>

      {/* Readout. The only number that moves on the landing page, and it is
          a state of the animation - not a claim about the business. The
          bracketed statistics below the hero stay still, deliberately. */}
      <div
        className="cwa-readout absolute top-[clamp(16px,3vw,28px)] left-[clamp(16px,3vw,32px)] min-w-[168px] border border-cw-line bg-cw-ground/85 px-[18px] py-3.5"
        aria-hidden="true"
      >
        <div className="font-cw-mono text-[11px] tracking-[0.16em] text-cw-muted uppercase">
          Charging
        </div>
        <div className="cwa-pct font-cw-mono text-[30px] leading-[1.2] font-medium tracking-[-0.02em] text-cw-accent tabular-nums" />
        <div className="mt-1.5 font-cw-mono text-[11px] tracking-[0.16em] text-cw-muted uppercase">
          {siteId}
        </div>
      </div>
    </div>
  );
}

export default RouteToCharge;
