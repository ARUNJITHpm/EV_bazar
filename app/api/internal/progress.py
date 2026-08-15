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
               WHERE lgd_state_code IS NOT NULL)
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
        else "Human: open the chargeMOD app with devtools/mitmproxy, find the station-status "
        "endpoint (~hours, once). Validate with `python -m workers.poller --dry-run` (no "
        "database needed). Record terms + rate limit, flip authorised=True in "
        "app/domain/polling/sources.py. Then a VPS, never a laptop - a laptop that "
        "sleeps is a hole in the record.",
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
            f"{s.vahan_rows:,} rows across {s.vahan_states} state(s) (see the VAHAN panel)."
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
        "Validate first with `--dry-run --limit 2`.",
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
        "1.6",
        "Tier gate",
        Status.PARKED,
        "Persist per-district 'how much do we know' and stamp it on every site, "
        "waitlisting Tier 2/3 customers while still logging the pin.",
        "The Data panel already computes the same judgement live, and today it says "
        "Tier 3 everywhere - persisting that adds nothing.",
        "Becomes worth building the day the first tariff loads and the answer starts "
        "varying by state. Cheap then.",
    )
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
        "2 / 4 / 8",
        "Context, demand, and the model",
        Status.PARKED,
        "Part 2 describes each site's surroundings: distance to the nearest highway/"
        "main road, WHICH SIDE of a divided road (wrong side loses ~half the "
        "traffic), junction count, urban vs rural at the exact point, what holds a "
        "driver for 30-45 minutes nearby, competitors and their measured busyness, "
        "grid distance. Part 4's later steps (the 4.2 heuristic onward) turn that into "
        "a demand estimate with honest P10/P50/P90 bands - 4.1's vehicle counts are "
        "carved out above, already built. Part 8 is the trained model.",
        "Correctly waiting: 2 pays off once there are sites to describe, 4.2 needs 2, "
        "and 8 cannot start until 90 days after the poller's first row - which is why "
        "milestone #1 is the whole schedule.",
        "Unblocked by, in order: sites flowing, Part 2 imports, the poller's 90 days.",
    )
    add(
        "5 / 6 / 7 / G",
        "Reports, comparison, attribution, revenue",
        Status.NOT_STARTED,
        "The customer-facing report, the CPO comparison table, the prove-the-lead "
        "attribution chain (DO NOT DEFER once selling starts), and the revenue ladder: "
        "audits → institutional subscriptions → commissions.",
        "Nothing built. Part 7's schema is decided by the 0.3 conversations - which is "
        "why they are in the queue above.",
        "Deps: 5 needs 1-4; 6 needs 0.3 + 3; 7 needs 0.3; G.1 pairs with Part 3.",
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
                    "PART 0.1 - the occupancy record. Start with chargeMOD: it is our "
                    "own app, so authorising it is a decision we can make today, and it "
                    "doubles as the accuracy check for scraping the others."
                    if spec.name == "chargemod"
                    else "PART 0.1 - the occupancy record."
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
                "<the CSV> --write`. RTO list + coordinates are already seeded."
            ),
            detail=(
                "Loaded - at least one state scraped and ingested."
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
    "The foundation is built and verified: maps loaded, pin-to-district working live, "
    "the cascade complete, money metering structural, console guarded. What is missing "
    "is REALITY flowing through it - no source polled, no real address geocoded, no "
    "tariff typed in. Every item in the queue below is about connecting the machine to "
    "the world, and all five can proceed in parallel. The poller is first because its "
    "delay is the only one that can never be recovered."
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
