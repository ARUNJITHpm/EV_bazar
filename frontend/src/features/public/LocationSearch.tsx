import { useRef, useState, type FormEvent } from "react";
import { LocateFixed } from "lucide-react";

export interface SiteLocation {
  lat: number;
  lng: number;
  name: string;
  area: boolean;
}

interface SearchResult {
  display_name: string;
  lat: string;
  lon: string;
  addresstype?: string;
  type?: string;
}

const areas = new Set([
  "state",
  "county",
  "city",
  "town",
  "village",
  "suburb",
  "municipality",
  "district",
  "postcode",
  "neighbourhood",
  "administrative",
]);
const searchCache = new Map<string, SearchResult[]>();
let lastSearchAt = 0;

/** Explicit searches only: the current provider does not permit autocomplete. */
export function LocationSearch({
  id,
  initialQuery = "",
  onSelect,
  onChooseMap,
}: {
  id: string;
  initialQuery?: string;
  onSelect: (site: SiteLocation) => void;
  onChooseMap?: () => void;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [busy, setBusy] = useState<"search" | "position" | null>(null);
  const [error, setError] = useState("");
  const activeQuery = useRef(query);
  activeQuery.current = query;

  async function search(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (!q || busy) return;
    setBusy("search");
    setError("");
    setResults(null);
    try {
      const cached = searchCache.get(q.toLocaleLowerCase());
      if (cached) {
        setResults(cached);
        return;
      }
      if (Date.now() - lastSearchAt < 1000) throw new Error("search rate limit");
      lastSearchAt = Date.now();
      const response = await fetch(
        "https://nominatim.openstreetmap.org/search?format=jsonv2&countrycodes=in&limit=5&q=" +
          encodeURIComponent(q),
      );
      if (!response.ok) throw new Error("search failed");
      const body: unknown = await response.json();
      if (!Array.isArray(body)) throw new Error("invalid search");
      const valid = body.filter(
        (r): r is SearchResult =>
          typeof r === "object" &&
          r !== null &&
          typeof r.display_name === "string" &&
          typeof r.lat === "string" &&
          typeof r.lon === "string" &&
          r.lat.trim() !== "" &&
          r.lon.trim() !== "" &&
          Number.isFinite(Number(r.lat)) &&
          Number.isFinite(Number(r.lon)) &&
          Math.abs(Number(r.lat)) <= 90 &&
          Math.abs(Number(r.lon)) <= 180,
      );
      searchCache.set(q.toLocaleLowerCase(), valid);
      if (activeQuery.current.trim() === q) setResults(valid);
    } catch {
      setError(
        "Search is unavailable. Try again, use your current location, or choose on the map.",
      );
    } finally {
      setBusy(null);
    }
  }

  function locate() {
    if (!navigator.geolocation) {
      setError("This browser cannot share your location. Search for an address instead.");
      return;
    }
    setBusy("position");
    setError("");
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setBusy(null);
        onSelect({
          lat: coords.latitude,
          lng: coords.longitude,
          name: "Your current location",
          area: true,
        });
      },
      () => {
        setBusy(null);
        setError(
          "We could not get your location. Allow location access, or search for an address.",
        );
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  }

  return (
    <div className="location-search">
      <form onSubmit={search}>
        <label htmlFor={id} className="mb-2 block font-medium">
          Site location
        </label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            id={id}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setResults(null);
              setError("");
            }}
            placeholder="Enter a property, address or town"
            aria-describedby={`${id}-help`}
            className="min-h-[58px] min-w-0 flex-1 border border-cw-line bg-cw-surface px-5 text-cw-text placeholder:text-cw-muted"
          />
          <button type="submit" disabled={!!busy || !query.trim()} className="location-primary">
            {busy === "search" ? "Searching…" : "Find location"}
          </button>
        </div>
        <p id={`${id}-help`} className="mt-3 text-[15px] text-cw-muted">
          Choose a place, then confirm your site on the map.
        </p>
      </form>
      <div aria-live="polite">
        {results &&
          (results.length ? (
            <ul className="location-results" aria-label="Matching places">
              {results.map((r) => {
                const [name, ...address] = r.display_name.split(",");
                return (
                  <li key={`${r.lat},${r.lon},${r.display_name}`}>
                    <button
                      type="button"
                      disabled={!!busy}
                      onClick={() =>
                        onSelect({
                          lat: Number(r.lat),
                          lng: Number(r.lon),
                          name: r.display_name,
                          area: areas.has(r.addresstype ?? r.type ?? ""),
                        })
                      }
                    >
                      <span className="block font-medium">{name}</span>
                      <span className="block text-[15px] text-cw-muted">
                        {address.join(",").trim()}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="mt-3 text-[15px] text-cw-muted">
              No places found. Try a nearby landmark or choose on the map.
            </p>
          ))}
        {error && (
          <p role="alert" className="mt-3 text-[15px] text-cw-negative">
            {error}
          </p>
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-6">
        <button
          type="button"
          onClick={locate}
          disabled={!!busy}
          className="inline-flex min-h-[44px] items-center gap-2 text-[15px] text-cw-text underline underline-offset-4"
        >
          <LocateFixed size={18} aria-hidden="true" />
          {busy === "position" ? "Getting your location…" : "Use my current location"}
        </button>
        {onChooseMap && (
          <button
            type="button"
            disabled={!!busy}
            onClick={onChooseMap}
            className="min-h-[44px] text-[15px] text-cw-muted underline underline-offset-4"
          >
            Choose on map
          </button>
        )}
      </div>
      {results && (
        <p className="text-[12px] text-cw-muted">
          Search data ©{" "}
          <a href="https://www.openstreetmap.org/copyright" className="underline">
            OpenStreetMap contributors
          </a>
        </p>
      )}
    </div>
  );
}
