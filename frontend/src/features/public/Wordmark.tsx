/**
 * The Chargeworthy wordmark, Direction C - Worthy (design/brand/mark/): one
 * word in Newsreader, the weight stepping up on "worthy". Size and colour
 * come from the caller; the face and the split do not. The two spans sit
 * with no space between them, so the word is still read as one.
 */
export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-cw-wordmark tracking-[-0.01em] ${className}`}>
      <span className="font-normal">Charge</span>
      <span className="font-semibold">worthy</span>
    </span>
  );
}
