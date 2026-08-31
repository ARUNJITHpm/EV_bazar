import { useEffect, useRef, useState } from "react";

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
  onFailed,
}: {
  /** The real assessment call. Resolves true when the answer is stored. */
  run: () => Promise<boolean>;
  onDone: () => void;
  onFailed: () => void;
}) {
  const [settled, setSettled] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let alive = true;
    void run().then((ok) => {
      if (!alive) return;
      setSettled(true);
      if (ok) onDone();
      else onFailed();
    });
    return () => {
      alive = false;
    };
  }, [run, onDone, onFailed]);

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
