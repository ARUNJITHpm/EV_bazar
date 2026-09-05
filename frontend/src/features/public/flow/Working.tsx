import { useCallback, useEffect, useRef, useState } from "react";

import { AssemblingReport } from "../../animation/AssemblingReport";
import { checkFor, illustrative } from "../../animation/data";

/**
 * The working screen: the 34 factors, checked in front of the customer.
 *
 * The real request (one POST /assess) is fired the moment this mounts and
 * runs in parallel with the walk-through below. The walk-through paces the
 * 34 factors over about fourteen seconds, grouped the way the report groups
 * them, so the customer sees WHAT is being weighed — the same list the
 * landing page promises — rather than a spinner. Owner's call, 2026-09-03:
 * an answer that lands in under a second reads as a guess, and this one
 * is not a guess.
 *
 * VALUES ON THIS SCREEN ARE ILLUSTRATIVE. Owner's call, 2026-09-06,
 * reversing the earlier rule that a factor may tick but never show a number
 * it did not fetch: the walk-through now carries the sample values from
 * features/animation/data.ts so the shape of a finished assessment is
 * visible while the real one runs, and they are to be replaced with fetched
 * values later. They render BRACKETED — [18,400 /day] — which is the
 * repo's marker for a number nobody has sourced yet, so the placeholder
 * announces itself for as long as it is one. Wiring the real values is a
 * matter of passing them in beside `done`; nothing here needs restructuring
 * for it.
 *
 * The other honesty rule is untouched and must stay that way: the screen
 * never finishes ahead of the request. If the assessment takes longer than
 * the walk-through, the last factor stays open until the answer lands, and
 * the assembling sheet beside it never shows a verdict — the router
 * replaces it with the real report seconds later, and a guessed verdict
 * would be contradicted by the very next screen.
 * prefers-reduced-motion drops the pacing entirely and waits on the request
 * alone.
 */

interface Group {
  name: string;
  /** What is being read for this group — a source, never a result. */
  source: string;
  factors: string[];
}

const GROUPS: Group[] = [
  {
    name: "Access and geometry",
    source: "OpenStreetMap road layer",
    factors: [
      "Road class",
      "Distance from main road",
      "Carriageway direction served",
      "Sub-road access",
      "Median or divider",
      "Sight line",
      "Turning radius",
      "Entry and exit width",
      "Frontage width",
      "AADT traffic count",
      "Dominant flow direction",
      "Peak hour timing",
    ],
  },
  {
    name: "Demand",
    source: "VAHAN registrations, this district",
    factors: [
      "EV registrations",
      "Registration mix",
      "Fleet operators within 10 km",
      "Distance to nearest city",
    ],
  },
  {
    name: "Power and tariff",
    source: "State regulator’s EV tariff order",
    factors: [
      "Tariff order",
      "Demand charges",
      "Sanctioned load",
      "Transformer distance",
      "Transformer spare capacity",
      "Grid outage hours",
      "New connection cost",
      "State subsidy applicability",
    ],
  },
  {
    name: "Site and amenities",
    source: "OpenStreetMap places within 1 km",
    factors: [
      "Plot area",
      "Parking bays",
      "Canopy feasibility",
      "Amenities within walking distance",
      "Mobile network coverage",
      "Night lighting",
      "Land or lease cost",
    ],
  },
  {
    name: "Competition",
    source: "Competitor inventory, 10 km radius",
    factors: ["Competitor distance", "Competitor density at 3 / 5 / 10 km", "Announced stations"],
  },
];

const TOTAL = GROUPS.reduce((n, g) => n + g.factors.length, 0);
/** The same groups, in the shape the assembling sheet wants. */
const SHEET_GROUPS = GROUPS.map((g) => ({ name: g.name, count: g.factors.length }));
/** About fourteen seconds end to end, with a little unevenness so it reads
 *  as reading, not as a metronome. */
const TARGET_MS = 14_000;
/** A beat at the end with every tick showing before the answer replaces it. */
const HOLD_MS = 700;

/** When each factor ticks, in ms from the start: jittered steps normalised
 *  so the whole walk lands on TARGET_MS. Read against the clock rather than
 *  chained as timeouts, so a busy main thread (the map behind this screen
 *  is not free) slips a tick, never the total. */
function makeSchedule(): number[] {
  const steps = Array.from({ length: TOTAL }, () => 0.7 + Math.random() * 0.6);
  const sum = steps.reduce((a, b) => a + b, 0);
  let acc = 0;
  return steps.map((s) => (acc += (s / sum) * TARGET_MS));
}

