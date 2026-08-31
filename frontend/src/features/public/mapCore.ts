import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

/**
 * The published Chargeworthy dark style, rendered by the library it was
 * built for. design/DECISIONS.md (c) chose Leaflet + a CSS filter while the
 * style existed only as a colour specification; the owner has since supplied
 * the style's own credentials (design/MAPBOX.md), so the public surface now
 * renders the real thing. The console keeps Leaflet - its maps are
 * operational tools, not the brand surface.
 *
 * The token is a Mapbox PUBLIC token (pk.). It ships in the client bundle by
 * design - hiding it from a browser map is not possible - so the control is
 * URL restriction in the Mapbox console, not secrecy. It is injected at BUILD
 * time from VITE_MAPBOX_TOKEN (frontend/.env.local for dev; an HF Space
 * Variable in production) rather than committed, so the repo carries no token
 * for a scanner to trip over. Absent, every map here degrades to an empty
 * panel and the page keeps working (see the try/catch in each map component).
 * Rotating it means changing the env value, nowhere in git. See MAPBOX.md.
 */
export const MAPBOX_TOKEN: string = import.meta.env.VITE_MAPBOX_TOKEN ?? "";

export const MAP_STYLE = "mapbox://styles/chargeworthy/cmtcw48t4002401s146owc0tv";

if (!MAPBOX_TOKEN) {
  // One quiet line, not a throw: a missing token must not take the page down.
  console.warn("[Chargeworthy] VITE_MAPBOX_TOKEN is not set - maps will not render.");
}
mapboxgl.accessToken = MAPBOX_TOKEN;

/** Mapbox paint properties need literal colours, so tokens are read from the
 * cascade at call time - tokens.css stays the single source. */
function cssToken(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/**
 * Mapbox reads the container size ONCE at construction. In a flex / absolute
 * layout the container is often not at its final height yet on the frame the
 * map is created, so the first paint is black until something forces a
 * resize. Observing the container and calling `map.resize()` on every change
 * fixes the initial settle and later viewport/rotation changes alike (the RO
 * fires immediately on observe, so a correct size costs one harmless resize).
 * Returns a disconnect for effect cleanup.
 */
export function autoResize(map: mapboxgl.Map, container: HTMLElement): () => void {
  const ro = new ResizeObserver(() => map.resize());
  ro.observe(container);
  // The observer's first fire can land before the GL context is ready, so it
  // does not un-black the initial paint on its own. A resize once the style
  // has loaded guarantees the first real paint; the observer then handles
  // every later size change (rotation, the flex settling).
  map.once("load", () => map.resize());
  return () => ro.disconnect();
}

/**
 * The copper pin as a DOM element for mapboxgl.Marker (anchor: "bottom").
 * Colours are inline var() styles, not presentation attributes, so the
 * tokens resolve from CSS and no raw hex lands in a component.
 */
export function createPinElement({ draggable = false } = {}): HTMLDivElement {
  const el = document.createElement("div");
  el.style.width = "34px";
  el.style.height = "44px";
  el.style.cursor = draggable ? "grab" : "default";
  el.innerHTML = `
    <svg width="34" height="44" viewBox="0 0 34 44" fill="none" aria-hidden="true">
      <path d="M17 4a13 13 0 0 1 13 13c0 10-13 25-13 25S4 27 4 17A13 13 0 0 1 17 4z"
            style="fill:var(--cw-accent)"/>
      <circle cx="17" cy="17" r="4.6" style="fill:var(--cw-ground)"/>
    </svg>`;
  return el;
}

/** A circle as a GeoJSON polygon, so a radius ring means an actual distance
 * on the ground rather than being decoration. */
function circlePolygon(lng: number, lat: number, radiusKm: number, steps = 96) {
  const latRad = (lat * Math.PI) / 180;
  const kmPerDegLat = 110.574;
  const kmPerDegLng = 111.32 * Math.cos(latRad);
  const coords: [number, number][] = [];
  for (let i = 0; i <= steps; i += 1) {
    const theta = (i / steps) * 2 * Math.PI;
    coords.push([
      lng + (radiusKm / kmPerDegLng) * Math.cos(theta),
      lat + (radiusKm / kmPerDegLat) * Math.sin(theta),
    ]);
  }
  return {
    type: "Feature" as const,
    geometry: { type: "Polygon" as const, coordinates: [coords] },
    properties: { radiusKm },
  };
}

const RING_SOURCE = "cw-rings";

/**
 * The catchment radii as real circles - the same 3 / 5 / 10 km bands the
 * assessment itself uses, so the rings on screen are the ones in the report.
 * Call from the map's "load" handler.
 */
export function setRings(
  map: mapboxgl.Map,
  centre: { lng: number; lat: number },
  radiiKm: number[] = [3, 5, 10],
): void {
  const data = {
    type: "FeatureCollection" as const,
    features: radiiKm.map((r) => circlePolygon(centre.lng, centre.lat, r)),
  };
  const existing = map.getSource(RING_SOURCE) as mapboxgl.GeoJSONSource | undefined;
  if (existing) {
    existing.setData(data);
    return;
  }
  map.addSource(RING_SOURCE, { type: "geojson", data });
  map.addLayer({
    id: "cw-rings-line",
    type: "line",
    source: RING_SOURCE,
    paint: {
      "line-color": cssToken("--cw-slate"),
      "line-width": 1,
      // Inner rings read slightly stronger than outer ones.
      "line-opacity": ["interpolate", ["linear"], ["get", "radiusKm"], 3, 0.42, 10, 0.16],
    },
  });
}

export { mapboxgl };
