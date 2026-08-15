import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";
import { useEffect, useState } from "react";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/**
 * PART 1.3 L6 — the geocoding funnel and the manual queue.
 *
 * The funnel is the evidence for Part 1's exit criteria: what share of
 * addresses resolved, what share resolved without a paid call, and what the
 * paid levels actually cost this month. Those are claims the plan makes, and
 * this is where they are checked rather than asserted.
 *
 * The queue is the working surface. Every level of the cascade is allowed to
 * refuse precisely because refusals land here — a human reads the address,
 * clicks the point, and the answer is written back into the geocode cache so
 * nobody is ever asked about that address again.
 *
 * Two deliberate constraints on this page:
 *
 * - **The map is for placing a point, not for browsing.** No search box: a
 *   search box would be a fourth geocoder, unmetered and unrecorded.
 * - **Rejecting is a first-class button.** "I looked and this address does not
 *   describe a place" is a real finding about our input, and it must be as easy
 *   to record as a resolution — otherwise the honest answer is the slow one and
 *   people guess a point instead.
 *
 * Privacy note: tiles come from tile.openstreetmap.org, so the viewport of an
 * address under review leaves the building. Acceptable for an internal console;
 * point TILE_URL at a self-hosted renderer when one exists.
 */

const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

/** Kerala/Tamil Nadu, the Tier 1 area — the queue is almost entirely here. */
const DEFAULT_CENTRE: [number, number] = [10.85, 76.9];

// Leaflet's default marker resolves its icons by relative URL, which a bundler
// rewrites and then cannot find. A CSS circle avoids the whole problem and is
// easier to aim than the teardrop pin anyway.
const PIN = L.divIcon({
  className: "",
  html: '<div style="width:14px;height:14px;border-radius:50%;background:#e0562d;box-shadow:0 0 0 3px rgba(224,86,45,.28)"></div>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

type QueueItem = {
  id: number;
  raw_input: string;
  normalised_input: string;
  pincode: string | null;
  reason: string | null;
  hits: number;
  status: string;
  lat: number | null;
  lng: number | null;
  created_at: string;
};

type Funnel = {
  billing_month: string;
  cached_addresses: number;
  resolved: number;
  free_share: number | null;
  levels: { source: string; resolved: number; unresolved: number }[];
  spend: { provider: string; calls: number; cost_paise: number }[];
  queue_open: number;
  queue_resolved: number;
  queue_rejected: number;
};

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) throw new Error(`${res.status}`);
  return (await res.json()) as T;
}