const reduced = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function Tick({ animate = true }: { animate?: boolean }) {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={`text-cw-positive ${animate ? "cw-tick" : ""}`}
    >
      <path d="M4 10.5 L8.2 14.5 L16 5.5" />
    </svg>
  );
}

function Ring({ active }: { active: boolean }) {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      aria-hidden="true"
      className={active ? "cw-reading text-cw-slate" : "text-cw-line"}
    >
      <circle cx="10" cy="10" r="4.4" />
    </svg>
  );
}

export function Working({
  run,
  onDone,
}: {
  /** The real assessment call. Resolves true when the answer is stored. */
  run: () => Promise<boolean>;
  onDone: () => void;
}) {
  const [settled, setSettled] = useState(false);
  const [failed, setFailed] = useState(false);
  /** Factors ticked so far, 0..TOTAL. */
  const [done, setDone] = useState(0);
  const started = useRef(false);
  const alive = useRef(true);
  const paced = useRef(!reduced());
  const schedule = useRef<number[]>([]);
  const startedAt = useRef(0);
  // The request is fired once and must survive re-renders, so the callbacks
  // are read through a ref rather than being effect dependencies. Without
  // this the effect re-runs on every render, its own cleanup clears the
  // liveness flag, and the completion callback silently no-ops - which
  // strands the customer on this screen after a request that succeeded.
  // StrictMode's deliberate double-invoke does the same thing, so the flag
  // is RE-ARMED on every run rather than only initialised.
  const latest = useRef({ run, onDone });
  latest.current = { run, onDone };

  const fire = useCallback(() => {
    setFailed(false);
    latest.current
      .run()
      .then((ok) => {
        if (!alive.current) return;
        if (ok) setSettled(true);
        else setFailed(true);
      })
      .catch(() => {
        // A thrown request must land somewhere the customer can act on -
        // never on a screen that spins for ever.
        if (alive.current) setFailed(true);
      });
  }, []);

  useEffect(() => {
    alive.current = true;
    if (!started.current) {
      started.current = true;
      fire();
    }
    return () => {
      alive.current = false;
    };
  }, [fire]);

  // The walk-through, read against the clock. The last factor waits for the
  // request: the screen never claims to have finished before the answer
  // exists.
  useEffect(() => {
    if (!paced.current || failed) return undefined;
    if (schedule.current.length === 0) {
      schedule.current = makeSchedule();
      startedAt.current = performance.now();
    }
    const id = setInterval(() => {
      const elapsed = performance.now() - startedAt.current;
      let n = schedule.current.filter((t) => t <= elapsed).length;
      if (!settled) n = Math.min(n, TOTAL - 1);
      setDone((prev) => Math.max(prev, n));
      if (n >= TOTAL) clearInterval(id);
    }, 80);
    return () => clearInterval(id);
  }, [settled, failed]);

  // Unpaced (reduced motion): everything resolves the moment the answer lands.
  useEffect(() => {
    if (!paced.current && settled) setDone(TOTAL);
  }, [settled]);

  // Both halves finished: hold a beat with every tick showing, then move on.
  useEffect(() => {
    if (!settled || done < TOTAL) return undefined;
    const t = setTimeout(
      () => {
        if (alive.current) latest.current.onDone();
      },
      paced.current ? HOLD_MS : 0,
    );
    return () => clearTimeout(t);
  }, [settled, done]);

  if (failed) {
    return (
      <div className="flex max-w-[720px] flex-col gap-6">
        <h1 className="text-[clamp(28px,4vw,40px)] leading-[1.15] font-medium">
          We could not finish the check.
        </h1>
        <p className="text-cw-muted">
          Nothing was priced and your answers are still here. This is our end, not yours — try it
          again.
        </p>
        <div>
          <button
            type="button"
            onClick={fire}
            className="inline-flex min-h-[58px] items-center justify-center bg-cw-accent px-7 text-[17px] font-semibold text-cw-ground transition-[filter] duration-200 hover:brightness-107"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  const finished = done >= TOTAL && settled;

  return (
    <div className="flex max-w-[1140px] flex-col gap-[clamp(28px,4vw,40px)]">
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
        <div className="flex max-w-[640px] flex-col gap-3.5">
          <h1 className="text-[clamp(28px,4vw,40px)] leading-[1.15] font-medium">
            {finished
              ? "Checked. Preparing your answer."
              : `Checking ${TOTAL} factors against this location.`}
          </h1>
          <p className="text-cw-muted">
            This takes about fifteen seconds. We are reading the live sources now, not handing you a
            stored answer.
          </p>
        </div>
        <div
          className="font-cw-mono text-[clamp(28px,4vw,40px)] leading-none font-medium tracking-[-0.02em] text-cw-text tabular-nums"
          aria-hidden="true"
        >
          {done}
          <span className="text-cw-muted"> / {TOTAL}</span>
        </div>
      </div>

      <div className="h-0.5 bg-cw-line" aria-hidden="true">
        <div
          className="h-0.5 bg-cw-slate transition-[width] duration-[420ms] ease-(--cw-ease)"
          style={{ width: `${(done / TOTAL) * 100}%` }}
        />
      </div>

      {/* The checks on the left feed the document on the right. The list
          stays the accessible one - the sheet is aria-hidden, because a
          screen reader following aria-live would otherwise hear every
          factor twice. */}
      <div className="grid grid-cols-1 items-start gap-[clamp(28px,4vw,56px)] min-[1000px]:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <ol role="status" aria-live="polite" className="m-0 flex list-none flex-col p-0">
          {(() => {
            let offset = 0;
            return GROUPS.map((g) => {
              const start = offset;
              offset += g.factors.length;
              return (
                <GroupRow
                  key={g.name}
                  group={g}
                  start={start}
                  done={done}
                  paced={paced.current}
                  settled={settled}
                />
              );
            });
          })()}
        </ol>

        <AssemblingReport groups={SHEET_GROUPS} done={done} settled={settled} />
      </div>
    </div>
  );
}

function GroupRow({
  group,
  start,
  done,
  paced,
  settled,
}: {
  group: Group;
  start: number;
  done: number;
  paced: boolean;
  settled: boolean;
}) {
  const end = start + group.factors.length;
  const complete = done >= end;
  const active = !complete && done >= start;
  // Unpaced, every group stays open so the whole list is on the page at once.
  const open = active || !paced;

  return (
    <li className="border-b border-cw-line">
      <div
        className={`flex min-h-[56px] items-center gap-[18px] py-3 transition-colors duration-300 ${
          complete || active ? "text-cw-text" : "text-cw-muted"
        }`}
      >
        <span className="flex w-[17px] shrink-0 justify-center">
          {complete ? <Tick animate={paced} /> : <Ring active={active} />}
        </span>
        <span className="flex-grow font-cw-mono text-[17px]">{group.name}</span>
        <span className="font-cw-mono text-[14px] text-cw-muted tabular-nums">
          {complete
            ? `${group.factors.length} checked`
            : active
              ? `${done - start} / ${group.factors.length}`
              : `${group.factors.length}`}
        </span>
      </div>

      {open && (
        <div className="cw-rise pb-4 pl-[35px]">
          <p className="m-0 mb-2 text-[14px] text-cw-muted">
            {settled ? `Read ${group.source}.` : `Reading ${group.source}…`}
          </p>
          {/* One column, not two. With a value on each row the two-column
              form truncated the longer names ("Competitor densi…"), and a
              single column puts the values in a line under each other -
              which is how this product wants numbers read. */}
          <ul className="m-0 flex max-w-[560px] list-none flex-col gap-y-1 p-0">
            {group.factors.map((f, i) => {
              const idx = start + i;
              const ticked = done > idx;
              const reading = done === idx;
              // Illustrative, and bracketed so it says so. See the module
              // note: these are placeholders until real values are passed in.
              const check = checkFor(f);
              return (
                <li
                  key={f}
                  className={`flex min-h-[36px] items-center gap-3 text-[16px] transition-colors duration-300 ${
                    ticked ? "text-cw-text" : reading ? "text-cw-text" : "text-cw-muted"
                  }`}
                >
                  <span className="flex w-[17px] shrink-0 justify-center">
                    {ticked ? <Tick animate={paced} /> : <Ring active={reading} />}
                  </span>
                  <span className="min-w-0 flex-grow truncate font-cw-mono">{f}</span>
                  {ticked && check && (
                    <span
                      className={`shrink-0 font-cw-mono text-[14px] tabular-nums ${
                        check.unverified ? "text-cw-accent" : "text-cw-muted"
                      }`}
                    >
                      {check.unverified ? check.value : illustrative(check.value)}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </li>
  );
}
