import { Circle, MapContainer, Marker, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

/**
 * The landing hero's map: decorative, non-interactive, aria-hidden. The pin
 * and the 3 / 5 / 10 km catchment rings sit on the demo report's real site
 * (Kazhakkoottam, NH-66) - the same corridor the paper preview beside it
 * judges, so the two halves of the hero tell one story.
 *
 * Lazy-loaded (routes-level React.lazy in Landing.tsx) because it carries
 * Leaflet - the same payload discipline as the flow and the console's
 * geocoding panel (FINDINGS D11). The chunk is shared with the flow, so a
 * visitor who scrolls the landing has already paid for the map the flow
 * needs.
 */

const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

/** The demo site - KL-TVM-DEMO-001's pin. */
const CENTRE: [number, number] = [8.5695, 76.873];

const PIN = L.divIcon({
  className: "",
  html: '<div class="cw-pin"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

export function HeroMap() {
  return (
    <div
      aria-hidden="true"
      className="h-[clamp(260px,42vw,452px)] w-full border border-cw-line bg-cw-surface"
    >
      <MapContainer
        center={CENTRE}
        zoom={11}
        className="cw-map-dark h-full w-full"
        zoomControl={false}
        dragging={false}
        scrollWheelZoom={false}
        doubleClickZoom={false}
        touchZoom={false}
        keyboard={false}
        attributionControl={true}
      >
        <TileLayer url={TILE_URL} attribution="© OpenStreetMap contributors" />
        {[3000, 5000, 10000].map((r) => (
          <Circle key={r} center={CENTRE} radius={r} pathOptions={{ className: "cw-ring" }} />
        ))}
        <Marker position={CENTRE} icon={PIN} interactive={false} />
      </MapContainer>
    </div>
  );
}

export default HeroMap;
