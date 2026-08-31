import { useEffect, useRef } from "react";

import { MAP_STYLE, createPinElement, mapboxgl, setRings } from "./mapCore";

/**
 * The landing hero's map: decorative, non-interactive, aria-hidden. The pin
 * and the 3 / 5 / 10 km catchment rings sit on the demo report's real site
 * (Kazhakkoottam, NH-66) - the same corridor the paper preview beside it
 * judges, so the two halves of the hero tell one story.
 *
 * Lazy-loaded (routes-level React.lazy in Landing.tsx) because it carries
 * Mapbox GL - the same payload discipline as the flow (FINDINGS D11). The
 * chunk is shared with the flow, so a visitor who scrolls the landing has
 * already paid for the map the flow needs.
 */

/** The demo site - KL-TVM-DEMO-001's pin. */
const CENTRE = { lng: 76.873, lat: 8.5695 };

export function HeroMap() {
  const el = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!el.current) return;
    // A rejected token or missing WebGL must not take the hero down with it:
    // the panel stays an empty surface and the page keeps working.
    let map: mapboxgl.Map;
    try {
      map = new mapboxgl.Map({
        container: el.current,
        style: MAP_STYLE,
        center: CENTRE,
        zoom: 10.2,
        interactive: false,
      });
    } catch {
      return;
    }
    map.on("load", () => {
      setRings(map, CENTRE);
      new mapboxgl.Marker({ element: createPinElement(), anchor: "bottom" })
        .setLngLat(CENTRE)
        .addTo(map);
    });
    return () => map.remove();
  }, []);

  return (
    <div
      ref={el}
      aria-hidden="true"
      className="h-[clamp(260px,42vw,452px)] w-full border border-cw-line bg-cw-surface"
    />
  );
}

export default HeroMap;
