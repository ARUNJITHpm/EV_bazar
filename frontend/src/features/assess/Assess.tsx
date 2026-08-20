import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

import { formatRupeesPrecise, type Paise } from "../../lib/money";
import { formatUtilisation } from "../../lib/units";
import { DEMO_REPORT_ID } from "../report/payload";

/**
 * The public teaser (PLAN G.2), now the real flow: drop a pin anywhere, answer
 * up to five taps, POST /assess — and the certain number comes back from pure
 * arithmetic against the state's typed tariff. No model, no verdict: whether
 * the site will REACH the number is the full report's question.
 *
 * Every pin is logged as a lead with its district. Outside a covered state the
 * response is the waitlist — capture, not failure (OVERVIEW.md §4) — and the
 * page says so instead of pretending an answer.
 *
 * This route is lazy-loaded (routes.tsx) because it carries Leaflet, and the
 * public report must not pay for a mapping library it never draws.
 *
 * The search box above the map is NAVIGATION ONLY — it flies the map to a
 * typed place so the customer can then click or drag the pin to the exact
 * spot. Nothing from the search is recorded or trusted: the pin is the sole
 * input, which is why this box is allowed here while the console's Geocoding
 * panel forbids one (there, a search box would be a fourth geocoder quietly
 * influencing a resolution of record; here it only moves the viewport).
 * Nominatim's public search is keyless and free — explicit one-shot lookups
 * on a button press, well inside its fair-use policy.
 */

const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

/** Kerala/Tamil Nadu, the covered states — where most pins will land. */
const DEFAULT_CENTRE: [number, number] = [10.2, 77.2];

