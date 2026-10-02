import type { ReactNode } from "react";

import type { Direction as DirectionValue } from "./payload";

/**
 * The report's shared parts — one section head, one figure, one chip, one
 * direction marker — so the twelve sections read as one document rather
 * than twelve components that happen to share a page.
 *
 * Paper palette throughout (tokens.css, the cw-paper block). Prose is serif
 * at 17px; every number is monospace with tabular figures; sections are
 * separated by a single ink rule, never a card. Nothing here carries meaning
 * by colour alone: the verdict is a word, a direction is a sign plus a word,
 * an unverified value is a chip that prints as text.
 *
 * Track B · R2 rebuilt the section head and added StatCard, Callout and
 * Footnote. The reason they live here rather than in the twelve components
 * is that the sample document's consistency is structural — the same eyebrow,
 * the same serif sentence, the same table head on every page — and
 * consistency held by twelve files agreeing with each other is consistency
 * that lasts until the thirteenth edit.
 */

export function Section({
  num,
  title,
  heading,
  standfirst,
  id,
  children,
}: {
  num: string;
  /** The section's formal name. Appears only in the eyebrow and the print
   *  running head — never as the visible heading. */
  title: string;
  /**
   * The visible heading: a plain sentence, in serif, at reading size. This
   * is the single biggest change R2 makes. "The money, in simple terms."
   * tells a landowner what the page is; "WHAT THIS MEANS FOR YOUR MONEY" in
   * 13px mono tells them a filing system exists.
   */
  heading: string;
  /** One muted line under the heading, where the section needs a caveat or a
   *  scope note before the reader reaches the data. */
  standfirst?: string;
  id: string;
  children: ReactNode;
}) {
  return (
    <section id={id} data-report-section={id} className="mt-11">
      <div className="mb-4 border-t border-cw-ink pt-3">
        <p className="m-0 font-cw-mono text-[13px] tracking-[0.1em] text-cw-paper-slate uppercase">
          <span>{num}</span>
          <span className="mx-2 text-cw-rule" aria-hidden="true">
            /
          </span>
          <span>{title}</span>
        </p>
        <h2 className="mt-2.5 mb-0 text-[clamp(25px,3.4vw,32px)] leading-[1.15] font-normal tracking-[-0.01em]">
          {heading}
        </h2>
        {standfirst && (
          <p className="mt-2.5 mb-0 max-w-[68ch] text-[16px] leading-[1.55] text-cw-paper-muted">
            {standfirst}
          </p>
        )}
      </div>
      {children}
    </section>
  );
}

/** A quiet explanatory line under a heading or a table. */
export function Note({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <p className={`m-0 max-w-[70ch] text-[15px] leading-[1.6] text-cw-paper-muted ${className}`}>
      {children}
    </p>
  );
}

/**
 * The line that closes a table by taking something back — "Station counts do
 * not prove uptime", "All vehicles, not all EVs or customers".
 *
 * It is a separate part from `Note` because it has a job `Note` does not: a
 * table without one reads as a complete answer, and none of ours are. Small,
 * muted, and directly under the rule so it is unmistakably about the table
 * above rather than the prose below.
 */
export function Footnote({ children }: { children: ReactNode }) {
  return (
    <p className="mt-2.5 mb-0 max-w-[74ch] text-[14px] leading-[1.55] text-cw-paper-muted">
      {children}
    </p>
  );
}

/** A large monospace figure with a serif label — the money section's unit. */
export function Figure({
  label,
  value,
  small = false,
  detail,
}: {
  label: string;
  value: string;
  small?: boolean;
  detail?: string;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="text-[15px] text-cw-paper-muted">{label}</span>
      <span
        className={`font-cw-mono leading-[1.2] font-medium tabular-nums ${
          small ? "text-[clamp(19px,2.4vw,22px)]" : "text-[clamp(24px,3.4vw,30px)]"
        }`}
      >
        {value}
      </span>
      {detail && <span className="text-[14px] text-cw-paper-muted">{detail}</span>}
    </div>
  );
}

/**
 * A figure that has been lifted out of the prose because the reader will look
 * for it first — setup budget, cash per month. `Figure` is for a number in a
 * row of numbers; this is for the one or two a page is built around.
 *
 * The tint prints: `print-color-adjust` is set on the paper block in
 * index.css, because a stat card that loses its ground on paper loses the
 * only thing that made it a card.
 */
export function StatCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="min-w-0 flex-1 basis-[min(100%,15rem)] bg-cw-paper-tint px-5 py-4">
      <p className="m-0 font-cw-mono text-[12px] font-medium tracking-[0.1em] text-cw-paper-muted uppercase">
        {label}
      </p>
      <p className="mt-2 mb-0 font-cw-mono text-[clamp(23px,3.2vw,29px)] leading-[1.15] font-medium tabular-nums">
        {value}
      </p>
      {detail && <p className="mt-1.5 mb-0 text-[14px] text-cw-paper-muted">{detail}</p>}
    </div>
  );
}