function ClickToPlace({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({
    click: (e) => onPick(e.latlng.lat, e.latlng.lng),
  });
  return null;
}

export function Geocoding() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<number | null>(null);
  const [point, setPoint] = useState<[number, number] | null>(null);
  const [note, setNote] = useState("");

  const funnel = useQuery({
    queryKey: ["geocoding-funnel"],
    queryFn: () => getJson<Funnel>("/api/internal/geocoding/funnel"),
    refetchInterval: 60_000,
  });

  const queue = useQuery({
    queryKey: ["geocoding-queue"],
    queryFn: () =>
      getJson<{ open_count: number; items: QueueItem[] }>("/api/internal/geocoding/queue"),
  });

  const job = queue.data?.items.find((i) => i.id === selected) ?? null;

  // Moving to a different job must not carry the last one's point across —
  // that is exactly how a click lands on the wrong address.
  useEffect(() => {
    setPoint(null);
    setNote("");
  }, [selected]);

  const act = useMutation({
    mutationFn: async (what: "resolve" | "reject") => {
      if (!job) return;
      const body =
        what === "resolve"
          ? { lat: point?.[0], lng: point?.[1], note: note || null }
          : { note: note || null };
      const res = await fetch(`/api/internal/geocoding/queue/${job.id}/${what}`, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
    },
    onSuccess: () => {
      setSelected(null);
      void qc.invalidateQueries({ queryKey: ["geocoding-queue"] });
      void qc.invalidateQueries({ queryKey: ["geocoding-funnel"] });
    },
  });

  const f = funnel.data;
  const freePct = f?.free_share == null ? null : Math.round(f.free_share * 1000) / 10;
  const spend = f?.spend.reduce((sum, s) => sum + s.cost_paise, 0) ?? 0;

  return (
    <>
      <PanelHeader
        title="Geocoding"
        note="Address in, map pin out. This shows how many addresses each level of the cascade resolved, what the paid levels cost, and the queue of addresses the cascade refused to guess at — a miss, or two geocoders more than 2 km apart."
      />
      <Glossary
        terms={["Geocoding", "Cascade", "Nominatim", "Confidence", "Manual queue", "Cap", "Paise"]}
      />

      {/* --- the funnel ------------------------------------------------- */}
      <section className="mb-6 flex max-w-4xl flex-wrap gap-x-8 gap-y-2 border-t border-rule pt-2">
        <Figure label="Addresses cached" value={f ? String(f.cached_addresses) : "…"} />
        <Figure label="Resolved" value={f ? String(f.resolved) : "…"} />
        <Figure
          label="Without a paid call"
          value={freePct == null ? "—" : `${freePct}%`}
          warn={freePct != null && freePct < 90}
          title="PLAN Part 1 exit criterion: at least 90%."
        />
        <Figure
          label="Maps spend this month"
          value={`₹${(spend / 100).toFixed(2)}`}
          title={f?.spend.map((s) => `${s.provider}: ${s.calls} calls`).join(" · ")}
        />
        <Figure label="Queue open" value={f ? String(f.queue_open) : "…"} warn={!!f?.queue_open} />
        <Figure label="Placed by hand" value={f ? String(f.queue_resolved) : "…"} />
        <Figure label="Rejected" value={f ? String(f.queue_rejected) : "…"} />
      </section>

      {f && f.levels.length > 0 && (
        <table className="mb-8 max-w-lg border-t border-rule text-left">
          <thead>
            <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
              <th className="py-1 font-medium">Level</th>
              <th className="py-1 text-right font-medium">Resolved</th>
              <th className="py-1 text-right font-medium">Still unresolved</th>
            </tr>
          </thead>
          <tbody>
            {f.levels.map((l) => (
              <tr key={l.source} className="border-t border-rule">
                <td className="py-1 font-data text-[13px]">{l.source}</td>
                <td className="py-1 text-right font-data text-[13px] tabular-nums">{l.resolved}</td>
                <td className="py-1 text-right font-data text-[13px] text-ink-muted tabular-nums">
                  {l.unresolved}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* --- the queue --------------------------------------------------- */}
      <h3 className="mb-2 font-ui text-[11px] tracking-[0.08em] text-ink-faint uppercase">
        Manual queue — busiest first
      </h3>

      {queue.isPending ? (
        <p className="font-data text-[13px] text-ink-faint">…</p>
      ) : queue.isError ? (
        <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          Could not reach the queue endpoint.
        </p>
      ) : queue.data && queue.data.items.length === 0 ? (
        <p className="max-w-prose font-data text-[13px] text-ink-muted">
          Nothing queued. Every address the cascade has seen either resolved or was rejected by a
          human.
        </p>
      ) : (
        <div className="grid max-w-5xl gap-6 lg:grid-cols-2">
          <ul className="max-h-[26rem] overflow-y-auto border-t border-rule">
            {queue.data?.items.map((item) => (
              <li key={item.id} className="border-b border-rule">
                <button
                  type="button"
                  onClick={() => setSelected(item.id)}
                  className={`w-full px-2 py-1.5 text-left ${
                    item.id === selected ? "bg-warn-ground" : ""
                  }`}
                >
                  <span className="font-data text-[13px]">{item.raw_input}</span>
                  <span className="ml-2 font-data text-[11px] text-ink-faint">
                    ×{item.hits}
                    {item.pincode ? ` · PIN ${item.pincode}` : ""}
                  </span>
                  {item.reason && (
                    <span className="mt-0.5 block font-data text-[11px] text-ink-muted">
                      {item.reason}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>

          <div>
            {job === null ? (
              <p className="font-data text-[13px] text-ink-faint">
                Pick an address to place it on the map.
              </p>
            ) : (
              <>
                <p className="mb-2 font-data text-[13px]">{job.raw_input}</p>
                <div className="h-72 border border-rule">
                  <MapContainer
                    center={point ?? DEFAULT_CENTRE}
                    zoom={point ? 15 : 8}
                    className="h-full w-full"
                  >
                    <TileLayer url={TILE_URL} attribution="© OpenStreetMap contributors" />
                    <ClickToPlace onPick={(lat, lng) => setPoint([lat, lng])} />
                    {point && <Marker position={point} icon={PIN} />}
                  </MapContainer>
                </div>

                <p className="mt-1 font-data text-[11px] text-ink-faint tabular-nums">
                  {point ? `${point[0].toFixed(5)}, ${point[1].toFixed(5)}` : "click the map"}
                </p>

                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="which building, which entrance, or why not"
                  className="mt-2 w-full border border-rule px-2 py-1 font-data text-[13px]"
                />

                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    disabled={!point || act.isPending}
                    onClick={() => act.mutate("resolve")}
                    className="border border-rule px-3 py-1 font-ui text-[12px] disabled:opacity-40"
                  >
                    Save point
                  </button>
                  <button
                    type="button"
                    disabled={act.isPending}
                    onClick={() => act.mutate("reject")}
                    className="border border-rule px-3 py-1 font-ui text-[12px] text-ink-muted"
                    title="A human looked and could not place it. Nothing is written to the cache."
                  >
                    Cannot place
                  </button>
                </div>

                {act.isError && (
                  <p className="mt-2 bg-warn-ground px-2 py-1 font-data text-[12px] text-warn">
                    Could not save. The point must be inside India.
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function Figure({
  label,
  value,
  warn,
  title,
}: {
  label: string;
  value: string;
  warn?: boolean;
  title?: string;
}) {
  return (
    <div title={title}>
      <div className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">{label}</div>
      <div
        className={`font-data text-[15px] tabular-nums ${warn ? "bg-warn-ground px-1 text-warn" : ""}`}
      >
        {value}
      </div>
    </div>
  );
}
