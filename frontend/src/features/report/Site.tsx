import type { ReactNode } from "react";

import type { Direction, ReportPayload, SiteFact } from "./payload";
import { DirectionMark, Footnote, Note, SRC, Section, TH, Table } from "./parts";
import { SiteMap } from "./SiteMap";

/**
 * 04 — the evidence, and the longest section in the document. The site in two
 * pictures, then every check assessed: what it is, what we found, and — since
 * Track B · R4 — **what it means**, in one plain sentence per check.
 *
 * THE SENTENCE IS THE SECTION. A reader who does not already build charging
 * stations cannot tell whether "9 m turning radius" is good news, and a table
 * of readings they cannot interpret is a table they skip — which is how a
 * document that shows its working gets read as a document that hides it. The
 * sentence comes from the payload (`SiteFact.means`), written once per check
 * rather than once per site, so it says why the check is on the list at all
 * and stays true when the value moves.
 *
 * FOUR STATES, NOT THREE. Unverified is no longer a chip beside the value; it
 * REPLACES the direction mark. A check nobody has confirmed has not argued
 * anything yet, so it is counted separately in the balance line too — the
 * four numbers add up to the check count, and each matches a mark printed on
 * the page.
 *
 * DEGRADING CLEANLY, in three steps, because this section outlives its
 * payloads:
 *
 *   · no `means`  — the sentence is omitted, the mark stays;
 *   · no direction — the third column goes entirely, and so does the balance
 *     line, rather than pretending to a tally the data cannot support;
 *   · no `group`  — one flat table under a generic chapter.
 *
 * Favourable checks on a rejected site are printed at equal weight and
 * counted in the balance line. Suppressing them is the bias this section
 * exists to disprove.
 */

/* -------------------------------------------------------------------------
 * Chapters. The 34 checks answer three questions, and a reader looking for
 * one of them should not have to know which of the five SOURCE groups holds
 * it. The groups are how the data is fetched (one group is one real fetch,
 * the discipline `features/animation/data.ts` owns); the chapters are how the
 * answer is read. Both are printed — the chapter as the question, the group
 * as the subhead over its own table.
 * ---------------------------------------------------------------------- */

interface Chapter {
  question: string;
  standfirst: string;
  /** Source groups, in the order they should print under this question. */
  groups: string[];
  footnote: ReactNode;
}

const CHAPTERS: Chapter[] = [
  {
    question: "Can drivers get in and out?",
    standfirst:
      "A good road nearby is not enough. Every one of these is about the entrance itself — whether a driver who wants to stop here is able to.",
    groups: ["Access and geometry"],
    footnote: (
      <>
        <b>+ favours · = neutral · − against</b> describe which way a check argued, not a pass mark;
        a site can fail on a check that argues for it. Road and plot dimensions here are
        measurements taken from mapping data, <b>not safety standards</b> — only a licensed survey
        clears an entrance for construction.
      </>
    ),
  },
  {
    question: "Customers, and electricity.",
    standfirst:
      "A charger needs the right vehicles within reach and a connection that can feed them. These two groups are the demand side and the cost side of the same sale.",
    groups: ["Demand", "Power and tariff"],
    footnote: (
      <>
        Registrations count <b>every vehicle registered in the district</b> — not EVs on this road,
        and not customers. Tariff, spare capacity and any subsidy are confirmed by the discom and
        the state, never by us; until they are, they carry the unverified mark.
      </>
    ),
  },
  {
    question: "A place people will choose.",
    standfirst:
      "Waiting comfort, rent and the competition are what turn a promising plot into an expensive one. A driver with a choice will make it here.",
    groups: ["Site and amenities", "Competition"],
    footnote: (
      <>
        Station counts do not prove uptime — <b>a competitor that is down is not competition</b>,
        and this version does not measure that. Announced stations are intentions, not concrete.
      </>
    ),
  },
];

/** Anything the chapters do not claim still prints, under its own heading —
 *  a check that has been added to the assembler and not yet to this list must
 *  never silently vanish from the page. */
