import { useEffect } from "react";
import { MapContainer, Marker, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

/**
 * The map stays continuous behind every step, so location context is never
 * lost — a non-negotiable from design/IMPLEMENT.md.
 *
 * Dimmed, aria-hidden and inert: it is context, not an interface. OSM tiles
 * are pulled into the dark ground by the .cw-map-dark filter, which is our
 * Leaflet rendering of the published Mapbox dark style (design/DECISIONS.md
 * (c) — the style is a colour specification, not a dependency).
 */

const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

const PIN = L.divIcon({
  className: "",
  html: '<div class="cw-pin"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

/** Follows the confirmed site without remounting the map. */
function Follow({ centre }: { centre: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(centre, map.getZoom(), { animate: true, duration: 0.7 });
  }, [centre, map]);
  return null;
}

export function BackgroundMap({ pin }: { pin: { lat: number; lng: number } }) {
  const centre: [number, number] = [pin.lat, pin.lng];
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-0 opacity-30">
      <MapContainer
        center={centre}
        zoom={13}
        className="cw-map-dark h-full w-full"
        zoomControl={false}
        attributionControl={false}
        dragging={false}
        scrollWheelZoom={false}
        doubleClickZoom={false}
        touchZoom={false}
        keyboard={false}
      >
        <TileLayer url={TILE_URL} />
        <Follow centre={centre} />
        <Marker position={centre} icon={PIN} interactive={false} />
      </MapContainer>
    </div>
  );
}

export default BackgroundMap;