// Same trick as the console's Geocoding panel: Leaflet's default marker icons
// break under a bundler; a CSS circle is easier to aim anyway.
const PIN = L.divIcon({
  className: "",
  html: '<div style="width:14px;height:14px;border-radius:50%;background:#1c1917;border:2px solid #fff;box-shadow:0 0 0 2px rgba(28,25,23,.35)"></div>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

interface TapOut {
  label: string;
  provided: boolean;
  effect: string;
}

interface TeaserOut {
  /** null = the margin is negative: no utilisation breaks even. */
  breakeven_utilisation: number | null;
  breakeven_kwh_year: number | null;
  breakeven_kwh_day: number | null;
  connectors: number;
  rated_kw_each: number;
  selling_paise_per_kwh: number;
  sanctioned_kva: number;
  energy_tariff_paise_per_kwh: number;
  tariff_source: string;
  taps: TapOut[];
  notes: string[];
}

interface AssessOut {
  site_id: string;
  requests: number;
  district: string | null;
  state: string | null;
  confidence: string | null;
  boundary_ambiguous: boolean;
  /** PLAN 1.6: 1 = full report · 2 = breakeven + tariff audit · 3 = waitlist. */
  tier: number | null;
  tier_why: string | null;
  waitlisted: boolean;
  waitlist_reason: string | null;
  teaser: TeaserOut | null;
}

interface AssessIn {
  lat: number;
  lng: number;
  existing_connection: boolean | null;
  sanctioned_kva: number | null;
  transformer_on_site: boolean | null;
  land_owned: boolean | null;
  budget_band: string | null;
}

function ClickToPlace({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({ click: (e) => onPick(e.latlng.lat, e.latlng.lng) });
  return null;
}

/** Flies the map when a search result is chosen. Render-only side effect. */
function FlyTo({ target }: { target: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo(target, 16, { duration: 1.2 });
  }, [target, map]);
  return null;
}

/** One Nominatim search hit — only what the navigation needs. */
interface Place {
  display_name: string;
  lat: string;
  lon: string;
}

export function Assess() {
  const [pin, setPin] = useState<[number, number] | null>(null);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<Place[] | null>(null);
  const [focus, setFocus] = useState<[number, number] | null>(null);
  const [connection, setConnection] = useState("");
  const [kva, setKva] = useState("");
  const [transformer, setTransformer] = useState("");
  const [land, setLand] = useState("");
  const [budget, setBudget] = useState("");

  async function search() {
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    try {
      const res = await fetch(
        "https://nominatim.openstreetmap.org/search?format=jsonv2&countrycodes=in&limit=5&q=" +
          encodeURIComponent(q),
      );
      setResults(res.ok ? ((await res.json()) as Place[]) : []);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  function goTo(p: Place) {
    const at: [number, number] = [Number(p.lat), Number(p.lon)];
    setPin(at);
    setFocus(at);
    setResults(null);
  }

  const assess = useMutation({
    mutationFn: async (body: AssessIn): Promise<AssessOut> => {
      const res = await fetch("/api/internal/assess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      return (await res.json()) as AssessOut;
    },
  });

  function submit() {
    if (!pin) return;
    assess.mutate({
      lat: pin[0],
      lng: pin[1],
      existing_connection: connection === "" ? null : connection === "yes",
      sanctioned_kva: kva === "" ? null : Number(kva),
      transformer_on_site: transformer === "" ? null : transformer === "yes",
      land_owned: land === "" ? null : land === "owned",
      budget_band: budget === "" ? null : budget,
    });
  }

  const out = assess.data ?? null;

  return (
    <div className="mx-auto max-w-[52rem] px-6 py-12">
      <header className="flex items-baseline justify-between border-b-2 border-rule-strong pb-3">
        <p className="font-ui text-[13px] font-bold tracking-[0.08em] uppercase">
          EV Site Intelligence
        </p>
        <p className="font-data text-[11px] text-ink-faint">breakeven teaser · free</p>
      </header>

      <h1 className="mt-8 max-w-[34rem] text-[1.125rem] leading-tight">
        Drop a pin. The utilisation this site must reach to break even — in 30 seconds, from
        arithmetic, before any model.
      </h1>

      <div className="mt-6 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void search();
          }}
          placeholder="type a place — town, landmark, junction…"
          className="min-w-0 flex-1 border border-rule bg-ground px-2 py-1.5 font-data text-[13px]"
        />
        <button
          type="button"
          onClick={() => void search()}
          disabled={searching || !query.trim()}
          className="border border-rule-strong px-3 py-1.5 font-ui text-[12px] font-bold tracking-[0.04em] uppercase disabled:opacity-40"
        >
          {searching ? "…" : "Find"}
        </button>
      </div>
      {results &&
        (results.length ? (
          <ul className="border-x border-b border-rule">
            {results.map((r) => (
              <li key={`${r.lat},${r.lon}`}>
                <button
                  type="button"
                  onClick={() => goTo(r)}
                  className="block w-full border-b border-rule px-2 py-1.5 text-left font-data text-[12px] text-ink-muted hover:bg-ground-sunk"
                >
                  {r.display_name}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="border-x border-b border-rule px-2 py-1.5 font-data text-[12px] text-ink-faint">
            nothing found — try a nearby town, then drag the pin to the spot
          </p>
        ))}

      <div className="mt-2 h-[300px] border border-rule">
        <MapContainer
          center={DEFAULT_CENTRE}
          zoom={7}
          className="h-full w-full"
          scrollWheelZoom={true}
        >
          <TileLayer url={TILE_URL} attribution="© OpenStreetMap contributors" />
          <ClickToPlace onPick={(lat, lng) => setPin([lat, lng])} />
          <FlyTo target={focus} />
          {pin && (
            <Marker
              position={pin}
              icon={PIN}
              draggable
              eventHandlers={{
                dragend: (e) => {
                  const at = (e.target as L.Marker).getLatLng();
                  setPin([at.lat, at.lng]);
                },
              }}
            />
          )}
        </MapContainer>
      </div>
      <p className="mt-1 font-data text-[11px] text-ink-faint">
        {pin
          ? `pin at ${pin[0].toFixed(5)}, ${pin[1].toFixed(5)} — drag it or click to adjust; the pin, not the search, is what gets assessed`
          : "type a place to jump there, or click the map — then drag the pin to the exact spot"}
      </p>

      <h2 className="mt-8 mb-3 border-b border-rule pb-2 font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
        Five taps sharpen it — every one optional
      </h2>
      <div className="grid gap-2">
        <TapSelect
          label="Existing electricity connection?"
          value={connection}
          onChange={setConnection}
          options={[
            ["yes", "yes"],
            ["no", "no"],
          ]}
        />
        <div className="flex items-baseline justify-between gap-4 border-b border-rule py-1.5">
          <label htmlFor="tap-kva" className="font-ui text-[13px] text-ink-muted">
            Sanctioned load (kVA)?
          </label>
          <input
            id="tap-kva"
            type="number"
            min="1"
            max="5000"
            value={kva}
            onChange={(e) => setKva(e.target.value)}
            placeholder="not provided"
            className="w-36 border border-rule bg-ground px-2 py-1 text-right font-data text-[13px]"
          />
        </div>
        <TapSelect
          label="Transformer on site?"
          value={transformer}
          onChange={setTransformer}
          options={[
            ["yes", "yes"],
            ["no", "no"],
          ]}
        />
        <TapSelect
          label="Land owned or leased?"
          value={land}
          onChange={setLand}
          options={[
            ["owned", "owned"],
            ["leased", "leased"],
          ]}
        />
        <TapSelect
          label="Budget band?"
          value={budget}
          onChange={setBudget}
          options={[
            ["under ₹10 L", "under ₹10 L"],
            ["₹10–25 L", "₹10–25 L"],
            ["₹25–50 L", "₹25–50 L"],
            ["₹50 L +", "₹50 L +"],
          ]}
        />
      </div>

      <button
        type="button"
        onClick={submit}
        disabled={!pin || assess.isPending}
        className="mt-6 border border-rule-strong px-4 py-2 font-ui text-[13px] font-bold tracking-[0.04em] uppercase disabled:opacity-40"
      >
        {assess.isPending ? "computing…" : "Compute breakeven"}
      </button>

      {assess.isError && (
        <p className="mt-4 max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          The request failed ({String(assess.error)}). Nothing was priced; try again.
        </p>
      )}

      {out?.waitlisted && (
        <div className="mt-8 border-y border-rule py-6">
          <p className="font-ui text-[11px] font-bold tracking-[0.08em] text-warn uppercase">
            On the waitlist
          </p>
          <p className="mt-2 max-w-prose text-[13px]">{out.waitlist_reason}</p>
          {out.district && (
            <p className="mt-2 font-data text-[11px] text-ink-faint">
              {out.district} · {out.state} · request #{out.requests} for this spot
            </p>
          )}
        </div>
      )}

      {out?.teaser && (
        <div className="mt-8 border-y border-rule py-6">
          <p className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
            {out.district} · {out.state}
            {out.boundary_ambiguous && " · near a district border — two tariff regimes"}
          </p>
          {out.teaser.breakeven_utilisation !== null ? (
            <>
              <p className="num mt-2 text-[2.75rem] leading-none font-bold">
                {formatUtilisation(out.teaser.breakeven_utilisation)}
              </p>
              <p className="num mt-1 text-[13px] text-ink-muted">
                breakeven utilisation · {out.teaser.connectors} × {out.teaser.rated_kw_each} kW DC ·
                ≈ {Math.round(out.teaser.breakeven_kwh_day ?? 0)} kWh/day
              </p>
            </>
          ) : (
            <p className="mt-2 max-w-prose bg-warn-ground px-2 py-1 text-[13px] text-warn">
              No utilisation breaks even at the assumed price against this tariff — the notes below
              say why. That is an answer, not an error.
            </p>
          )}
          <p className="mt-3 font-data text-[11px] text-ink-faint">
            selling {formatRupeesPrecise(out.teaser.selling_paise_per_kwh as Paise)}/kWh · energy
            tariff {formatRupeesPrecise(out.teaser.energy_tariff_paise_per_kwh as Paise)}/kWh (
            {out.teaser.tariff_source}) · {Math.round(out.teaser.sanctioned_kva)} kVA
          </p>
          {out.tier !== null && (
            <p className="mt-1 font-data text-[11px] text-ink-faint">
              data tier {out.tier} — {out.tier_why}
            </p>
          )}

          <dl className="mt-6 border-t border-rule">
            {out.teaser.taps.map((t) => (
              <div key={t.label} className="border-b border-rule py-1.5">
                <div className="flex items-baseline justify-between gap-4">
                  <dt className="font-ui text-[13px] text-ink-muted">{t.label}</dt>
                  {!t.provided && (
                    <span className="bg-warn-ground px-1 font-data text-[12px] text-warn">
                      not provided ⚠
                    </span>
                  )}
                </div>
                <dd className="mt-0.5 max-w-prose font-data text-[11px] text-ink-faint">
                  {t.effect}
                </dd>
              </div>
            ))}
          </dl>

          {out.teaser.notes.map((n) => (
            <p key={n} className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
              {n}
            </p>
          ))}
        </div>
      )}

      <p className="mt-8">
        <Link
          to={`/report/${DEMO_REPORT_ID}`}
          className="font-ui text-[13px] underline underline-offset-4"
        >
          What the full assessment looks like →
        </Link>
      </p>
      <p className="mt-4 max-w-[34rem] font-data text-[11px] text-ink-faint">
        kerala &amp; tamil nadu today. a pin elsewhere joins the district waitlist — the queue
        decides which state's tariffs we load next. every pin is logged as a lead.
      </p>
    </div>
  );
}

function TapSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-rule py-1.5">
      <label htmlFor={`tap-${label}`} className="font-ui text-[13px] text-ink-muted">
        {label}
      </label>
      <select
        id={`tap-${label}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-36 border border-rule bg-ground px-2 py-1 font-data text-[13px]"
      >
        <option value="">not provided</option>
        {options.map(([v, text]) => (
          <option key={v} value={v}>
            {text}
          </option>
        ))}
      </select>
    </div>
  );
}
