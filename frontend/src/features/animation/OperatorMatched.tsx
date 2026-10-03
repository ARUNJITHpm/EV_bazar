import { NEIGHBOURS, OPERATOR_CANDIDATES, illustrative } from "./data";
import { useLoopClock } from "./useLoopClock";

/**
 * Animation D — the same neighbour, counted three ways.
 *
 * The one argument in this product that prose keeps losing: a charger a
 * kilometre away is competition for everybody, but a charger run by the
 * operator YOU sign with is competition AND a split, because their app now
 * has two places to send the same drivers. So the six neighbours on this
 * plane do not change between steps — only who you signed with changes, and
 * with it what each neighbour means.
 *
 * That is why it is an animation and not a paragraph. A still frame can show
 * six dots; only the cut between operators shows that the dots did not move.
 *
 * The operators are UNNAMED, and stay that way. Landing.tsx promises partner
 * operators appear named only with each one's written permission, and an
 * illustration is not an exception. Every figure runs through
 * `illustrative()` like the rest of data.ts.
 *
 * Held to the same rules as A–C: no animation library, no per-frame render —
 * one step index on a timeout chain, every movement inside a step is CSS —
 * and under `prefers-reduced-motion: reduce` the clock parks on the last
 * step, which is the summary. Nothing loops.
 */

/** Six beats: the plane, then each operator in turn, then all three. */
const STEPS = [2400, 3200, 3200, 3200, 4600] as const;

export function OperatorMatched() {
  const [ref, step] = useLoopClock<HTMLDivElement>(STEPS);
  const focus = (step >= 1 && step <= 3 ? OPERATOR_CANDIDATES[step - 1] : null) ?? null;
  const summary = step === 4;

  return (
    <div
      ref={ref}
      className="grid gap-[clamp(24px,3vw,44px)] lg:grid-cols-[minmax(0,1fr)_minmax(0,320px)]"
    >
      {/* ---------------------------------------------------- the plane */}
      <div className="relative aspect-[4/3] w-full border border-cw-line bg-cw-surface">
        {/* The two radii, drawn as rings rather than labelled distances —
            the geometry is illustrative and should not read as a scale. */}
        <Ring size={56} label={illustrative("3 km")} />
        <Ring size={88} label={illustrative("10 km")} />

        {NEIGHBOURS.map((n) => {
          const split = focus !== null && n.owner === focus.id && n.near;
          const theirs = focus !== null && n.owner === focus.id;
          return (
            <div
              key={n.id}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${n.x}%`, top: `${n.y}%` }}
            >
              <span
                className={`block h-[11px] w-[11px] rounded-full border transition-all duration-500 ${
                  split
                    ? "scale-[1.55] border-cw-accent bg-cw-accent"
                    : theirs
                      ? "border-cw-accent bg-transparent"
                      : "border-cw-muted bg-cw-muted/30"
                }`}
                style={{ transitionTimingFunction: "var(--cw-ease)" }}
              />
              <span
                className={`absolute top-[15px] left-1/2 -translate-x-1/2 font-cw-mono text-[10px] tracking-[0.08em] whitespace-nowrap uppercase transition-opacity duration-500 ${
                  split ? "text-cw-accent opacity-100" : "text-cw-muted opacity-0"
                }`}
              >
                splits
              </span>
            </div>
          );
        })}

        {/* The site. It never moves and never changes: the plot is the one
            thing the operator choice cannot alter. */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-center">
          <span className="block h-[15px] w-[15px] border-2 border-cw-text bg-cw-ground" />
          <span className="mt-2 block font-cw-mono text-[10px] tracking-[0.12em] text-cw-muted uppercase">
            Your plot
          </span>
        </div>

        <p className="absolute right-3 bottom-3 left-3 m-0 font-cw-mono text-[11px] leading-[1.5] tracking-[0.04em] text-cw-muted">
          {focus === null
            ? `${illustrative("6")} chargers nearby. Same six on every frame below.`
            : `Signed with ${focus.label}: ${illustrative(String(focus.ownWithin3km))} of these are theirs, inside 3 km.`}
        </p>
      </div>

      {/* ---------------------------------------------------- the cards */}
      <div className="flex flex-col gap-2.5">
        {OPERATOR_CANDIDATES.map((c) => {
          const on = summary || focus?.id === c.id;
          return (
            <article
              key={c.id}
              className={`border p-3.5 transition-all duration-500 ${
                on ? "border-cw-line bg-cw-surface-2 opacity-100" : "border-cw-line/60 opacity-40"
              }`}
              style={{ transitionTimingFunction: "var(--cw-ease)" }}
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-cw-mono text-[13px] tracking-[0.08em] uppercase">
                  {c.label}
                </span>
                {c.ours && (
                  <span className="font-cw-mono text-[10px] tracking-[0.08em] text-cw-muted uppercase">
                    our network
                  </span>
                )}
              </div>

              <dl className="mt-2.5 grid grid-cols-3 gap-x-3 gap-y-1">
                <Cell
                  label="own, 3 km"
                  value={illustrative(String(c.ownWithin3km))}
                  lit={on && c.ownWithin3km > 0}
                />
                <Cell label="district" value={illustrative(String(c.district))} />
                <Cell label="state" value={illustrative(String(c.state))} />
              </dl>

              <p
                className={`m-0 mt-2.5 text-[13px] leading-[1.5] text-cw-muted transition-opacity duration-500 ${
                  on ? "opacity-100" : "opacity-0"
                }`}
              >
                {c.note}
              </p>
            </article>
          );
        })}

        <p
          className={`m-0 border-t border-cw-line pt-2.5 text-[13px] leading-[1.55] text-cw-muted transition-opacity duration-500 ${
            summary ? "opacity-100" : "opacity-0"
          }`}
        >
          Three answers, one plot. The widest reach is also the nearest competition for the same
          drivers — a trade we show, and never settle for you with a single score.
        </p>
      </div>
    </div>
  );
}

/** One illustrative radius. Concentric, centred, and unlabelled by distance
 *  except in brackets — the plane is a diagram, not a map. */
function Ring({ size, label }: { size: number; label: string }) {
  return (
    <div
      className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-cw-line"
      style={{ width: `${size}%`, height: `${size}%` }}
    >
      <span className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-cw-surface px-1.5 font-cw-mono text-[10px] tracking-[0.08em] text-cw-muted">
        {label}
      </span>
    </div>
  );
}

function Cell({ label, value, lit = false }: { label: string; value: string; lit?: boolean }) {
  return (
    <div>
      <dt className="font-cw-mono text-[10px] tracking-[0.08em] text-cw-muted uppercase">
        {label}
      </dt>
      <dd
        className={`m-0 font-cw-mono text-[15px] tabular-nums transition-colors duration-500 ${
          lit ? "text-cw-accent" : "text-cw-text"
        }`}
      >
        {value}
      </dd>
    </div>
  );
}
