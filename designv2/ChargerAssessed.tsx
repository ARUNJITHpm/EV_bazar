/**
 * ChargerAssessed - hero animation B, for the "What a full assessment
 * checks" section or the report showcase.
 *
 * The unit draws itself, a survey line sweeps it, the factors resolve one
 * at a time against real units, the projected utilisation band fills
 * against the breakeven line, and the verdict lands LAST. That order is
 * the whole point and must not be re-sequenced for visual punch: the
 * report itself leads with the verdict, but this is the assessment, and
 * an assessment that announced its answer first would be a different
 * product.
 *
 * The single copper value is the unverified factor - the reserved meaning
 * tokens.css protects. The verdict uses --cw-positive, which is semantic,
 * so a DON'T BUILD renders in the same composition without contradiction.
 *
 * FACTORS below are illustrative real units, not live data. When this is
 * wired to a payload, pass them in; do not invent values to fill the
 * column, and keep the unverified row's copper meaning honest.
 */

type Factor = { name: string; value: string; unverified?: boolean };

const FACTORS: Factor[] = [
  { name: "AADT traffic count", value: "18,400 /day" },
  { name: "Transformer distance", value: "140 m" },
  { name: "Sanctioned load", value: "75 kVA" },
  { name: "Competitor density, 5 km", value: "3 stations" },
  { name: "Grid outage hours", value: "unverified", unverified: true },
];

