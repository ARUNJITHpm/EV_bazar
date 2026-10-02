import { GridConditions } from "./GridConditions";
import { formatRupeesPrecise } from "../../lib/money";
import { formatUtilisation } from "../../lib/units";
import { HORIZON_YEARS, scenarioFor, type ReportPayload } from "./payload";
import { Callout, Footnote, NUM, Section, TD, TH, Table } from "./parts";

/**
 * 08 — the levers, and the number each one has to move past. This section is
 * why a reader trusts a no: it proves the verdict is conditional on
 * evidence, not on disposition.
 *
 * Every row is built from figures already in the payload — the two breakeven
 * lines, the price-sensitivity points, the fleet-anchor run. Nothing here is
 * a new number.
 *
 * THREE THINGS TRACK B · R7 CHANGED, each a gap the sample document exposed
 * rather than a restyling.
 *
 * 1. **The rows are named levers now, not bare conditions.** A left column of
 *    short noun phrases is what makes the table scannable; the sentence
 *    carrying the number belongs beside the name, not as the name.
 * 2. **The build-cost line became a lever.** R5 added the second breakeven
 *    and R6 printed ten years of running total against the build cost, and
 *    this section still asked only whether the site covers its bills. On the
 *    BUILD fixture the downside case clears the bills line and is ₹1.94 L
 *    short over ten years — precisely the fact a reader deserves as a
 *    checkable condition rather than as a surprise in section 05. No verdict
 *    is measured against this line, so the cell beside it shows the whole
 *    band rather than the one case a rule would pick.
 * 3. **A contract only counts if it is additional.** The sample gives this a
 *    lever of its own ("No double counting") and it is the cheapest mistake
 *    in this document to make: signing a fleet for volume the forecast
 *    already assumed buys nothing and feels like it bought everything.
 *
 * The closing callout is what section 01's YOUR NEXT MOVE promises when it
 * sends the reader here to answer the conditions in writing. It is built
 * from the checks still open on THIS site rather than from a standing list:
 * a report telling a reader to go and confirm something already confirmed
 * has stopped being about their site.
 */

interface Row {
  lever: string;
  condition: string;
  standing: string;
}

const BILLS_LINE = "Demand, against the bills line";
const ANCHOR = "A fleet or campus contract";

function rows(p: ReportPayload): Row[] {
  const out: Row[] = [];
  const be = p.breakeven;
  const { p10, p50, p90 } = p.predicted;
  const f = p.financials;

  if (p.verdict.value === "dont") {
    out.push({
      lever: BILLS_LINE,
      condition: `The central case reaches ${formatUtilisation(be.utilisation)} — about ${be.kwh_day} units a day`,
      standing: `${formatUtilisation(p50)} central`,
    });
  }
  out.push(
    p.verdict.value === "build"
      ? {
          lever: BILLS_LINE,
          condition: `The downside case falls below ${formatUtilisation(be.utilisation)} — that alone would withdraw the verdict`,
          standing: `${formatUtilisation(p10)} downside`,
        }
      : {
          // On a DON'T the row above already names this line, so the second
          // one says which case it is about and reads as a continuation.
          lever: p.verdict.value === "dont" ? "The same line, at the low end" : BILLS_LINE,
          condition: `The downside case reaches ${formatUtilisation(be.utilisation)} — the rule the verdict is measured against`,
          standing: `${formatUtilisation(p10)} downside`,
        },
  );

  if (be.full_cost_utilisation != null && be.full_cost_kwh_day != null) {
    out.push({
      lever: "Demand, against the build-cost line",
      condition: `Demand reaches ${formatUtilisation(be.full_cost_utilisation)} — about ${be.full_cost_kwh_day} units a day — for the setup cost to come back over ${HORIZON_YEARS} years`,
      standing: `${formatUtilisation(p10)} – ${formatUtilisation(p90)} likely`,
    });
  }

  const assumed = f.price_sensitivity.find((x) => x.price_paise_kwh === f.selling_price_paise_kwh);
  const higher = f.price_sensitivity.find((x) => x.price_paise_kwh > f.selling_price_paise_kwh);
  const lower = f.price_sensitivity.find((x) => x.price_paise_kwh < f.selling_price_paise_kwh);
  if (assumed && higher && p.verdict.value !== "build") {
    out.push({
      lever: "The price to the driver",
      condition: `At ${formatRupeesPrecise(higher.price_paise_kwh)}/unit the bills line drops to ${formatUtilisation(higher.breakeven_utilisation)}`,
      standing: `${formatRupeesPrecise(assumed.price_paise_kwh)}/unit assumed`,
    });
  }
  if (assumed && lower && p.verdict.value === "build") {
    out.push({
      lever: "The price to the driver",
      condition: `At ${formatRupeesPrecise(lower.price_paise_kwh)}/unit the bills line rises to ${formatUtilisation(lower.breakeven_utilisation)}`,
      standing: `${formatRupeesPrecise(assumed.price_paise_kwh)}/unit assumed`,
    });
  }

  // Shown on a BUILD too when the downside case misses the build-cost line —
  // which is a data question, not a verdict question, and on the BUILD
  // fixture the answer is yes.
  const short = be.full_cost_utilisation != null && p10 < be.full_cost_utilisation;
  if (p.verdict.value !== "build" || short) {
    const central = scenarioFor(p, "P50");
    out.push({
      lever: ANCHOR,
      condition: `${f.anchor_note.kwh_year.toLocaleString("en-IN")} units a year committed take-or-pay — the central case then returns ${f.anchor_note.irr_pct}%`,
      standing:
        central?.irr_pct == null ? "no contract · no return" : `no contract · ${central.irr_pct}%`,
    });
  }

  if (p.competitors.within_3km > 0) {
    out.push({
      lever: "Competing stations nearby",
      condition: "Any of them closing, filling up or adding fast chargers re-runs the demand band",
      standing: `${p.competitors.within_3km} within 3 km`,
    });
  }
  return out;
}

