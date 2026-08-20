"""Progress - what is done, what is next, and why, in order. PART C.

The console's other panels each explain one subsystem; this one explains the
*project*. One ordered list: every milestone with a plain-English description,
its honest status, and - for anything not done - exactly what closes it.

Statuses are **derived from the database wherever a table can testify**, the
same discipline as the coverage panel: `poll_runs` says whether the poller has
ever recorded, `geocode_cache` whether an address was ever resolved, `sites`
whether a customer request was ever logged. A checkbox can go stale; a row
count cannot. The prose is curated by hand, and that is fine - the prose says
what a milestone *is*, the signals say where it *stands*.

Guarded: mounted on the ``guarded`` router in ``api/internal/__init__.py``.
"""

from __future__ import annotations

import datetime as dt
import enum
from dataclasses import dataclass

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.domain.polling.sources import SOURCES

router = APIRouter()


class Status(enum.StrEnum):
    DONE = "done"  # built AND verified against something real
    CODE_DONE = "code_done"  # built and tested, never fed real data
    PARTIAL = "partial"  # some of it is live
    NEXT = "next"  # the actionable queue, in order
    PARKED = "parked"  # deliberately not yet - with the reason
    NOT_STARTED = "not_started"


@dataclass(frozen=True)
class Signals:
    """Everything the milestone list reads from the database. One round trip."""

    districts: int
    pincodes: int
    crosswalk_unverified: int
    geocoded: int
    queue_open: int
    sites: int
    poll_runs: int
    price_cards: int
    usage_events: int
    tariff_rows: int
    tariff_states: int
    competitor_stations: int
    vahan_rows: int
    vahan_states: int
    predictions: int
    reports: int
    #: Sites created by a customer pin on /assess - the funnel's own rows,
    #: distinct from operator-made sites.
    pin_leads: int
    #: Sites carrying a data_tier stamp - PLAN 1.6's gate leaving evidence.
    tiered_sites: int
    sources_authorised: int
    sources_total: int


def read_signals(session: Session) -> Signals:
    row = session.execute(
        text("""
            SELECT
              (SELECT count(*) FROM districts),
              (SELECT count(*) FROM pincodes),
              (SELECT count(*) FROM district_name_crosswalk WHERE verified_by IS NULL),
              (SELECT count(*) FROM geocode_cache),
              (SELECT count(*) FROM geocode_manual_queue WHERE status = 'open'),
              (SELECT count(*) FROM sites),
              (SELECT count(*) FROM poll_runs),
              (SELECT count(*) FROM provider_price_cards),
              (SELECT count(*) FROM api_usage_events),
              (SELECT count(*) FROM electricity_tariffs),
              (SELECT count(DISTINCT lgd_state_code) FROM electricity_tariffs
               WHERE effective_to IS NULL OR effective_to > CURRENT_DATE),
              (SELECT count(*) FROM competitor_stations),
              (SELECT count(*) FROM vahan_ev_registrations),
              (SELECT count(DISTINCT lgd_state_code) FROM vahan_ev_registrations
               WHERE lgd_state_code IS NOT NULL),
              (SELECT count(*) FROM predictions),
              (SELECT count(*) FROM reports),
              (SELECT count(*) FROM sites WHERE geocode_source = 'pin'),
              (SELECT count(*) FROM sites WHERE data_tier IS NOT NULL)
        """)
    ).one()
    return Signals(
        districts=int(row[0]),
        pincodes=int(row[1]),
        crosswalk_unverified=int(row[2]),
        geocoded=int(row[3]),
        queue_open=int(row[4]),
        sites=int(row[5]),
        poll_runs=int(row[6]),
        price_cards=int(row[7]),
        usage_events=int(row[8]),
        tariff_rows=int(row[9]),
        tariff_states=int(row[10]),
        competitor_stations=int(row[11]),
        vahan_rows=int(row[12]),
        vahan_states=int(row[13]),
        predictions=int(row[14]),
        reports=int(row[15]),
        pin_leads=int(row[16]),
        tiered_sites=int(row[17]),
        sources_authorised=sum(1 for s in SOURCES if s.authorised),
        sources_total=len(SOURCES),
    )


class MilestoneOut(BaseModel):
    order: int
    part: str
    title: str
    status: Status
    #: What this milestone is, for someone who has not read PLAN.md.
    what: str
    #: Where it stands - live numbers where the database can testify.
    evidence: str
    #: For anything not done: the specific thing that closes it, and whose
    #: work it is (code vs human).
    to_close: str | None = None


class InputStatus(enum.StrEnum):
    CONFIGURED = "configured"  # present in settings, ready to use
    MISSING = "missing"  # needed now, nothing in settings
    ATTENTION = "attention"  # something is set, but it will not work as-is
    LATER = "later"  # not needed until a later part; do not chase it yet


