import { CW_MARK_BOX, CW_MARK_PATH } from "./cwMarkGlyphs";

/**
 * The Cw mark on paper: board C's "32 light" (design/brand/mark/) - paper
 * ground, a rule border, slate letters. The favicon is the dark version of
 * the same glyphs. Drawn inline rather than loaded as an image, so it prints
 * as vectors in the archived PDF, waits on no request before the render, and
 * takes its colours from the tokens. Decorative: the wordmark beside it
 * already says the name.
 */
export function CwMark({ className = "" }: { className?: string }) {
  const b = CW_MARK_BOX;
  return (
    <svg
      viewBox={`0 0 ${b} ${b}`}
      aria-hidden="true"
      focusable="false"
      className={`shrink-0 ${className}`}
    >
      <rect
        x="0.5"
        y="0.5"
        width={b - 1}
        height={b - 1}
        rx="5.5"
        className="fill-cw-paper stroke-cw-rule"
        strokeWidth="1"
      />
      <path d={CW_MARK_PATH} className="fill-cw-paper-slate" />
    </svg>
  );
}