export function ChangeVerdict({ payload }: { payload: ReportPayload }) {
  const list = rows(payload);
  const anchored = list.some((r) => r.lever === ANCHOR);
  const open = payload.site_facts.filter((f) => f.unverified).map((f) => f.label.toLowerCase());
  // Three at most. A list long enough to skim past is a list nobody acts on,
  // and the full set is section 04's job with the ledger behind it.
  const named = open.slice(0, 3);

  return (
    <Section
      num="08"
      title="What would change this verdict"
      heading="What would change this answer."
      standfirst="Each lever below is checkable, and any one of them would prompt a reassessment. The verdict is conditional on evidence, not on disposition."
      id="change"
    >
      <GridConditions payload={payload} />
      <Table minWidth="36rem">
        <thead>
          <tr>
            <th className={TH}>Lever</th>
            <th className={TH}>Checkable condition</th>
            <th className={`${TH} ${NUM}`}>Where it stands</th>
          </tr>
        </thead>
        <tbody>
          {list.map((r) => (
            <tr key={r.lever}>
              <td className={`${TD} w-[12rem]`}>{r.lever}</td>
              <td className={`${TD} text-[15px] text-cw-paper-muted`}>{r.condition}</td>
              <td className={`${TD} ${NUM} w-[10rem] whitespace-nowrap`}>{r.standing}</td>
            </tr>
          ))}
        </tbody>
      </Table>

      {anchored && (
        <Footnote>
          A contract only helps if its volume is <em>additional</em> to the range above. It also has
          to arrive at hours the site can serve, and carry a minimum payment that is enforceable
          rather than intended.
        </Footnote>
      )}

      <div className="mt-6">
        <Callout label="Get this in writing before money moves">
          {named.length > 0 ? (
            <p>
              {open.length} of the {payload.site_facts.length} checks are still unverified —{" "}
              {named.join(", ")}
              {open.length > named.length ? " among them" : ""}. Every figure in this document
              multiplies the demand band by numbers those checks either confirm or move, so settle
              them before the build cost is released, not after.
            </p>
          ) : (
            <p>
              All {payload.site_facts.length} checks are verified. What remains open is the demand
              band itself, and section 09 puts a width on that rather than a point.
            </p>
          )}
        </Callout>
      </div>
    </Section>
  );
}