const FALLBACK: Chapter = {
  question: "Everything else we checked.",
  standfirst: "Checks that do not yet sit under one of the three questions above.",
  groups: [],
  footnote: <>Direction describes which way a check argued, not a pass mark.</>,
};

const FLAT_GROUP = "Site facts";

interface Group {
  name: string;
  /** 1-based position in the payload's own group order — the "GROUP 3" of the
   *  subhead, and stable regardless of which chapter prints it. */
  index: number;
  rows: NumberedFact[];
}

interface NumberedFact extends SiteFact {
  /** 1-based position across the whole check list: the "07" of "07 Turning
   *  radius". Counted over the payload, so a 16-check report numbers 01–16
   *  and never claims a 34-check set it does not have. */
  n: number;
}

function groupFacts(facts: SiteFact[]): Group[] {
  const groups: Group[] = [];
  facts.forEach((f, i) => {
    const name = f.group ?? FLAT_GROUP;
    const g = groups.find((x) => x.name === name);
    const row: NumberedFact = { ...f, n: i + 1 };
    if (g) g.rows.push(row);
    else groups.push({ name, index: groups.length + 1, rows: [row] });
  });
  return groups;
}

/** Chapters paired with the groups actually present, in payload order.
 *  A chapter whose groups are all missing does not print at all. */
function chaptersFor(groups: Group[]): { chapter: Chapter; groups: Group[] }[] {
  const claimed = new Set<string>();
  const out: { chapter: Chapter; groups: Group[] }[] = [];
  for (const chapter of CHAPTERS) {
    const mine = chapter.groups
      .map((name) => groups.find((g) => g.name === name))
      .filter((g): g is Group => g !== undefined);
    mine.forEach((g) => claimed.add(g.name));
    if (mine.length > 0) out.push({ chapter, groups: mine });
  }
  const rest = groups.filter((g) => !claimed.has(g.name));
  if (rest.length > 0) out.push({ chapter: FALLBACK, groups: rest });
  return out;
}

interface Balance extends Record<Direction, number> {
  unverified: number;
}

/** The four counts that add to the check total. Unverified is taken out of
 *  the direction counts, not added on top of them, so the line matches the
 *  marks on the page row for row. Null when any check has no direction at
 *  all — a partial tally would be worse than none. */
function balance(facts: SiteFact[]): Balance | null {
  const b: Balance = { favours: 0, against: 0, neutral: 0, unverified: 0 };
  for (const f of facts) {
    if (f.unverified) {
      b.unverified += 1;
      continue;
    }
    if (!f.direction) return null;
    b[f.direction] += 1;
  }
  return b;
}

export function Site({ payload }: { payload: ReportPayload }) {
  const { site, site_facts } = payload;
  const groups = groupFacts(site_facts);
  const chapters = chaptersFor(groups);
  const counts = balance(site_facts);
  const first = chapters[0];
  /** One chapter holding one unnamed group is a legacy payload: print the
   *  table alone rather than a question it was never written to answer. */
  const flat = chapters.length === 1 && first !== undefined && first.groups[0]?.name === FLAT_GROUP;

  return (
    <Section
      num="04"
      title="The site"
      heading="Everything we checked, and which way it argued."
      id="site"
    >
      <p className="m-0 text-[20px] leading-[1.4]">
        {site.name} <span className="text-cw-paper-muted">— {site.line}</span>
      </p>
      <p className="mt-1 mb-6 font-cw-mono text-[13px] text-cw-paper-muted">
        {site.lat.toFixed(4)}, {site.lng.toFixed(4)} · LGD district {site.lgd_district_code} ·
        archetype {site.archetype} · data tier {site.data_tier}
      </p>

      <SiteMap lat={site.lat} lng={site.lng} name={site.name} />

      {counts && (
        <div className="mt-10 mb-2.5 border border-cw-ink px-[18px] py-3.5 font-cw-mono text-[15px] tabular-nums">
          {site_facts.length} checks — {counts.favours} favourable, {counts.against} against,{" "}
          {counts.neutral} neutral, {counts.unverified} still unverified
        </div>
      )}
      <Note className="mb-2">
        Checks that argued in this site’s favour are listed at equal weight, whatever the verdict.
        Suppressing them is the bias this section exists to disprove. A check marked{" "}
        <span className="font-cw-mono text-[13px] text-cw-caution-text">? UNVERIFIED</span> is an
        assumption or a pending fetch — it has not argued either way, and is not counted as though
        it had.
      </Note>

      {chapters.map(({ chapter, groups: mine }) => (
        <ChapterBlock
          key={chapter.question}
          chapter={chapter}
          groups={mine}
          bare={flat}
          withDirection={counts !== null}
        />
      ))}
    </Section>
  );
}