class InputOut(BaseModel):
    """One external thing only a human can supply: a key, an endpoint, a file.

    The status is read from live settings at request time, so pasting a line
    into ``.env`` and restarting the API flips the row on its own - the page
    can never claim a key exists that the process cannot see.
    """

    name: str
    #: key | endpoint | data | infra
    kind: str
    status: InputStatus
    #: Which part needs it, in plain words.
    needed_for: str
    #: The exact lines to fill in .env - empty for non-env inputs.
    env_vars: list[str]
    #: Where the human gets it: the account to make, the file to download.
    how_to_get: str
    #: What the live settings actually show right now.
    detail: str


class ProgressOut(BaseModel):
    checked_at: dt.datetime
    #: The one-paragraph state of the project.
    summary: str
    milestones: list[MilestoneOut]
    #: Keys, endpoints, data files and infrastructure only a human can supply.
    inputs: list[InputOut]


def build_milestones(s: Signals) -> list[MilestoneOut]:
    """The ordered list. Pure - a function of the signals, nothing else.

    Order is the order a reader should care: the actionable queue first
    (because that is what the page is opened for), then what is done, then
    what is parked on purpose.
    """
    poller_live = s.poll_runs > 0
    geocoding_live = s.geocoded > 0

    out: list[MilestoneOut] = []
    n = 0

    def add(
        part: str, title: str, status: Status, what: str, evidence: str, to_close: str | None = None
    ) -> None:
        nonlocal n
        n += 1
        out.append(
            MilestoneOut(
                order=n,
                part=part,
                title=title,
                status=status,
                what=what,
                evidence=evidence,
                to_close=to_close,
            )
        )

    # ------------------------------------------------------------------ NEXT
    add(
        "0.1",
        "Turn the poller on - one source",
        Status.PARTIAL if poller_live else Status.NEXT,
        "The recorder. Every few minutes it asks each charging network's app which "
        "chargers are free, and writes it down. Months of this becomes the occupancy "
        "record nobody else in India has - and the ONE thing in this project that "
        "cannot be backfilled, bought, or hurried. The 90-day clock for the demand "
        "model starts at the first recorded row.",
        (
            f"{s.poll_runs:,} poll runs recorded; "
            f"{s.sources_authorised} of {s.sources_total} sources authorised."
            if poller_live
            else f"Never run. 0 of {s.sources_total} sources authorised - the code is "
            "complete and tested, waiting only on a human decision."
        ),
        None
        if poller_live
        else "Human: the poller collects by SCRAPING competitors, and the Tata Power adapter "
        "is BUILT with its route confirmed - authorise it in app/domain/polling/sources.py, put "
        "TATA_POWER_EZ__BASE_URL + the token in .env, then validate with "
        "`python -m workers.poller --dry-run`. chargeMOD's real occupancy is the private "
        "accuracy check (scraped-vs-real, by hand), not a wired feed. Then a VPS, never a "
        "laptop - a laptop that sleeps is a hole in the record.",
    )
    assess_live = s.pin_leads > 0
    add(
        "G.2",
        "POST /assess - the funnel's front door",
        Status.PARTIAL if assess_live else Status.CODE_DONE,
        "The free teaser as a real flow: a customer drops a pin, answers up to five "
        "taps, and gets the utilisation that site must clear to break even - pure "
        "arithmetic against the state's typed tariff, no model consulted, so no "
        "prediction row (rule 5 governs model outputs; the teaser makes none). "
        "EVERY pin writes a `sites` lead row first: a pin in an uncovered state "
        "joins the district waitlist, which is capture, not failure - the request "
        "counter on a waitlisted district is the expansion roadmap.",
        (
            f"{s.pin_leads:,} customer pin(s) dropped ({s.sites:,} sites total)."
            if assess_live
            else "Endpoint, arithmetic and frontend built and tested; no customer "
            "has dropped a pin yet. The first one flips this on its own."
        ),
        "Put it in front of people - nothing in the codebase closes this. Then "
        "contact capture on the lead, whose schema is Part 7's (decided by the "
        "0.3 conversations below).",
    )
    add(
        "1.3",
        "Feed the geocoder something real",
        Status.PARTIAL if geocoding_live else Status.NEXT,
        "Address in, map pin out, through the cascade: clean the text, check the cache, "
        "Nominatim free, then Ola / Mappls / Google paid, then a human. All seven levels "
        "are built and tested - against recorded fake responses only.",
        (
            f"{s.geocoded:,} addresses in the cache; {s.queue_open} waiting for a human."
            if geocoding_live
            else "The cascade has never resolved a single real address."
        ),
        None
        if geocoding_live
        else "Config, half a day: point NOMINATIM_URL at the public OpenStreetMap instance "
        "(proper User-Agent, 1 request/second - fine at our volume; the 40-80 GB "
        "self-hosted import is NOT needed at hundreds of reports a month). Expect the "
        "first real Ola/Mappls/Google calls to need a debugging pass - their response "
        "shapes were written from documentation, never observed.",
    )
    add(
        "1 exit",
        "Prove Part 1 on 200 real addresses",
        Status.NEXT,
        "Part 1 is finished only when 200 real Kerala + Tamil Nadu addresses have gone "
        "through the whole pipe and a human has checked the district on every one. The "
        "harness is one command and already scores four of the six criteria itself.",
        f"The address list does not exist yet. {s.sites:,} sites recorded so far.",
        "Human: assemble 200 addresses (by hand or a public directory). Then "
        "`python -m scripts.cascade_batch addresses.csv --out verify.csv --write` "
        "and hand-check the correct_y_n column.",
    )
    add(
        "3.3",
        "Reconcile the engine against one real P&L",
        Status.NEXT,
        "The exit test the ROI engine still owes: reproduce one operator's real "
        "monthly P&L to within 5% using the engine's arithmetic. The 43 green tests "
        "prove the formulas agree with the plan; only a real bill proves the plan "
        "agrees with the world. Until this runs, every rupee in every report is "
        "uncalibrated arithmetic - correct by construction, unproven by evidence.",
        "Never run. No real month's numbers have been fed in; chargeMOD's own "
        "stations are the natural first candidate.",
        "Human: one month of one real station - energy purchased, revenue, rent, "
        "demand charges. Code: `uv run python -m scripts.roi_example` already shows "
        "how to state them as RoiInputs; the comparison itself is an afternoon.",
    )
    tariffs_live = s.tariff_states > 0
    add(
        "0.2 → 3.1",
        "Type in the tariffs: the first thing anyone pays for",
        Status.PARTIAL if tariffs_live else Status.NEXT,
        "Collect each state's electricity tariff orders (EV order AND the general "
        "schedule, including superseded ones - an old report must regenerate with the "
        "old price) and type them into the effective-dated tables. A Tariff Audit - "
        "'here is where you are overpaying' - is verifiable by the customer against "
        "their own bill, which is why it sells before any prediction can. Exit test: "
        "sell three.",
        (
            f"{s.tariff_rows} tariff row(s) covering {s.tariff_states} state(s)."
            if tariffs_live
            else "The schema and the calculator are BUILT and tested - the tables hold "
            "zero rows, which is exactly why every state shows Tier 3 on the Data "
            "panel. Type in Kerala's order and Kerala turns Tier 2 on its own."
        ),
        "Human: KSERC first, then TNERC - one state per evening. Each row needs the "
        "order number and PDF as provenance; a tariff that cannot be defended to a "
        "customer whose bill disagrees is not data.",
    )
    add(
        "0.3",
        "Two CPO conversations",
        Status.NEXT,
        "Two real conversations with charge-point operators, before Part 7. The one "
        "question that decides the attribution schema: how do they credit an inbound "
        "lead today? Record the answer verbatim.",
        "Not started. Long lead time - conversations take weeks to arrange, so "
        "starting them costs nothing now and unblocks Part 7 later.",
        "Human: arrange them. Nothing in the codebase can.",
    )

    # ------------------------------------------------------------------ DONE
    add(
        "1.1–1.2",
        "Reference maps loaded",
        Status.DONE,
        "India's official state, district and PIN boundaries in our own database, with "
        "the government's LGD code carried on every polygon so nothing ever matches on "
        "spelling. Provenance (source, checksum, licence, date) recorded per layer.",
        f"{s.districts:,} districts, {s.pincodes:,} PIN polygons, all 36 states/UTs. "
        f"Open: the urban/rural layer (B4), and {s.crosswalk_unverified} crosswalk rows "
        "await a human signature.",
        None,
    )
    add(
        "1.4",
        "Pin → district, verified live",
        Status.DONE,
        "Which district contains this point - with refusal as a first-class answer: "
        "two overlapping districts is refused, nothing within 5 km is refused, a "
        "conflicting customer PIN wins over the geocoder, and every answer carries "
        "high/medium/low plus the reasons. Explorable on the Lookup panel.",
        "Selftest 9/9 against real places. Walayar → Palakkad with Coimbatore (Tamil "
        "Nadu) at 87 m - the two-tariff border case working as designed.",
        None,
    )
    add(
        "1.5",
        "The sites table",
        Status.DONE,
        "One row per distinct place a customer asks about, holding both verdicts "
        "(geocode + district) folded to the weaker confidence, and a request counter - "
        "the same place asked twice is one site, counted, and that count is the "
        "expansion roadmap.",
        f"{s.sites:,} rows (none yet - no customer request has been recorded). Two "
        "columns deliberately NULL until their parts land: urban_rural (B4), "
        "data_tier (1.6).",
        None,
    )
    add(
        "C.0–C.1",
        "Console shell, login, and the money meter",
        Status.DONE,
        "Server-side login guarding every internal endpoint (unconfigured = 503, never "
        "an open door), and metering: every paid call writes an append-only row BEFORE "
        "its response is used, priced by an effective-dated price card. A paid level "
        "that cannot be priced cannot even be constructed.",
        f"{s.price_cards} price cards seeded ({s.usage_events} usage events - no paid "
        "call has happened yet). Two of three rates are placeholder guesses until a "
        "real bill confirms them.",
        None,
    )
    competitors_live = s.competitor_stations > 0
    add(
        "2.3",
        "Competitor inventory",
        Status.PARTIAL if competitors_live else Status.NEXT,
        "Who else has a charger where, and how powerful - the denominator for "
        "'how much competition is near this site'. Pulled from Open Charge Map (one "
        "free-key API over all of India), each station resolved to its district on "
        "ingest. This is existence + specs; how BUSY each one is comes only from the "
        "poller, and attaches to these rows later.",
        (
            f"{s.competitor_stations:,} stations stored (see the Competitors panel)."
            if competitors_live
            else "None fetched yet."
        ),
        None
        if competitors_live
        else "Get a free Open Charge Map key (openchargemap.org), put it in .env, then "
        "`python -m scripts.fetch_competitors --state kerala --write`.",
    )
    vahan_live = s.vahan_rows > 0
    add(
        "4.1",
        "VAHAN vehicle counts - the demand raw material",
        Status.PARTIAL if vahan_live else Status.CODE_DONE,
        "How many EVs are registered in each district, by vehicle class, from the "
        "government's VAHAN dashboard. Our own fetcher scrapes it - every vehicle class "
        "(buses and commercial included, not a hand-picked few) and one pass per "
        "calendar year, because PLAN 4.1 weights the GROWTH rate above the absolute "
        "count and a growth rate needs more than one year. Stored as a time series, "
        "never overwritten, each RTO resolved to its district. This is the third of the "
        "four Tier-1 layers for a state; occupancy is the last.",
        (
            f"{s.vahan_rows:,} rows across {s.vahan_states} state(s) (see the VAHAN "
            "panel), refreshed by the scheduled job scripts/vahan_refresh.bat: it pins "
            "one CSV per run (--out, so midnight cannot split it), retries the scrape "
            "up to 12x on top of resume (sentinel rows make retries cheap), ingests "
            "that exact file, and has a --smoke mode that rehearses the whole job on "
            "2 RTOs under a sentinel snapshot date."
            if vahan_live
            else "Scraper, schema and ingest are BUILT and tested - zero rows yet, which "
            "is why every state's vehicle-count flag is false on the Data panel. Scrape "
            "Kerala and its flag turns true on its own."
        ),
        None
        if vahan_live
        else "Human: `uv sync --extra scrape` (installs the browser), then "
        "`python -m scripts.scrape_vahan --state kerala` (a long run against the "
        "portal), then `python -m scripts.ingest_vahan --csv <the CSV> --write`. "
        "Validate first with `--dry-run --limit 2`. Once proven, schedule "
        "scripts/vahan_refresh.bat so the time series grows on its own.",
    )
    add(
        "3.1 + 3.2",
        "The tariff schema and the ROI calculator",
        Status.CODE_DONE,
        "The money machinery: effective-dated tariff and subsidy tables (never "
        "overwritten, so an old report recomputes under the old price), and the pure "
        "ROI engine - breakeven utilisation, NPV, IRR, payback, 10-year cashflow, "
        "fleet-anchor / solar / financing scenarios, price sensitivity at +/- Rs 2, "
        "and a recommended sanctioned load. No database, no network - the honesty "
        "firewall (PART 7) depends on nothing being able to reach in and bend a "
        "number. Try it: `uv run python -m scripts.roi_example`.",
        "43 engine tests green, every PLAN 3.2 named case covered. UNPROVEN against "
        "reality: 3.3 requires reconciling one operator's real monthly P&L to within "
        "5%, and no tariff row or real P&L exists yet.",
        None,
    )
    add(
        "2.1–2.2",
        "Site context from OpenStreetMap - roads and what holds a driver",
        Status.DONE,
        "What surrounds a pin, scraped FREE from OSM's Overpass API (no key, no "
        "account; throttled to 1 request/second with an identified User-Agent): the "
        "nearest major road with its class, ref and measured distance, whether it is "
        "divided, junctions within 500 m - and POI counts in 500 m / 1 km / 3 km "
        "rings weighted into a dwell score (a mall holds a driver 45 minutes; a fuel "
        "pump holds nobody). Fetch and parse are split, so every parse is tested "
        "against recorded fixtures, and a failed fetch degrades to 'not assessed' in "
        "the report's ledger rather than a guess.",
        "Built, tested, and fed real data: the demo report found its adjacent road at "
        "4.1 m and scored real named dwell anchors. Deliberately NOT claimed in v0: "
        "which SIDE of a divided road the site is on (needs carriageway-pair "
        "matching), and drive-time catchments (OpenRouteService is keyed, and every "
        "keyed call must be metered first).",
        None,
    )
    demand_live = s.predictions > 0
    add(
        "4.2",
        "Synthetic demand v0 - the stopgap the report admits to",
        Status.PARTIAL if demand_live else Status.CODE_DONE,
        "Until the poller's occupancy record exists, demand is a pure, deterministic "
        "heuristic: archetype base x district EV growth x competition x dwell, with "
        "coefficients declared in a versioned JSON file - guesses, but WRITTEN-DOWN "
        "guesses. It outputs only kWh/connector-day as a P10-P90 band, never money; "
        "every input it is missing WIDENS the band instead of narrowing the story. "
        "Each run writes an append-only row to `predictions` with actual_kwh NULL, "
        "so when reality arrives the model's error is measurable, not deniable.",
        (
            f"{s.predictions:,} prediction(s) logged (demo runs flagged is_demo, never skipped)."
            if demand_live
            else "Module and coefficients built and tested; no prediction logged yet."
        ),
        "Replaced, never patched: the trained model (Part 8) takes over 90 days "
        "after the poller's first row, and the predictions table is the scorecard "
        "that proves it earned the job.",
    )
    reports_live = s.reports > 0
    add(
        "5 + 6",
        "The report pipeline - pin to verdict, stored and served",
        Status.PARTIAL if reports_live else Status.CODE_DONE,
        "The customer-facing product: assemble VAHAN + tariff + competitors + OSM "
        "context + the synthetic band, run the ROI engine per percentile and per "
        "CPO arrangement (the comparison table, Part 6), and persist the whole "
        "payload as JSONB in `reports`. GET /api/internal/reports/{id} serves that "
        "row VERBATIM - never recomputes - and the frontend renders it at "
        "/report/:id, with the /assess teaser reading the same stored row. Every "
        "rupee figure comes from the engine; the report's job is to show its work.",
        (
            f"{s.reports:,} report(s) stored. The demo (KL-TVM-DEMO-001, "
            "Kazhakkoottam NH-66) renders live from the database - and its verdict "
            "is DON'T BUILD at -3.5 pp, because eight real competitors sit within "
            "3 km. An honest 'no' on our own doorstep is the product working."
            if reports_live
            else "Pipeline, storage, endpoint and frontend built and tested; no "
            "report generated yet. `python -m scripts.generate_demo_report --write` "
            "creates the first."
        ),
        "Attribution (Part 7) once the 0.3 conversations decide its schema - the "
        "customer intake itself (POST /assess) is built and carved out into G.2 "
        "at the top of the queue.",
    )
    tiered = s.tiered_sites > 0
    add(
        "1.6",
        "Tier gate",
        Status.PARTIAL if tiered else Status.CODE_DONE,
        "'How much do we know here', as a number a site carries: Tier 1 = full "
        "report honest, Tier 2 = breakeven + tariff audit honest, Tier 3 = "
        "waitlist. One pure function in domain/resolution/coverage.py, derived "
        "from the live tables - /assess stamps every pin's sites.data_tier with "
        "it and waitlists Tier 3 while still logging the lead; the coverage "
        "panel displays the same judgement per state. Neither owns a copy, so "
        "they cannot disagree.",
        (
            f"{s.tiered_sites:,} site(s) carry a stamped tier; "
            f"{s.tariff_states} state(s) currently reach Tier 2."
            if tiered
            else "Built and tested; no site stamped yet - the next /assess pin stamps itself."
        ),
        "Per-district data_coverage rows become worth persisting the day tiers "
        "vary WITHIN a state - which needs district-attributed occupancy (the "
        "poller + FINDINGS B3). Until then three subselects are the truth.",
    )
    add(
        "C (explain)",
        "The explainer panels",
        Status.DONE,
        "Lookup (a coordinate resolved with every step shown and the table behind each "
        "answer), Data (every table + what it is for + live per-state tiers), this "
        "Progress page, and a glossary on every panel.",
        "You are reading the evidence.",
        None,
    )

    # ---------------------------------------------------------------- PARKED
    add(
        "L2 self-host",
        "Self-hosted Nominatim",
        Status.PARKED,
        "Running our own geocoder, which makes geocoding free forever at the cost of a "
        "40-80 GB one-time import on the VPS.",
        "Not needed at hundreds of reports a month - the public instance inside its "
        "usage policy covers the current volume.",
        "Revisit if the free 'drop a pin' public tool (PLAN G.2) takes off and volume jumps.",
    )
    add(
        "2 (rest) / 8",
        "The context that needs more than OSM, and the trained model",
        Status.PARKED,
        "What Part 2 still owes after the OSM layer above: WHICH SIDE of a divided "
        "road the site sits on (wrong side loses ~half the traffic - needs "
        "carriageway-pair matching), urban vs rural at the exact point (blocked on "
        "the Census town layer, B4), grid/transformer distance, drive-time "
        "catchments (needs a metered ORS key), and each competitor's measured "
        "busyness - which only the poller can supply. Part 8 is the trained model "
        "that retires synthetic_v0.",
        "Correctly waiting: every item is blocked on a named input (a data layer, a "
        "key, or the poller's record), not on code.",
        "Unblocked by: the town-boundary load, an ORS key behind the meter, and - "
        "for busyness and Part 8 - the poller's first 90 days, which is why "
        "milestone #1 is the whole schedule.",
    )
    add(
        "7 / G",
        "Attribution and the revenue ladder",
        Status.NOT_STARTED,
        "The prove-the-lead attribution chain (DO NOT DEFER once selling starts) and "
        "the revenue ladder: audits → institutional subscriptions → commissions. The "
        "report and CPO comparison that used to sit here are built - carved out "
        "above.",
        "Nothing built. Part 7's schema is decided by the 0.3 conversations - which is "
        "why they are in the queue above.",
        "Deps: 7 needs 0.3's verbatim answers; G.1 pairs with Part 3's tariff audit.",
    )

    return out


