import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

import { api } from "../../../api/client";
import { MAP_STYLE, createPinElement, mapboxgl } from "../mapCore";
import { placeName, toBody, type AssessOut } from "./state";

/**
 * Step one: the map IS the interface, not a backdrop.
 *
 * The search box is NAVIGATION ONLY - it flies the map to a typed place so
 * the customer can then click or drag the pin to the exact spot. Nothing
 * from the search is recorded or trusted: the pin is the sole input. That
 * is why this box is allowed here while the console's Geocoding panel
 * forbids one (there it would be a fourth geocoder quietly influencing a
 * resolution of record; here it only moves the viewport). Nominatim's
 * public search is keyless and free - explicit one-shot lookups on a
 * button press, well inside its fair-use policy.
 *
 * "Check this spot" is a deliberate tap, not a drag side-effect: each press
 * is one POST /assess, which logs the pin as a lead FIRST (the shipped
 * doctrine) and returns our own resolver's district - so an owner who
 * abandons after this point is still a captured lead, and the confirmation
 * card never needs a third-party reverse geocode.
 */

/** Kerala/Tamil Nadu, the covered states - where most pins will land. */
const DEFAULT_CENTRE = { lng: 77.2, lat: 10.2 };

interface Place {
  display_name: string;
  lat: string;
  lon: string;
}

