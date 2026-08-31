import { type ReactNode } from "react";

/**
 * The question screens' shared parts.
 *
 * Non-negotiables from design/IMPLEMENT.md, all enforced here rather than
 * remembered per screen: one question per screen, NO DROPDOWNS anywhere in
 * the flow, and a 56px minimum tap target because the owner may be standing
 * at the site holding a phone.
 */

export function Screen({ question, children }: { question: string; children: ReactNode }) {
  return (
    <div className="flex max-w-[940px] flex-col gap-[clamp(32px,5vw,44px)]">
      <h1 className="max-w-[820px] text-[clamp(30px,4.6vw,46px)] leading-[1.15] font-medium text-pretty">
        {question}
      </h1>
      {children}
    </div>
  );
}

export function Answers({ children, cols = 2 }: { children: ReactNode; cols?: 2 | 3 }) {
  return (
    <div
      className="grid gap-5"
      style={{
        gridTemplateColumns: `repeat(auto-fit, minmax(min(100%, ${cols === 3 ? 260 : 320}px), 1fr))`,
      }}
    >
      {children}
    </div>
  );
}

export function Answer({
  title,
  sub,
  onClick,
}: {
  title: string;
  sub: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-[56px] flex-col justify-center gap-3 border border-cw-line bg-cw-surface p-8 text-left text-cw-text transition-colors duration-200 hover:border-cw-slate hover:bg-cw-surface-2"
    >
      <span className="text-[22px] leading-[1.3] font-medium tracking-[-0.015em]">{title}</span>
      <span className="text-cw-muted">{sub}</span>
    </button>
  );
}

/** Native range input: keyboard arrows keep working, and the thumb is sized
 *  for a thumb (styling lives in index.css under .cw-surface-root). */
export function Slider({
  id,
  label,
  value,
  min,
  max,
  step,
  unit,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex flex-col gap-4 border border-cw-line bg-cw-surface p-6 sm:px-9 sm:py-8">
      <div className="flex flex-wrap items-baseline justify-between gap-5">
        <label htmlFor={id} className="text-[20px] font-medium">
          {label}
        </label>
        <div className="flex items-baseline gap-2">
          <span className="font-cw-mono text-[clamp(30px,5vw,40px)] font-medium tracking-[-0.02em] tabular-nums">
            {value}
          </span>
          <span className="font-cw-mono text-[18px] text-cw-muted">{unit}</span>
        </div>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-valuetext={`${value} ${unit}`}
      />
    </div>
  );
}

export function StepFooter({
  onSkip,
  onNext,
  skipLabel = "I don’t know this one — skip it",
  nextLabel = "Continue",
}: {
  onSkip: () => void;
  onNext: () => void;
  skipLabel?: string;
  nextLabel?: string;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <button
        type="button"
        onClick={onSkip}
        className="inline-flex min-h-[56px] items-center text-[17px] text-cw-muted transition-colors duration-200 hover:text-cw-text"
      >
        {skipLabel}
      </button>
      <button
        type="button"
        onClick={onNext}
        className="inline-flex min-h-[58px] items-center justify-center bg-cw-accent px-7 text-[17px] font-semibold text-cw-ground transition-[filter] duration-200 hover:brightness-107"
      >
        {nextLabel}
      </button>
    </div>
  );
}

export function Aside({ children }: { children: ReactNode }) {
  return <p className="max-w-[720px] text-cw-muted">{children}</p>;
}