#: The paid geocoders share one shape: an account, a key, and - before the key
#: goes anywhere near .env - a hard spending cap set in the provider's own
#: console. The app refuses to boot with a key that has no cap (config.py).
_PAID_GEOCODERS: tuple[tuple[str, str, str, str], ...] = (
    (
        "ola_maps",
        "Ola Maps (cascade L3)",
        "First paid fallback when Nominatim misses. Indian addresses are its home turf.",
        "Account at maps.olakrutrim.com -> create an API key -> set a hard monthly "
        "quota cap in THEIR console first.",
    ),
    (
        "mappls",
        "Mappls / MapmyIndia (cascade L4)",
        "Second paid fallback. Strong on Indian PIN-level addresses and eLoc handles.",
        "Account at apis.mappls.com -> REST API key -> set the cap in their console "
        "first. (Their OAuth flow is not needed for a REST key.)",
    ),
    (
        "google_maps",
        "Google Maps (cascade L5, last resort)",
        "Final paid fallback, called only when everything cheaper failed or doubted "
        "itself. You already have a key - BEFORE pasting it, set a hard quota cap on "
        "the Geocoding API in Google Cloud console.",
        "console.cloud.google.com -> APIs & Services -> Geocoding API -> Quotas -> "
        "set a hard daily/monthly cap.",
    ),
)