export function Locate({
  pin,
  onPin,
  confirmed,
  onChecked,
  onContinue,
}: {
  pin: { lat: number; lng: number } | null;
  onPin: (pin: { lat: number; lng: number }) => void;
  confirmed: AssessOut | null;
  onChecked: (out: AssessOut) => void;
  onContinue: (out: AssessOut) => void;
}) {
  // The landing's location field hands its text here so nothing typed is lost.
  const seeded = (useLocation().state as { q?: string } | null)?.q ?? "";
  const [query, setQuery] = useState(seeded);
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<Place[] | null>(null);
  const [checking, setChecking] = useState(false);
  const [failed, setFailed] = useState(false);

  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markerRef = useRef<mapboxgl.Marker | null>(null);
  // Latest callback for map event handlers, which outlive any one render.
  const onPinRef = useRef(onPin);
  onPinRef.current = onPin;
  // Construction-time view only: a returning visitor opens on their pin.
  const initial = useRef(pin);

  useEffect(() => {
    if (!mapEl.current) return;
    let map: mapboxgl.Map;
    try {
      map = new mapboxgl.Map({
        container: mapEl.current,
        style: MAP_STYLE,
        center: initial.current ? { lng: initial.current.lng, lat: initial.current.lat } : DEFAULT_CENTRE,
        zoom: initial.current ? 15 : 6,
      });
    } catch {
      return;
    }
    mapRef.current = map;
    map.on("click", (e) => onPinRef.current({ lat: e.lngLat.lat, lng: e.lngLat.lng }));
    return () => {
      mapRef.current = null;
      markerRef.current = null;
      map.remove();
    };
  }, []);

  // The pin is owned by flow state; the marker only mirrors it.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !pin) return;
    const at = { lng: pin.lng, lat: pin.lat };
    if (!markerRef.current) {
      const marker = new mapboxgl.Marker({
        element: createPinElement({ draggable: true }),
        draggable: true,
        anchor: "bottom",
      })
        .setLngLat(at)
        .addTo(map);
      marker.on("dragend", () => {
        const p = marker.getLngLat();
        onPinRef.current({ lat: p.lat, lng: p.lng });
      });
      markerRef.current = marker;
    } else {
      markerRef.current.setLngLat(at);
    }
  }, [pin]);

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
    const at = { lat: Number(p.lat), lng: Number(p.lon) };
    onPin(at);
    mapRef.current?.flyTo({ center: { lng: at.lng, lat: at.lat }, zoom: 15, duration: 1200 });
    setResults(null);
  }

  async function check() {
    if (!pin) return;
    setChecking(true);
    setFailed(false);
    const { data } = await api.POST("/api/internal/assess", { body: toBody(pin, {}) });
    setChecking(false);
    if (data) onChecked(data);
    else setFailed(true);
  }

  return (
    <div className="relative min-h-[60vh] flex-grow">
      <div ref={mapEl} className="absolute inset-0 bg-cw-surface" />

      <div className="absolute top-8 left-1/2 z-[1000] w-[min(620px,calc(100%-40px))] -translate-x-1/2">
        <div className="flex min-h-[58px] items-center gap-3 border border-cw-line bg-cw-surface px-5 text-cw-muted">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void search();
            }}
            placeholder="Drop a pin, or type the location"
            aria-label="Search for the site location"
            autoComplete="off"
            className="min-w-0 flex-grow bg-transparent text-[17px] text-cw-text outline-none placeholder:text-cw-muted"
          />
          <button
            type="button"
            onClick={() => void search()}
            disabled={searching || !query.trim()}
            className="inline-flex min-h-[44px] items-center text-[15px] text-cw-slate disabled:opacity-40"
          >
            {searching ? "…" : "Find"}
          </button>
        </div>
        {results &&
          (results.length ? (
            <ul className="max-h-[46vh] overflow-y-auto border border-t-0 border-cw-line bg-cw-surface">
              {/* Large rows, never a compact dropdown. */}
              {results.map((r) => (
                <li key={`${r.lat},${r.lon}`}>
                  <button
                    type="button"
                    onClick={() => goTo(r)}
                    className="block min-h-[56px] w-full border-b border-cw-line px-5 py-3.5 text-left text-[17px] text-cw-text transition-colors duration-200 hover:bg-cw-surface-2"
                  >
                    {r.display_name}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="border border-t-0 border-cw-line bg-cw-surface px-5 py-3.5 text-[15px] text-cw-muted">
              Nothing found — try a nearby town, then drag the pin to the spot.
            </p>
          ))}
      </div>

      {pin && (
        <div className="absolute bottom-8 left-1/2 z-[1000] flex max-h-[62vh] w-[min(720px,calc(100%-40px))] -translate-x-1/2 flex-col gap-6 overflow-y-auto border border-cw-line bg-cw-surface p-6 sm:p-8">
          <div className="flex flex-col gap-1.5">
            <div className="font-cw-mono text-[13px] tracking-[0.14em] text-cw-muted uppercase">
              {checking ? "Checking…" : confirmed ? "Is this the spot?" : "The pin decides"}
            </div>
            <h2 className="text-[clamp(21px,3vw,27px)] font-medium">
              {confirmed?.district
                ? placeName(confirmed.district, confirmed.state)
                : "Drag the pin to the exact spot"}
            </h2>
          </div>

          <div
            className="grid gap-5"
            style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}
          >
            <Field
              label="Coordinates"
              mono
              value={`${pin.lat.toFixed(4)}, ${pin.lng.toFixed(4)}`}
            />
            <Field
              label="District"
              value={
                confirmed
                  ? (confirmed.district ?? "Not resolved — a human will look")
                  : "Check the spot to find out"
              }
            />
            <Field label="Road class" value="Not yet determined" />
          </div>

          {failed && (
            <p className="text-[15px] text-cw-negative">
              The check failed — nothing was recorded. Try again.
            </p>
          )}

          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-cw-line pt-5">
            <span className="inline-flex min-h-[56px] items-center text-cw-muted">
              Not quite? Drag the pin, or tap the map.
            </span>
            {confirmed ? (
              <button
                type="button"
                onClick={() => onContinue(confirmed)}
                className="inline-flex min-h-[58px] items-center justify-center bg-cw-accent px-7 text-[17px] font-semibold text-cw-ground transition-[filter] duration-200 hover:brightness-107"
              >
                Yes, continue
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void check()}
                disabled={checking}
                className="inline-flex min-h-[58px] items-center justify-center bg-cw-accent px-7 text-[17px] font-semibold text-cw-ground transition-[filter] duration-200 hover:brightness-107 disabled:cursor-wait disabled:opacity-50"
              >
                Check this spot
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-[15px] text-cw-muted">{label}</div>
      <div className={mono ? "font-cw-mono text-[17px] tabular-nums" : "text-[17px]"}>{value}</div>
    </div>
  );
}