export function ChargerAssessed({
  factors = FACTORS,
  verdict = "Build",
  note = "Clears breakeven across the projected band. Read the assumptions ledger before you commit.",
}: {
  factors?: Factor[];
  verdict?: string;
  note?: string;
}) {
  return (
    <div
      className="grid items-center gap-[clamp(24px,4vw,56px)]"
      style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 300px), 1fr))" }}
    >
      <svg
        className="block h-auto max-h-[460px] w-full"
        viewBox="0 0 380 460"
        role="img"
        aria-label="A charging unit is surveyed by a scan line while the assessment factors resolve beside it."
      >
        <defs>
          <linearGradient id="cwaBody" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--cw-surface-2)" />
            <stop offset="100%" stopColor="var(--cw-ground)" />
          </linearGradient>
          <linearGradient id="cwaScan" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--cw-accent)" stopOpacity="0" />
            <stop offset="50%" stopColor="var(--cw-accent)" stopOpacity="0.9" />
            <stop offset="100%" stopColor="var(--cw-accent)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="cwaTrail" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--cw-accent)" stopOpacity="0" />
            <stop offset="100%" stopColor="var(--cw-accent)" stopOpacity="0.22" />
          </linearGradient>
          <clipPath id="cwaUnitClip">
            <rect x="112" y="86" width="156" height="270" rx="16" />
          </clipPath>
        </defs>

        {/* Plinth */}
        <g className="cwa-unitFill">
          <rect x="92" y="392" width="196" height="12" rx="3" fill="var(--cw-line)" />
          <rect
            x="126"
            y="356"
            width="128"
            height="38"
            rx="4"
            fill="var(--cw-surface)"
            stroke="var(--cw-line)"
            strokeWidth="1.5"
          />
        </g>

        {/* Body: the fill settles in behind the drawn outline. */}
        <rect className="cwa-unitFill" x="112" y="86" width="156" height="270" rx="16" fill="url(#cwaBody)" />
        <rect
          className="cwa-unitDraw"
          x="112"
          y="86"
          width="156"
          height="270"
          rx="16"
          fill="none"
          stroke="var(--cw-slate)"
          strokeWidth="1.75"
          opacity="0.85"
        />

        {/* Screen */}
        <g className="cwa-screen">
          <rect
            x="134"
            y="112"
            width="112"
            height="76"
            rx="6"
            fill="var(--cw-ground)"
            stroke="var(--cw-line)"
            strokeWidth="1.5"
          />
          <text x="148" y="140" fontFamily="var(--cw-mono)" fontSize="21" fill="var(--cw-text)">
            60 kW
          </text>
          <text
            x="148"
            y="163"
            fontFamily="var(--cw-mono)"
            fontSize="11"
            fill="var(--cw-muted)"
            letterSpacing="1.4"
          >
            CCS-2 &#183; DC
          </text>
          <rect x="148" y="172" width="84" height="4" rx="2" fill="var(--cw-line)" />
          <rect x="148" y="172" width="52" height="4" rx="2" fill="var(--cw-slate)" />
        </g>

        {/* LED strip */}
        <rect className="cwa-led" x="186" y="206" width="8" height="96" rx="4" fill="var(--cw-accent)" />

        {/* Holstered connectors and their cables */}
        <g className="cwa-unitFill">
          <rect
            x="132"
            y="214"
            width="30"
            height="40"
            rx="6"
            fill="var(--cw-ground)"
            stroke="var(--cw-line)"
            strokeWidth="1.5"
          />
          <circle cx="147" cy="228" r="5" fill="none" stroke="var(--cw-muted)" strokeWidth="1.5" />
          <path
            d="M147 254 C 147 300 96 300 96 344"
            fill="none"
            stroke="var(--cw-line)"
            strokeWidth="7"
            strokeLinecap="round"
          />
          <rect
            x="218"
            y="214"
            width="30"
            height="40"
            rx="6"
            fill="var(--cw-ground)"
            stroke="var(--cw-line)"
            strokeWidth="1.5"
          />
          <circle cx="233" cy="228" r="5" fill="none" stroke="var(--cw-muted)" strokeWidth="1.5" />
          <path
            d="M233 254 C 233 300 288 300 288 344"
            fill="none"
            stroke="var(--cw-line)"
            strokeWidth="7"
            strokeLinecap="round"
          />
        </g>

        {/* The survey sweep: a soft trailing band under a hard copper edge,
            clipped to the unit so it reads as a scan of THIS object. */}
        <g clipPath="url(#cwaUnitClip)">
          <g className="cwa-scan">
            <rect x="112" y="66" width="156" height="30" fill="url(#cwaTrail)" />
            <rect x="112" y="94" width="156" height="2.5" fill="url(#cwaScan)" />
          </g>
        </g>
      </svg>

      <div className="flex min-w-0 flex-col">
        <div className="mb-1.5">
          <div className="font-cw-mono text-[13px] tracking-[0.16em] text-cw-muted uppercase">
            Measured, not assumed
          </div>
          <h2 className="mt-3.5 text-[clamp(24px,3vw,32px)] leading-[1.15] font-medium">
            Nothing here is a guess.
          </h2>
        </div>

        {factors.map((f, i) => (
          <div
            key={f.name}
            className={`cwa-row flex items-baseline gap-3.5 border-t border-cw-line py-[11px] ${
              i === factors.length - 1 ? "border-b" : ""
            }`}
            style={{ animationDelay: `${i * 0.36}s` }}
          >
            <span className="min-w-0 flex-auto text-[16px]">{f.name}</span>
            <span
              className={`font-cw-mono text-[15px] whitespace-nowrap tabular-nums ${
                f.unverified ? "text-cw-accent" : "text-cw-muted"
              }`}
            >
              {f.value}
            </span>
          </div>
        ))}

        {/* P10-P90 against breakeven - a band, never a single number. */}
        <div className="mt-[26px]">
          <div className="relative h-2.5 border border-cw-line bg-cw-surface-2">
            <div className="cwa-band absolute top-0 bottom-0 left-[18%] bg-cw-slate" />
            <div className="cwa-breakeven absolute top-[-4px] bottom-[-4px] left-[34%] w-0.5 bg-cw-text" />
          </div>
          <div className="mt-2.5 flex justify-between gap-3 font-cw-mono text-[12px] tracking-[0.06em] text-cw-muted">
            <span>P10</span>
            <span>BREAKEVEN</span>
            <span>P90</span>
          </div>
        </div>

        <div className="cwa-verdict mt-6 border-t-2 border-cw-line pt-[18px]">
          <div className="font-cw-mono text-[clamp(26px,3.4vw,38px)] leading-[1.15] font-medium tracking-[0.04em] text-cw-positive uppercase">
            {verdict}
          </div>
          <p className="mt-1.5 text-[16px] text-cw-muted">{note}</p>
        </div>
      </div>
    </div>
  );
}

export default ChargerAssessed;
