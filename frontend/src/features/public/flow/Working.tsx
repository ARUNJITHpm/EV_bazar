import { useCallback, useEffect, useRef, useState } from "react";

/**
 * The working screen. It shows the REAL request, however short.
 *
 * design/IMPLEMENT.md is explicit that a padded progress bar is the one
 * element that would undo everything this product argues, and the reference
 * build's own stub padded itself with `setTimeout(900 + random * 900)`. So
 * there are no timers here: the checks below are the sources the request
 * genuinely consults, the first is marked active while the POST is in
 * flight, and every one resolves the moment the response lands. If the
 * assessment returns in two seconds, the screen lasts two seconds.
 */

const CHECKS = [
  "Your pin, placed in its district",
  "The state electricity regulator's EV tariff order",
  "Sanctioned load and demand charges",
  "Fixed costs against the assumed selling price",
  "How much we actually know about this state",
];

function Tick() {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="text-cw-positive"
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
      strokeWidth="1.7"
      aria-hidden="true"
      className={active ? "text-cw-slate" : "text-cw-line"}
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
  const started = useRef(false);
  const alive = useRef(true);
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
        if (ok) {
          setSettled(true);
          latest.current.onDone();
        } else setFailed(true);
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

  return (
    <div className="flex max-w-[880px] flex-col gap-[clamp(32px,5vw,44px)]">
      <div className="flex flex-col gap-3.5">
        <h1 className="text-[clamp(28px,4vw,40px)] leading-[1.15] font-medium">
          Checking this location against the live records.
        </h1>
        <p className="max-w-[640px] text-cw-muted">
          Whatever this takes is what it takes — nothing here is waiting for effect.
        </p>
      </div>

      <ol role="status" aria-live="polite" className="m-0 list-none p-0">
        {CHECKS.map((c, i) => (
          <li
            key={c}
            className={`flex items-center gap-[18px] border-b border-cw-line py-[17px] transition-colors duration-300 ${
              settled ? "text-cw-text" : i === 0 ? "text-cw-text" : "text-cw-muted"
            }`}
          >
            <span className="flex shrink-0">{settled ? <Tick /> : <Ring active={i === 0} />}</span>
            <span className="font-cw-mono text-[17px]">{c}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