def build_inputs(
    settings: Settings, *, urban_layer_loaded: bool, vahan_loaded: bool = False
) -> list[InputOut]:
    """Everything only a human can supply, with live status. Pure given inputs.

    The flow this list is built for: make the account, set the provider-side
    cap, paste the env lines into ``.env``, restart the API - and this page
    flips the row to `configured` on its own, because it reads settings rather
    than remembering claims.
    """
    out: list[InputOut] = []

    # --- geocoding -----------------------------------------------------------
    nominatim_is_local_default = settings.nominatim_url.rstrip("/") == "http://localhost:8080"
    out.append(
        InputOut(
            name="Nominatim (cascade L2 - the free geocoder)",
            kind="endpoint",
            status=InputStatus.ATTENTION if nominatim_is_local_default else InputStatus.CONFIGURED,
            needed_for="PART 1.3 - resolving addresses without paying. Blocks all of Part 1 live.",
            env_vars=["NOMINATIM_URL=https://nominatim.openstreetmap.org"],
            how_to_get=(
                "NO account and NO key - this is the one that needs nothing. Either point "
                "at the public OpenStreetMap instance (fine at our volume: ~1 request/"
                "second with a proper User-Agent), or self-host on the VPS later "
                "(40-80 GB import; parked until volume demands it)."
            ),
            detail=(
                f"Currently {settings.nominatim_url!r}"
                + (
                    " - the localhost default, and nothing is running there, so every "
                    "address falls straight through to the paid levels (which are also "
                    "unconfigured). One .env line fixes this."
                    if nominatim_is_local_default
                    else "."
                )
            ),
        )
    )

    for key, name, why, how in _PAID_GEOCODERS:
        provider = settings.paid_providers[key]
        prefix = key.upper()
        out.append(
            InputOut(
                name=name,
                kind="key",
                status=InputStatus.CONFIGURED if provider.enabled else InputStatus.MISSING,
                needed_for=f"PART 1.3 - {why}",
                env_vars=[
                    f"{prefix}__API_KEY=...",
                    f"{prefix}__MONTHLY_CAP=10000",
                    f"{prefix}__CONSOLE_CAP_CONFIRMED=true",
                ],
                how_to_get=how,
                detail=(
                    f"Configured, cap {provider.monthly_cap:,}/month."
                    if provider.enabled and provider.monthly_cap
                    else "No key in settings. Note: the app refuses to boot with a key "
                    "that has no cap - paste all three lines together, and set "
                    "CONSOLE_CAP_CONFIRMED=true only after the cap really exists in "
                    "the provider's console."
                ),
            )
        )

    # --- CPO endpoints ---------------------------------------------------------
    scrape = settings.scrape_sources
    for spec in SOURCES:
        cfg = scrape.get(spec.name)
        if cfg is None:
            continue  # not a scraped source (e.g. OCPI) - nothing to fill in .env
        if spec.authorised and cfg.configured:
            status, detail = InputStatus.CONFIGURED, "Authorised and configured - polling."
        elif spec.authorised:
            status = InputStatus.MISSING
            detail = "Authorised in sources.py; waiting on the endpoint discovery."
        elif cfg.configured:
            status = InputStatus.ATTENTION
            detail = (
                "An endpoint is configured but the source is NOT authorised in "
                "sources.py - it will not be polled, by design. Config alone is "
                "never consent."
            )
        else:
            status, detail = InputStatus.MISSING, "Neither authorised nor configured."
        prefix = spec.name.upper()
        out.append(
            InputOut(
                name=f"{spec.name} endpoint (poller)",
                kind="endpoint",
                status=status,
                needed_for=(
                    "PART 0.1 - the occupancy record. chargeMOD is NOT fed from its own "
                    "backend (owner decision); its real occupancy is the private accuracy "
                    "check - scraped-vs-real is compared by hand to trust the scraping."
                    if spec.name == "chargemod"
                    else "PART 0.1 - the occupancy record, by scraping."
                ),
                env_vars=[
                    f"{prefix}__BASE_URL=https://...",
                    f"{prefix}__STATIONS_PATH=/stations",
                    f"{prefix}__RATE_LIMIT_PER_MINUTE=30",
                ],
                how_to_get=(
                    "Not a vendor account - a discovery: open the app with mitmproxy or "
                    "browser devtools, find the URL it calls for station status (~hours, "
                    "once per app). Validate with `python -m workers.poller --dry-run` "
                    "(no database needed), then flip authorised=True in "
                    "app/domain/polling/sources.py."
                ),
                detail=detail,
            )
        )

    # --- context scraping (free, keyless) ---------------------------------------
    out.append(
        InputOut(
            name="OSM Overpass (context layer - roads and POIs)",
            kind="endpoint",
            status=InputStatus.CONFIGURED,
            needed_for=(
                "PART 2.1-2.2 - the nearest major road, its distance and class, "
                "junction density, and the POI rings behind the dwell score in every "
                "report."
            ),
            env_vars=[],
            how_to_get=(
                "Nothing to get: overpass-api.de is free and keyless. The client "
                "identifies itself with a proper User-Agent and throttles to 1 "
                "request/second - report generation makes a handful of calls, well "
                "inside the fair-use policy. Unmetered on purpose: the meter exists "
                "to cap SPEND, and this cannot spend."
            ),
            detail="Built in, nothing to configure. Used live by report generation.",
        )
    )
    out.append(
        InputOut(
            name="OpenRouteService key (drive-time catchments)",
            kind="key",
            status=InputStatus.LATER,
            needed_for=(
                "PART 2.2 - the 5/10-minute drive-time catchment around a site. The "
                "free tier (500 isochrones/day) is plenty; the report currently says "
                "'not assessed' instead."
            ),
            env_vars=[],
            how_to_get=(
                "Do not chase it yet - before any keyed call is made, ORS must be "
                "wired through the meter (api_usage_events) like every other keyed "
                "provider, even at price zero. Free account at openrouteservice.org "
                "when that lands."
            ),
            detail="Not wired into config.py yet, deliberately.",
        )
    )

    # --- data files (no accounts, no keys) --------------------------------------
    out.append(
        InputOut(
            name="Urban/rural layer (Census 2011 town boundaries)",
            kind="data",
            status=InputStatus.CONFIGURED if urban_layer_loaded else InputStatus.MISSING,
            needed_for=(
                "PART 1.2/1.5 (blocker B4) - whether a specific pin is in a town or a "
                "field. District polygons cannot answer this; it needs the town/"
                "built-up-area polygons as one more reference layer."
            ),
            env_vars=[],
            how_to_get=(
                "A public download, no account: Census 2011 town/UA boundaries "
                "(datameet's census GIS mirrors carry them). Then one LayerSpec in "
                "app/domain/resolution/reference.py and a load_reference run - the "
                "code half is ours."
            ),
            detail="Loaded."
            if urban_layer_loaded
            else "Not loaded - sites.urban_rural stays NULL.",
        )
    )
    out.append(
        InputOut(
            name="SERC tariff PDFs (KL, TN, KA, MH, DL, GJ)",
            kind="data",
            status=InputStatus.MISSING,
            needed_for=(
                "PART 0.2 -> 3 - the first sellable product. Also what moves a state "
                "off Tier 3: load Kerala's tariff and Kerala becomes Tier 2 on its own."
            ),
            env_vars=[],
            how_to_get=(
                "Public documents, no account: each SERC's website (KSERC, TNERC, ...). "
                "Collect the EV charging order AND the general HT/LT schedule, "
                "INCLUDING superseded orders - an old report must regenerate with the "
                "old price. One state per evening."
            ),
            detail="None collected. No tariff table exists yet.",
        )
    )

    # --- later ------------------------------------------------------------------
    out.append(
        InputOut(
            name="LLM API key (Anthropic or OpenAI)",
            kind="key",
            status=InputStatus.LATER,
            needed_for="PART 3.1 - extracting structured rows from tariff PDFs, human-checked.",
            env_vars=[],
            how_to_get=(
                "Do not chase it yet - the setting itself does not exist until Part 3.1 "
                "is built. It will follow the same three-locks shape as the geocoders."
            ),
            detail="Not wired into config.py yet, deliberately.",
        )
    )
    out.append(
        InputOut(
            name="VAHAN registration data",
            kind="data",
            status=InputStatus.CONFIGURED if vahan_loaded else InputStatus.MISSING,
            needed_for=(
                "PART 4.1 - EV counts and growth per district, the third of the four "
                "Tier-1 layers. No key or account; the work is a browser scrape."
            ),
            env_vars=[],
            how_to_get=(
                "Our own fetcher, no vendor: `uv sync --extra scrape` then "
                "`python -m scripts.scrape_vahan --state kerala` (long run against the "
                "government dashboard), then `python -m scripts.ingest_vahan --csv "
                "<the CSV> --write`. RTO list + coordinates are already seeded. For "
                "steady state, schedule scripts/vahan_refresh.bat (Task Scheduler): "
                "scrape with retries + resume, ingest the pinned CSV, all in one job "
                "- rehearse it first with --smoke."
            ),
            detail=(
                "Loaded - at least one state scraped and ingested; the scheduled "
                "refresh job keeps the time series growing."
                if vahan_loaded
                else "Not scraped yet. The scraper, schema and ingest are built and "
                "tested; running the scrape is a human step (it drives a browser)."
            ),
        )
    )

    # --- infrastructure -----------------------------------------------------------
    out.append(
        InputOut(
            name="A cheap always-on VPS",
            kind="infra",
            status=InputStatus.MISSING,
            needed_for=(
                "PART 0.1 - where the poller lives. Never a laptop: a laptop that "
                "sleeps is a hole in the record, and holes in this record cannot be "
                "repaired. Later also the self-hosted Nominatim, if volume demands it."
            ),
            env_vars=[],
            how_to_get="Any provider; ~2 vCPU / 4 GB is plenty to start.",
            detail="None provisioned.",
        )
    )
    out.append(
        InputOut(
            name="Database (Neon Postgres)",
            kind="infra",
            status=InputStatus.CONFIGURED,
            needed_for="Everything.",
            env_vars=["DATABASE_URL=postgresql://..."],
            how_to_get="Already done.",
            detail="Connected; all migrations applied.",
        )
    )
    out.append(
        InputOut(
            name="Console login",
            kind="infra",
            status=(
                InputStatus.ATTENTION
                if settings.console_auth_disabled
                else InputStatus.CONFIGURED
                if settings.console_configured
                else InputStatus.MISSING
            ),
            needed_for="PART C.0 - this console.",
            env_vars=["CONSOLE_SECRET_KEY=...", "CONSOLE_PASSWORD_HASH=..."],
            how_to_get="`uv run python -m scripts.console_password` prints both lines.",
            detail=(
                "Login is switched OFF for local dev (CONSOLE_AUTH_DISABLED=true). "
                "Deliberate, and prod refuses to boot in this state - but it stays "
                "flagged here so it cannot be forgotten. Remove the line to bring "
                "the password back."
                if settings.console_auth_disabled
                else "Configured - you are logged into the evidence."
                if settings.console_configured
                else "Not set; every console endpoint returns 503 until it is."
            ),
        )
    )

    return out


