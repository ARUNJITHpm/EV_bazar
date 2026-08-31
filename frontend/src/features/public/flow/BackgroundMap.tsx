import { useEffect, useRef } from "react";

import { MAP_STYLE, createPinElement, mapboxgl } from "../mapCore";

/**
 * The map stays continuous behind every step, so location context is never
 * lost — a non-negotiable from design/IMPLEMENT.md.
 *
 * Dimmed, aria-hidden and inert: it is context, not an interface. This is
 * the published Chargeworthy dark style itself, quiet enough at 30% that the
 * question column needs no scrim over it (the scrim existed to tame the
 * filtered-OSM approximation this replaced). Attribution for the same data
 * is carried by the flow's footer.
 */

export function BackgroundMap({ pin }: { pin: { lat: number; lng: number } }) {
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markerRef = useRef<mapboxgl.Marker | null>(null);
  // Construction-time view only; later pin moves go through easeTo below.
  const initial = useRef(pin);

  useEffect(() => {
    if (!el.current) return;
    let map: mapboxgl.Map;
    try {
      map = new mapboxgl.Map({
        container: el.current,
        style: MAP_STYLE,
        center: { lng: initial.current.lng, lat: initial.current.lat },
        zoom: 12,
        interactive: false,
        attributionControl: false,
      });
    } catch {
      return;
    }
    mapRef.current = map;
    return () => {
      mapRef.current = null;
      markerRef.current = null;
      map.remove();
    };
  }, []);

  // Follows the confirmed site without remounting the map.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const at = { lng: pin.lng, lat: pin.lat };
    if (!markerRef.current) {
      markerRef.current = new mapboxgl.Marker({ element: createPinElement(), anchor: "bottom" })
        .setLngLat(at)
        .addTo(map);
      map.jumpTo({ center: at });
    } else {
      markerRef.current.setLngLat(at);
      map.easeTo({ center: at, duration: 700 });
    }
  }, [pin.lat, pin.lng]);

  return (
    <div
      ref={el}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 z-0 bg-cw-ground opacity-30"
    />
  );
}

export default BackgroundMap;