/** Stat cards sit in pairs or threes and wrap on a narrow screen. */
export function StatCards({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap gap-3">{children}</div>;
}

/**
 * A block the reader must not skim past: a left rule, a tint, a small
 * uppercase label, and the sentence.
 *
 * Two tones only. `neutral` is an instruction — "YOUR NEXT MOVE". `caution`
 * is something that costs money if missed — "READ THIS BEFORE SIGNING". The
 * left rule carries the distinction as thickness and position, not colour
 * alone, so it survives a monochrome photocopy.
 */
export function Callout({
  label,
  tone = "neutral",
  children,
}: {
  label: string;
  tone?: "neutral" | "caution";
  children: ReactNode;
}) {
  const caution = tone === "caution";
  return (
    <aside
      data-callout
      className={`border-l-[3px] py-3 pr-5 pl-5 ${
        caution ? "border-cw-caution bg-cw-caution-tint" : "border-cw-paper-slate bg-cw-paper-tint"
      }`}
    >
      <p
        className={`m-0 font-cw-mono text-[12px] font-medium tracking-[0.1em] uppercase ${
          caution ? "text-cw-caution-text" : "text-cw-paper-slate"
        }`}
      >
        {label}
      </p>
      <div className="mt-2 max-w-[70ch] text-[16px] leading-[1.55] [&>p]:m-0 [&>p+p]:mt-2.5">
        {children}
      </div>
    </aside>
  );
}

/**
 * UNVERIFIED / ESTIMATED — caution tint, and legible as plain text once the
 * colour is stripped.
 *
 * `wrap` is for the one caller whose chip carries a VALUE rather than a
 * fixed word: section 11's provenance grid, where the text is a payload
 * field — `competitor fetch` is whatever the fetcher called itself — and can
 * be any length. Today's values all fit; `nowrap` is what would make a
 * longer one leave the page instead of taking a second line (Track B · R10).
 * Everywhere else the chip is a label of one or three words and must not
 * break mid-phrase, so nowrap stays the default.
 */
export function Chip({ children, wrap = false }: { children: ReactNode; wrap?: boolean }) {
  return (
    <span
      className={`inline-block bg-cw-caution-tint px-2 py-0.5 font-cw-mono text-[12px] tracking-[0.08em] text-cw-caution-text uppercase ${
        wrap ? "max-w-full whitespace-normal [overflow-wrap:anywhere]" : "whitespace-nowrap"
      }`}
    >
      {children}
    </span>
  );
}

const DIRECTION: Record<DirectionValue, { sign: string; word: string; ink: string }> = {
  favours: { sign: "+", word: "FAVOURS", ink: "text-cw-verdict-positive" },
  against: { sign: "−", word: "AGAINST", ink: "text-cw-verdict-negative" },
  neutral: { sign: "=", word: "NEUTRAL", ink: "text-cw-paper-muted" },
};

/** The fourth state (Track B · R4). It is not a direction — it is the
 *  absence of one, which is why it REPLACES the mark rather than sitting
 *  beside it. A check nobody has confirmed has not argued anything yet, and
 *  a page that counted it as favourable would be flattering itself. */
const UNVERIFIED = { sign: "?", word: "UNVERIFIED", ink: "text-cw-caution-text" };

export function DirectionMark({
  direction,
  unverified = false,
}: {
  direction?: DirectionValue | null;
  unverified?: boolean;
}) {
  const d = unverified ? UNVERIFIED : direction ? DIRECTION[direction] : null;
  if (!d) return null;
  return (
    <span
      className={`font-cw-mono text-[13px] tracking-[0.08em] whitespace-nowrap ${d.ink}`}
      aria-label={d.word.toLowerCase()}
    >
      <span className="inline-block w-[1.1em] font-medium">{d.sign}</span>
      {d.word}
    </span>
  );
}

/* Table cells. Columns must not touch: "Northbound only" running into the
 * factor name is what makes a dense table unreadable.
 *
 * R2 gave the head a dark ground. The reason is scanning, not decoration: on
 * a page carrying four tables, a hairline under the head row does not tell
 * you where the next table starts, and a reader looking for one figure has to
 * re-read every heading. `TH` keeps its own padding so a head cell still
 * works in a table that opts out of the ground. */
export const TH =
  "bg-cw-paper-head px-3 py-2 text-left align-bottom font-cw-mono text-[12px] font-medium tracking-[0.1em] text-cw-paper uppercase first:pl-3.5 last:pr-3.5";
export const TD =
  "border-b border-cw-rule px-3 py-2.5 align-top text-[17px] first:pl-3.5 last:pr-3.5";
export const NUM = "text-right font-cw-mono tabular-nums";
export const SRC = "text-[15px] text-cw-paper-muted";

/**
 * `minWidth` is the width below which the table scrolls on screen rather
 * than crushing its columns — and it is also a print constraint, because A4
 * less the 14 mm margins leaves about 688px and a wider table on paper is
 * CUT OFF, not scrolled. Keep it under 42rem.
 */
export function Table({
  children,
  minWidth = "0",
  zebra = true,
}: {
  children: ReactNode;
  minWidth?: string;
  /** Off for the short two- and three-row tables, where banding is noise. */
  zebra?: boolean;
}) {
  return (
    <div tabIndex={0} role="group" aria-label="Scrollable report table" className="overflow-x-auto">
      <table
        className={`w-full border-collapse ${
          zebra ? "[&>tbody>tr:nth-child(even)]:bg-cw-paper-zebra" : ""
        }`}
        style={{ minWidth }}
      >
        {children}
      </table>
    </div>
  );
}
