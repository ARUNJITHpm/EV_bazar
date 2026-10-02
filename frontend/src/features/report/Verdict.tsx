import type { ReportPayload, Verdict as VerdictValue } from "./payload";
import { Callout, Section } from "./parts";

/**
 * 01 — one word, before any statistics. Driven by P10, never P50
 * (OVERVIEW.md §3).
 *
 * Track B · R3 rebuilt this section around the sample's strongest page: a
 * full-width dark block carrying the word and a plain subtitle, then the
 * lead sentence in large serif, what the word means for the reader's money,
 * the one caveat worth reading on for, and what to actually do next.
 *
 * TWO DECISIONS ARE FROZEN HERE, and both are about not letting anything
 * except the word carry the verdict.
 *
 * 1. **All three verdicts sit on the same dark ground.** The word used to be
 *    set in green / amber / red. It no longer is — a BUILD in green reads as
 *    an endorsement, and a document that has to survive a monochrome
 *    photocopy in a bank file cannot spend its only colour on the one thing
 *    the reader will never misread. Colour may agree with a judgement
 *    elsewhere (section 04's direction marks); here the word decides alone.
 * 2. **`conditional` prints as CONDITIONAL, not "BUILD — CONDITIONAL".** At
 *    this size the old label's first word is the whole glance, and the whole
 *    glance said BUILD. The sample's answer to the same problem is the word
 *    MODERATE; adopting that is a rename across `data.ts`, the console and
 *    the API enum, so it is a product decision parked with R5's vocabulary,
 *    not something to slip in behind a stylesheet. Dropping the misleading
 *    prefix needs no rename anywhere.
 */

const WORD: Record<VerdictValue, string> = {
  build: "BUILD",
  conditional: "CONDITIONAL",
  dont: "DON’T BUILD",
};

/** The block's second line: what the word licenses, in six words or fewer. */
const SUBTITLE: Record<VerdictValue, string> = {
  build: "A strong starting point",
  conditional: "Build only after the conditions are met",
  dont: "Protect your money at this location",
};

/**
 * What the word means for the reader's money, in plain language — the
 * paragraph `console/Concept.tsx` promises this section carries.
 *
 * Each one used to close on "the rest of this document shows the working,
 * including the factors that argued against it". R3 cut that clause from all
 * three: THE MAIN REASON TO KEEP READING now says the same thing four lines
 * below, and says it about this site rather than in general.
 */
const MEANING: Record<VerdictValue, string> = {
  build:
    "This means the site should earn back what it costs to build even if demand lands at the low end of what we expect.",
  conditional:
    "This means the site pays for itself if demand lands where we expect, but not if it lands at the low end. Building it is a bet on the central case — or on a fleet or campus contract that removes the bet.",
  dont: "This means the site, as it stands, would not earn back what it costs to build — not because of any one thing, but because the numbers do not add up at this cost structure and price.",
};

/** The action, not the assessment — and in every case a step short of
 *  spending, because a report is not a purchase order. */
const NEXT_MOVE: Record<VerdictValue, string> = {
  build:
    "Get power, access and the operator contract confirmed in writing, then release the money in stages. A positive report is not permission to buy equipment.",
  conditional:
    "Do not commit the build cost yet. Answer the conditions in section 08 in writing first — a fleet or campus contract is the cheapest way to remove the bet.",
  dont: "Do not spend on this location. Take section 08 to the next site: most of what failed here is a fact about the road and the grid, not about you.",
};

/**
 * THE MAIN REASON TO KEEP READING — the one caveat that changes how the word
 * above should be read.
 *
 * Chosen from the payload rather than written per site, so it cannot quietly
 * stop being true when the data moves. Nothing here is recomputed
 * (AGENTS.md rule 9): the checks are counted, never re-judged.
 *
 * The order is what a reader would ask in order:
 *
 *   · On a NO, the reason to read on is the case FOR the site. Twelve
 *     favourable checks that lost is the anti-bias promise this document
 *     makes, and burying it would be the exact failure section 04 exists to
 *     prevent.
 *   · Otherwise, whatever is still open outranks whatever is settled — an
 *     unverified check is a bill that has not arrived yet.
 *   · Then the demand band, if it is modelled rather than measured.
 *   · Then, on a payload where nothing is open at all, the weight of the
 *     evidence against.
 */
function mainReason(payload: ReportPayload): string {
  const facts = payload.site_facts;
  const total = facts.length;

  // Unverified is excluded here for the same reason section 04's balance
  // line excludes it: a check nobody has confirmed has not argued in the
  // site's favour, and this sentence sends the reader straight to that line.
  const favours = facts.filter((f) => f.direction === "favours" && !f.unverified).length;
  if (payload.verdict.value === "dont" && favours > 0) {
    return `${favours} of the ${total} checks argued in this site’s favour, and section 04 prints every one of them at full weight. Section 08 says what would have to change for them to win.`;
  }

  const open = facts.filter((f) => f.unverified);
  const named = open.slice(0, 2).map((f) => f.label.toLowerCase());
  if (named.length > 0) {
    return `${open.length} of the ${total} checks are still unverified — ${named.join(" and ")}${
      open.length > named.length ? " among them" : ""
    }. Confirm them before committing money.`;
  }

  if (payload.predicted.modelled_not_measured) {
    return `The demand band is modelled (${payload.predicted.model_version}), not measured at this site. Section 09 shows how wide that leaves the answer.`;
  }

  const against = facts.filter((f) => f.direction === "against" && !f.unverified).length;
  return `${against} of the ${total} checks argued against this site. Section 04 lists every one of them.`;
}

export function Verdict({ payload }: { payload: ReportPayload }) {
  const { verdict } = payload;
  return (
    <Section num="01" title="Verdict" heading="The answer, in one word." id="verdict">
      {/* `break-inside: avoid` in print.css: the word and its subtitle are one
          object, and a page break between them would leave a page ending on a
          shout. */}
      <div
        data-verdict-block
        className="bg-cw-paper-head px-[clamp(22px,4vw,44px)] py-[clamp(22px,3.4vw,34px)]"
      >
        <p className="m-0 font-cw-sans text-[clamp(36px,7vw,60px)] leading-[1] font-bold tracking-[-0.02em] text-cw-paper">
          {WORD[verdict.value]}
        </p>
        <p className="mt-3.5 mb-0 text-[clamp(17px,2.2vw,21px)] leading-[1.35] text-cw-paper-head-dim">
          {SUBTITLE[verdict.value]}
        </p>
      </div>

      <p className="mt-6 mb-0 max-w-[54ch] text-[clamp(21px,2.9vw,27px)] leading-[1.3]">
        {verdict.reason}
      </p>
      <p className="mt-4 mb-0 max-w-[70ch] text-[17px] leading-[1.6] text-cw-paper-muted">
        {MEANING[verdict.value]}
      </p>

      <p className="mt-5 mb-0 font-cw-mono text-[12px] font-medium tracking-[0.1em] text-cw-paper-slate uppercase">
        The main reason to keep reading
      </p>
      <p className="mt-2 mb-0 max-w-[70ch] text-[17px] leading-[1.55]">{mainReason(payload)}</p>

      <div className="mt-5">
        <Callout label="Your next move">
          <p>{NEXT_MOVE[verdict.value]}</p>
        </Callout>
      </div>
    </Section>
  );
}