function ChapterBlock({
  chapter,
  groups,
  bare,
  withDirection,
}: {
  chapter: Chapter;
  groups: Group[];
  /** Legacy flat payload: no question, no subheads, no footnote. */
  bare: boolean;
  withDirection: boolean;
}) {
  const from = groups[0]?.rows[0]?.n;
  const last = groups[groups.length - 1]?.rows;
  const to = last?.[last.length - 1]?.n;

  return (
    <div className="mt-9">
      {!bare && (
        <>
          <p className="m-0 font-cw-mono text-[12px] tracking-[0.1em] text-cw-paper-muted uppercase">
            {from !== undefined && to !== undefined ? `Checks ${pad(from)}–${pad(to)}` : "Checks"}
          </p>
          <h3 className="mt-1.5 mb-0 text-[clamp(21px,2.6vw,25px)] leading-[1.2] font-normal">
            {chapter.question}
          </h3>
          <Note className="mt-2 mb-0">{chapter.standfirst}</Note>
        </>
      )}

      {groups.map((g) => (
        <div key={g.name} className="mt-5">
          {!bare && groups.length > 1 && (
            <h4 className="mt-0 mb-2 font-cw-mono text-[12px] font-medium tracking-[0.12em] text-cw-paper-slate uppercase">
              Group {g.index} / {g.name} / {g.rows.length} checks
            </h4>
          )}
          <Table minWidth="34rem">
            <thead>
              <tr>
                {/* The means column takes what is left, and is meant to be
                    the widest: it is the only one a reader who does not build
                    charging stations can actually use. */}
                <th className={`${TH} w-[10.5rem]`}>Check</th>
                <th className={`${TH} w-[12.5rem]`}>What we found</th>
                {withDirection && <th className={TH}>What it means</th>}
              </tr>
            </thead>
            <tbody>
              {g.rows.map((f) => (
                <tr key={f.label}>
                  <td className={CELL}>
                    <span className="font-cw-mono text-[14px] text-cw-paper-muted tabular-nums">
                      {pad(f.n)}
                    </span>{" "}
                    {f.label}
                  </td>
                  <td className={CELL}>
                    {f.value}
                    <span className={`mt-0.5 block ${SRC}`}>{f.source}</span>
                  </td>
                  {withDirection && (
                    <td className={CELL}>
                      <DirectionMark direction={f.direction} unverified={f.unverified} />
                      {f.means && (
                        <span className="mt-0.5 block text-[15px] leading-[1.45]">{f.means}</span>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      ))}

      {!bare && <Footnote>{chapter.footnote}</Footnote>}
    </div>
  );
}

const pad = (n: number) => String(n).padStart(2, "0");

/**
 * Section 04's cell, spelled out rather than composed from the shared `TD`.
 *
 * Two reasons, and the second is the one that bites. First: 34 rows means
 * every point of padding and leading is paid 34 times, so this is the one
 * table in the document that earns a tighter row and 15px body — the same
 * size as the sentence beside it, so a row reads as one block rather than a
 * caption under a headline. Second: `TD` sets `text-[17px]`, and an override
 * appended after it does NOT reliably win — two Tailwind utilities of equal
 * specificity are resolved by their order in the generated stylesheet, not by
 * the order they appear in the class attribute. Composing looked like it
 * worked and silently did nothing.
 */
const CELL =
  "border-b border-cw-rule px-3 py-2 align-top text-[15px] leading-[1.4] first:pl-3.5 last:pr-3.5";