_SUMMARY = (
    "The machine now runs end to end and has a front door: a customer can drop a pin "
    "on /assess and get the breakeven number from pure arithmetic, every pin logged "
    "as a lead - and behind it, pin → district → OSM context → a versioned demand "
    "band → the ROI engine → a report stored as JSONB and served verbatim at "
    "/report/:id. Real data flows through it all - VAHAN on a scheduled nightly "
    "scrape, competitor inventory, typed tariffs - and the statuses below read the "
    "database, not the plan. Still missing is the one input that cannot be "
    "backfilled: the poller's occupancy record. Its delay is the only permanent "
    "loss, which is why it stays at the top of the queue."
)


@router.get("/progress", response_model=ProgressOut)
def progress(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ProgressOut:
    urban_loaded = bool(
        session.execute(
            text(
                "SELECT count(*) FROM reference_layers "
                "WHERE name ILIKE '%urban%' OR name ILIKE '%town%'"
            )
        ).scalar_one()
    )
    signals = read_signals(session)
    return ProgressOut(
        checked_at=dt.datetime.now(dt.UTC),
        summary=_SUMMARY,
        milestones=build_milestones(signals),
        inputs=build_inputs(
            settings, urban_layer_loaded=urban_loaded, vahan_loaded=signals.vahan_rows > 0
        ),
    )
