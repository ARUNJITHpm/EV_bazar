import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { MapPin, Minus, Plus } from "lucide-react";
import { api } from "../../../api/client";
import { MAPBOX_TOKEN, MAP_STYLE, autoResize, mapboxgl } from "../mapCore";
import { LocationSearch, type SiteLocation } from "../LocationSearch";
import { toBody, type AssessOut } from "./state";

/** Only explicit confirmation records the customer’s pin; search results are previews. */
export function Locate({
  pin,
  location,
  onPin,
  onSelect,
  confirmed,
  onChecked,
  onContinue,
}: {
  pin: { lat: number; lng: number } | null;
  location?: SiteLocation;
  onPin: (pin: { lat: number; lng: number }) => void;
  onSelect: (site: SiteLocation) => void;
  confirmed: AssessOut | null;
  onChecked: (out: AssessOut) => void;
  onContinue: (out: AssessOut) => void;
}) {
  const seeded = (useLocation().state as { q?: string } | null)?.q ?? "";
  const [searchOpen, setSearchOpen] = useState(!pin);
  const [checking, setChecking] = useState(false);
  const [moving, setMoving] = useState(false);
  const [failed, setFailed] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [mapFailed, setMapFailed] = useState(!MAPBOX_TOKEN);
  const [satellite, setSatellite] = useState(false);
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const initial = useRef(pin);
  const current = useRef({ onPin, pin, searchOpen, checking });
  current.current = { onPin, pin, searchOpen, checking };

  useEffect(() => {
    if (!mapEl.current || !MAPBOX_TOKEN) return;
    let map: mapboxgl.Map;
    try {
      map = new mapboxgl.Map({
        container: mapEl.current,
        style: MAP_STYLE,
        center: initial.current ?? { lng: 77.2, lat: 10.2 },
        zoom: initial.current ? 17 : 6,
      });
    } catch {
      setMapFailed(true);
      return;
    }
    mapRef.current = map;
    const stopResize = autoResize(map, mapEl.current);
    map.on("style.load", () => {
      setMapFailed(false);
    });
    map.on("idle", () => {
      setMapReady(true);
      setMapFailed(false);
    });
    map.on("error", () => {
      if (!map.loaded()) setMapFailed(true);
    });
    map.on("movestart", () => setMoving(true));
    map.on("moveend", () => {
      setMoving(false);
      const { pin: selected, checking: pending, searchOpen: searching } = current.current;
      if (pending || (!selected && searching)) return;
      const centre = map.getCenter();
      if (
        !selected ||
        Math.abs(selected.lat - centre.lat) > 1e-8 ||
        Math.abs(selected.lng - centre.lng) > 1e-8
      )
        current.current.onPin({ lat: centre.lat, lng: centre.lng });
    });
    map.on("click", (e) => {
      if (!current.current.searchOpen && !current.current.checking)
        map.easeTo({ center: e.lngLat, duration: 0 });
    });
    return () => {
      stopResize();
      mapRef.current = null;
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!checking) {
      map.dragPan.enable();
      map.keyboard.enable();
    } else {
      map.dragPan.disable();
      map.keyboard.disable();
    }
  }, [checking, mapReady]);

  function select(site: SiteLocation) {
    onSelect(site);
    setSearchOpen(false);
    setFailed(false);
    mapRef.current?.jumpTo({ center: { lat: site.lat, lng: site.lng }, zoom: 17 });
  }

  async function confirm() {
    if (!pin || checking || moving || !mapReady || mapFailed) return;
    setChecking(true);
    setFailed(false);
    try {
      if (confirmed) {
        onContinue(confirmed);
        return;
      }
      const { data } = await api.POST("/api/internal/assess", { body: toBody(pin, {}) });
      if (!data) {
        setFailed(true);
        return;
      }
      onChecked(data);
      onContinue(data);
    } catch {
      setFailed(true);
    } finally {
      setChecking(false);
    }
  }

  return (
    <section
      className="site-locate"
      data-search={searchOpen}
      aria-labelledby="site-location-heading"
    >
      <div className="site-location-panel">
        <h1 id="site-location-heading" className="text-[28px] leading-[1.2] font-medium">
          {pin ? "Is this your site?" : "Find your site"}
        </h1>
        {searchOpen ? (
          <fieldset disabled={checking} className="mt-5 min-w-0">
            <LocationSearch
              id="assess-location"
              initialQuery={seeded}
              onSelect={select}
              onChooseMap={() => {
                setSearchOpen(false);
                if (!pin && mapRef.current) {
                  const p = mapRef.current.getCenter();
                  onPin({ lat: p.lat, lng: p.lng });
                }
              }}
            />
            {pin && (
              <button
                type="button"
                onClick={() => setSearchOpen(false)}
                className="mt-2 min-h-[44px] underline underline-offset-4"
              >
                Back to selected site
              </button>
            )}
          </fieldset>
        ) : (
          <>
            <p className="mt-3 text-cw-muted">{location?.name ?? "Your selected site"}</p>
            <p className="mt-4 text-[15px]">
              {location?.area
                ? "Choose your property within this area. Move the map so the pin sits on your site."
                : "Move the map under the pin, or tap your property."}
            </p>
            <div className="mt-3 flex flex-wrap gap-x-6">
              <button
                type="button"
                disabled={checking}
                onClick={() => setSearchOpen(true)}
                className="min-h-[44px] text-cw-muted underline underline-offset-4"
              >
                Search another place
              </button>
            </div>
          </>
        )}
        {mapFailed && (
          <p role="alert" className="mt-4 text-[15px] text-cw-negative">
            The map could not load. Reload to check the pin before continuing.
          </p>
        )}
        {failed && (
          <p role="alert" className="mt-4 text-[15px] text-cw-negative">
            We could not confirm the location. Your pin is saved; please try again.
          </p>
        )}
        {!searchOpen && (
          <button
            type="button"
            onClick={() => void confirm()}
            disabled={!pin || checking || moving || !mapReady || mapFailed}
            className="location-primary mt-5 w-full"
          >
            {checking ? "Confirming…" : "Confirm location"}
          </button>
        )}
      </div>
      <div className="site-map" aria-label="Site location map">
        <div ref={mapEl} className="h-full w-full" />
        {!searchOpen && (
          <div className="site-centre-pin" aria-hidden="true">
            <MapPin size={42} fill="var(--cw-accent)" stroke="var(--cw-ground)" strokeWidth={1.5} />
          </div>
        )}
        {mapReady && !mapFailed && (
          <div className="site-map-controls">
            <button
              type="button"
              disabled={checking}
              aria-pressed={satellite}
              onClick={() => {
                const next = !satellite;
                setSatellite(next);
                setMapReady(false);
                mapRef.current?.setStyle(
                  next ? "mapbox://styles/mapbox/satellite-streets-v12" : MAP_STYLE,
                );
              }}
            >
              {satellite ? "Street view" : "Satellite view"}
            </button>
            <button
              type="button"
              disabled={checking}
              aria-label="Zoom in"
              onClick={() => mapRef.current?.zoomIn({ duration: 0 })}
            >
              <Plus size={20} />
            </button>
            <button
              type="button"
              disabled={checking}
              aria-label="Zoom out"
              onClick={() => mapRef.current?.zoomOut({ duration: 0 })}
            >
              <Minus size={20} />
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
