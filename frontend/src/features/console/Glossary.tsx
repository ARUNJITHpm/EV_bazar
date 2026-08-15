/**
 * PART C — the words, on the page that uses them.
 *
 * This console is full of terms that are obvious only once somebody explains
 * them: LGD codes, polygons, cascades, change logs, two locks. Rather than a
 * separate documentation page nobody opens, each panel carries the handful of
 * terms it actually uses, defined in one place so a definition cannot drift
 * between panels.
 *
 * Definitions are written for someone who has never seen the codebase.
 */

export const TERMS: Record<string, string> = {
  // --- sources and the poller ---------------------------------------------
  CPO: "Charge Point Operator — a charging network company. ChargeZone, Statiq, Kazam, Tata Power, chargeMOD.",
  Poller:
    "Our background program. Every few minutes it asks each charging network's app which of its chargers are free or busy, and writes down what it saw. Months of this becomes a record of real usage that nobody else in India has.",
  Scrape:
    "Reading the data an app already shows its own users, by calling the same web addresses the app calls. Our starting method for every network.",
  OCPI: "An official standard that lets charging networks share data with each other, with permission. Cleaner than scraping, but it needs a signed partnership — so it is the later upgrade, not the start.",
  Connector:
    "One physical plug. A station usually has several, and everything is measured per connector rather than per station.",
  Occupancy:
    "How much of the time a connector is actually in use. Observed by the poller, never estimated — this is the number the demand model is calibrated against.",
  "Two locks":
    "A network is polled only when BOTH are true: a human read its terms and marked it authorised in the code, AND an endpoint is configured. Configuration alone is never consent.",
  Archive:
    "The lossless copy of exactly what a network returned, stored before anything is interpreted. The one table that cannot be rebuilt if it is lost.",
  "Change log":
    "One row each time a connector's status changes — not one row per observation. Zero rows during a quiet hour is healthy, not broken.",
  "Dead-man's switch":
    "An alarm that fires when the poller goes quiet. For a recorder, silence is the failure mode, not errors.",

  // --- geography -----------------------------------------------------------
  LGD: "Local Government Directory code — the government's official number for each state and district. Everything joins on the number, never on the spelling, so 'Vizag' and 'Visakhapatanam' cannot become two different places.",
  Polygon:
    "An area drawn as a shape, corner by corner. A district boundary is a polygon; so is a PIN delivery area.",
  "Point-in-polygon":
    "Asking the database which district outline contains this pin. The single most load-bearing lookup in the product: the district picks the tariff, the tariff decides the verdict.",
  "PIN polygon":
    "An India Post delivery area drawn as a shape. Useful for catching a geocode that landed in the wrong district — but India Post defines delivery rounds, not administrative areas, so it is a cross-check and never the final word.",
  PostGIS:
    "The add-on that teaches the database about shapes and distances, so 'which district contains this point' is one query rather than a program.",

  // --- resolution ----------------------------------------------------------
  Geocoding: "Turning a written address into two numbers: latitude and longitude. A map pin.",
  Cascade:
    "Our chain of geocoders, cheapest first, stopping at the first confident answer: clean the text → check the cache → Nominatim → Ola → Mappls → Google → ask a human. Most addresses never reach a paid level, and that is the entire cost strategy.",
  Nominatim:
    "The free, open-source geocoder behind OpenStreetMap's search box. It can be run on our own server, which makes geocoding cost nothing forever — at the price of a 40–80 GB one-time import.",
  Confidence:
    "high, medium or low — plus the reasons. Deliberately never a decimal: a 0.83 would imply a calibration nobody has done. One downgrade per doubt, and it never recovers.",
  "Manual queue":
    "Where an address goes when the cascade refuses to guess. A human places the pin once, and it is never asked again.",

  // --- coverage and money --------------------------------------------------
  Tier: "How much we honestly know about a district. Tier 1 = a full report. Tier 2 = a breakeven number only. Tier 3 = log the pin and waitlist the customer.",
  "Price card":
    "What a provider charges, with the dates it applied. Never overwritten — a new price is a new row, so a cost from last March still recomputes at last March's price.",
  Cap: "A hard monthly spending limit. At the cap the code refuses the call and falls through to the next level, rather than warning and continuing.",
  Paise:
    "Money is stored as whole paise (1/100 of a rupee) so that repeated arithmetic cannot drift the way decimals do.",
  "Append-only":
    "A table where rows can be added but never edited or deleted. Used for anything that is a record of what happened.",
  "Breakeven utilisation":
    "How busy the chargers must be for a site to stop losing money. The one number the whole report is built around.",
};

/**
 * The terms used on this panel. Open by default: the point is to be read.
 */
export function Glossary({ terms }: { terms: string[] }) {
  const known = terms.filter((t) => t in TERMS);
  if (known.length === 0) return null;

  return (
    <details open className="mb-6 max-w-3xl border border-rule">
      <summary className="cursor-pointer bg-ground-sunk px-3 py-1.5 font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
        Words on this page
      </summary>
      <dl className="px-3 py-2">
        {known.map((t) => (
          <div key={t} className="border-b border-rule py-1.5 last:border-b-0">
            <dt className="font-data text-[12px]">{t}</dt>
            <dd className="max-w-prose text-[12px] text-ink-muted">{TERMS[t]}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
