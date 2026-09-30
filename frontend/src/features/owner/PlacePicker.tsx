import { useEffect, useRef, useState } from "react";

import { MAP_STYLE, autoResize, createPinElement, mapboxgl } from "../public/mapCore";
import { inputCls, secondaryCls } from "./ui";

interface Place {
  display_name: string;
  lat: string;
  lon: string;
}

/** Kerala/Tamil Nadu, the covered states - where most stations will be. */
const DEFAULT_CENTRE = { lng: 77.2, lat: 10.2 };

/**
 * Where the station is: type an address and pick a result, or tap the map to drop
 * a pin (and drag it to the exact spot). The pin is what is stored; the address
 * is only text to help the owner recognise it. Nominatim's public search is
 * keyless and one-shot on a button press, well inside its fair-use policy.
 */
export function PlacePicker({
  pin,
  address,
  onChange,
}: {
  pin: { lat: number; lng: number } | null;
  address: string;
  onChange: (p: { pin: { lat: number; lng: number } | null; address: string }) => void;
}) {
  const [query, setQuery] = useState(address);
  const [results, setResults] = useState<Place[] | null>(null);
  const [searching, setSearching] = useState(false);
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markerRef = useRef<mapboxgl.Marker | null>(null);
  const change = useRef(onChange);
  change.current = onChange;
  const addressRef = useRef(address);
  addressRef.current = address;
  const initial = useRef(pin);

  useEffect(() => {
    if (!mapEl.current) return;
    let map: mapboxgl.Map;
    try {
      map = new mapboxgl.Map({
        container: mapEl.current,
        style: MAP_STYLE,
        center: initial.current ?? DEFAULT_CENTRE,
        zoom: initial.current ? 15 : 6,
      });
    } catch {
      return; // no map token: the address search below still works
    }
    mapRef.current = map;
    const stop = autoResize(map, mapEl.current);
    map.on("click", (e) =>
      change.current({
        pin: { lat: e.lngLat.lat, lng: e.lngLat.lng },
        address: addressRef.current,
      }),
    );
    return () => {
      stop();
      mapRef.current = null;
      markerRef.current = null;
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !pin) return;
    if (!markerRef.current) {
      const marker = new mapboxgl.Marker({
        element: createPinElement({ draggable: true }),
        draggable: true,
        anchor: "bottom",
      })
        .setLngLat(pin)
        .addTo(map);
      marker.on("dragend", () => {
        const p = marker.getLngLat();
        change.current({ pin: { lat: p.lat, lng: p.lng }, address: addressRef.current });
      });
      markerRef.current = marker;
    } else {
      markerRef.current.setLngLat(pin);
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

  function pick(p: Place) {
    const at = { lat: Number(p.lat), lng: Number(p.lon) };
    onChange({ pin: at, address: p.display_name });
    setQuery(p.display_name);
    mapRef.current?.flyTo({ center: at, zoom: 16, duration: 900 });
    setResults(null);
  }

  return (
    <div className="flex max-w-[760px] flex-col gap-5">
      <div className="flex gap-3">
        <input
          className={inputCls}
          placeholder="Type the address or town"
          aria-label="Station address"
          value={query}
          autoComplete="off"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void search();
          }}
        />
        <button
          type="button"
          className={secondaryCls}
          disabled={searching || !query.trim()}
          onClick={() => void search()}
        >
          {searching ? "…" : "Find"}
        </button>
      </div>
      {results &&
        (results.length ? (
          <ul className="border border-cw-line bg-cw-surface">
            {results.map((r) => (
              <li key={`${r.lat},${r.lon}`}>
                <button
                  type="button"
                  onClick={() => pick(r)}
                  className="block min-h-[56px] w-full border-b border-cw-line px-5 py-3.5 text-left transition-colors duration-200 hover:bg-cw-surface-2"
                >
                  {r.display_name}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-cw-muted">Nothing found. Try a nearby town, then tap the map.</p>
        ))}
      <div className="relative h-[46vh] min-h-[280px] border border-cw-line bg-cw-surface">
        <div ref={mapEl} className="h-full w-full" />
      </div>
      <p className="text-[15px] text-cw-muted">
        {pin ? (
          <>
            Pin at{" "}
            <span className="font-cw-mono tabular-nums">
              {pin.lat.toFixed(4)}, {pin.lng.toFixed(4)}
            </span>
            . Drag it to the exact spot if needed.
          </>
        ) : (
          "Tap the map to drop a pin, or pick a result above."
        )}
      </p>
    </div>
  );
}
