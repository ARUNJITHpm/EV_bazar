import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { PanelHeader } from "./ConsoleLayout";

/**
 * The charging network: every station, its chargers and connectors, with the
 * source listings behind it. Read-only. Filter by state, district, operator or
 * text; the filters live in the URL so a view can be shared or reloaded.
 */

type Counts = {
  stations: number;
  chargers: number;
  connectors: number;
  operators: number;
  unattributed: number;
  unplaced: number;
  connectors_without_power: number;
};
type Facets = {
  counts: Counts;
  states: { lgd_state_code: number; state: string; stations: number }[];
  districts: {
    lgd_district_code: number;
    lgd_state_code: number;
    district: string;
    stations: number;
  }[];
  operators: { id: number; name: string; stations: number }[];
};
type Row = {
  id: number;
  name: string | null;
  operator: string | null;
  operator_confirmed: boolean;
  town: string | null;
  district: string | null;
  state: string | null;
  lat: number;
  lng: number;
  chargers: number;
  connectors: number;
  max_power_kw: number | null;
  dc_fast: boolean;
  listings: number;
  updated_at: string;
};
type Page = { total: number; page: number; page_size: number; pages: number; stations: Row[] };
type Detail = {
  station: Row;
  address: string | null;
  postcode: string | null;
  access: string | null;
  is_operational: boolean | null;
  created_at: string;
  chargers: {
    id: number;
    label: string | null;
    current_type: string | null;
    rated_power_kw: number | null;
    inferred: boolean;
    status: string;
    connectors: {
      id: number;
      standard: string | null;
      format: string | null;
      max_power_kw: number | null;
    }[];
  }[];
  listings: {
    source: string;
    source_key: string;
    source_name: string | null;
    source_operator: string | null;
    first_seen_at: string;
    last_seen_at: string;
  }[];
};

const SORTS = [
  ["name", "Name"],
  ["connectors", "Most connectors"],
  ["power", "Highest power"],
  ["updated", "Recently updated"],
] as const;
const SIZES = [25, 50, 100, 200];

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) throw new Error(`${url} returned ${res.status}`);
  return (await res.json()) as T;
}

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

const kw = (v: number | null) => (v === null ? "—" : `${v.toLocaleString("en-IN")} kW`);

export function Network() {
  const [params, setParams] = useSearchParams();
  const state = params.get("state") ?? "";
  const district = params.get("district") ?? "";
  const operator = params.get("operator") ?? "";
  const sort = params.get("sort") ?? "name";
  const page = Math.max(1, Number(params.get("page") ?? 1) || 1);
  const size = SIZES.includes(Number(params.get("size"))) ? Number(params.get("size")) : 50;

  // The search box is typed into freely and applied after a pause.
  const [text, setText] = useState(params.get("q") ?? "");
  const q = params.get("q") ?? "";
  useEffect(() => {
    if (text === q) return;
    const t = setTimeout(() => set({ q: text }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  /** Change filters; anything but the page itself sends you back to page 1. */
  function set(next: Record<string, string>) {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    if (!("page" in next)) p.delete("page");
    setParams(p, { replace: true });
  }

  const facets = useQuery({
    queryKey: ["network-facets"],
    queryFn: () => get<Facets>("/api/internal/network/facets"),
  });

  const query = new URLSearchParams({ sort, page: String(page), page_size: String(size) });
  if (state) query.set("state", state);
  if (district) query.set("district", district);
  if (operator) query.set("operator", operator);
  if (q) query.set("q", q);
  const list = useQuery({
    queryKey: ["network-stations", query.toString()],
    queryFn: () => get<Page>(`/api/internal/network/stations?${query}`),
    placeholderData: keepPreviousData,
  });

  const [open, setOpen] = useState<number | null>(null);
  const detail = useQuery({
    queryKey: ["network-station", open],
    queryFn: () => get<Detail>(`/api/internal/network/stations/${open}`),
    enabled: open !== null,
  });

  const f = facets.data;
  const districts = (f?.districts ?? []).filter(
    (d) => !state || d.lgd_state_code === Number(state),
  );
  const filtered = Boolean(state || district || operator || q);

  return (
    <>
      <PanelHeader
        title="Network"
        note="Every charging station we know about, with its chargers and connectors and the sources that listed it. Read-only. Operators marked 'raw' are text a source gave us that no canonical CPO owns yet."
      />

      {f && (
        <section className="mb-6 flex max-w-4xl flex-wrap gap-x-8 gap-y-2 border-t border-rule pt-2">
          <Figure label="Stations" value={f.counts.stations} />
          <Figure label="Chargers" value={f.counts.chargers} />
          <Figure label="Connectors" value={f.counts.connectors} />
          <Figure label="Operators" value={f.counts.operators} />
          <Figure label="No operator" value={f.counts.unattributed} warn />
          <Figure label="No district" value={f.counts.unplaced} warn />
          <Figure label="Connectors without power" value={f.counts.connectors_without_power} warn />
        </section>
      )}

      <section className="mb-4 flex max-w-5xl flex-wrap items-end gap-3">
        <Field label="State">
          <select
            className={INPUT}
            value={state}
            onChange={(e) => set({ state: e.target.value, district: "" })}
          >
            <option value="">All states</option>
            {f?.states.map((s) => (
              <option key={s.lgd_state_code} value={s.lgd_state_code}>
                {s.state} ({s.stations.toLocaleString("en-IN")})
              </option>
            ))}
          </select>
        </Field>
        <Field label="District">
          <select
            className={INPUT}
            value={district}
            onChange={(e) => set({ district: e.target.value })}
          >
            <option value="">All districts</option>
            {districts.map((d) => (
              <option key={d.lgd_district_code} value={d.lgd_district_code}>
                {d.district} ({d.stations.toLocaleString("en-IN")})
              </option>
            ))}
          </select>
        </Field>
        <Field label="Operator">
          <select
            className={INPUT}
            value={operator}
            onChange={(e) => set({ operator: e.target.value })}
          >
            <option value="">All operators</option>
            <option value="0">No operator yet</option>
            {f?.operators.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name} ({o.stations.toLocaleString("en-IN")})
              </option>
            ))}
          </select>
        </Field>
        <Field label="Search">
          <input
            className={INPUT}
            value={text}
            placeholder="name, town, address"
            onChange={(e) => setText(e.target.value)}
          />
        </Field>
        <Field label="Sort">
          <select className={INPUT} value={sort} onChange={(e) => set({ sort: e.target.value })}>
            {SORTS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Field>
        {filtered && (
          <button
            type="button"
            className="pb-1 font-ui text-[11px] text-ink-muted underline"
            onClick={() => {
              setText("");
              setParams(new URLSearchParams(), { replace: true });
            }}
          >
            Clear filters
          </button>
        )}
      </section>

      {list.isError && (
        <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          Could not read stations.
        </p>
      )}

      {list.data && (
        <section className="max-w-5xl">
          <table className="w-full border-t border-rule text-left">
            <thead>
              <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                <th className="py-1 font-medium">Station</th>
                <th className="py-1 font-medium">Operator</th>
                <th className="py-1 font-medium">District</th>
                <th className="py-1 pl-4 text-right font-medium">Chargers</th>
                <th className="py-1 pl-4 text-right font-medium">Connectors</th>
                <th className="py-1 pl-4 text-right font-medium">Top power</th>
                <th className="py-1 pl-4 text-right font-medium">Sources</th>
              </tr>
            </thead>
            <tbody className={list.isFetching ? "opacity-60" : undefined}>
              {list.data.stations.map((s) => (
                <StationRow
                  key={s.id}
                  row={s}
                  open={open === s.id}
                  detail={open === s.id ? detail.data : undefined}
                  onToggle={() => setOpen(open === s.id ? null : s.id)}
                />
              ))}
              {list.data.stations.length === 0 && (
                <tr className="border-t border-rule">
                  <td colSpan={7} className="py-3 font-data text-[13px] text-ink-faint">
                    No stations match.
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          <nav className="mt-3 flex flex-wrap items-center gap-3 font-data text-[12px]">
            <span className="text-ink-muted tabular-nums">
              {list.data.total === 0
                ? "0 stations"
                : `${((list.data.page - 1) * list.data.page_size + 1).toLocaleString("en-IN")}–${Math.min(
                    list.data.page * list.data.page_size,
                    list.data.total,
                  ).toLocaleString("en-IN")} of ${list.data.total.toLocaleString("en-IN")}`}
            </span>
            <button
              type="button"
              className={BTN}
              disabled={page <= 1}
              onClick={() => set({ page: String(page - 1) })}
            >
              Previous
            </button>
            <span className="tabular-nums">
              Page {list.data.page} of {list.data.pages.toLocaleString("en-IN")}
            </span>
            <button
              type="button"
              className={BTN}
              disabled={page >= list.data.pages}
              onClick={() => set({ page: String(page + 1) })}
            >
              Next
            </button>
            <label className="ml-auto flex items-center gap-2 text-ink-muted">
              Rows
              <select
                className={INPUT}
                value={size}
                onChange={(e) => set({ size: e.target.value })}
              >
                {SIZES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </nav>
        </section>
      )}
    </>
  );
}

const INPUT = "border border-rule bg-transparent px-2 py-1 font-data text-[12px] text-ink";
const BTN =
  "border border-rule px-2 py-1 font-ui text-[11px] enabled:hover:bg-ink/5 disabled:opacity-40";

function StationRow({
  row: s,
  open,
  detail,
  onToggle,
}: {
  row: Row;
  open: boolean;
  detail: Detail | undefined;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className="cursor-pointer border-t border-rule align-top hover:bg-ink/5"
        onClick={onToggle}
        aria-expanded={open}
      >
        <td className="py-1.5 pr-2 text-[13px]">
          {s.name?.trim() || "(unnamed)"}
          {s.town && <div className="font-data text-[11px] text-ink-faint">{s.town}</div>}
        </td>
        <td className="py-1.5 pr-2 font-data text-[13px]">
          {s.operator ?? <span className="text-ink-faint">—</span>}
          {s.operator && !s.operator_confirmed && (
            <span className="ml-1 font-ui text-[10px] text-warn uppercase">raw</span>
          )}
        </td>
        <td className="py-1.5 pr-2 font-data text-[13px]">
          {s.district ?? <span className="text-ink-faint">—</span>}
          {s.state && <div className="text-[11px] text-ink-faint">{s.state}</div>}
        </td>
        <td className="py-1.5 pl-4 text-right font-data text-[13px] tabular-nums">{s.chargers}</td>
        <td className="py-1.5 pl-4 text-right font-data text-[13px] tabular-nums">
          {s.connectors}
        </td>
        <td className="py-1.5 pl-4 text-right font-data text-[13px] whitespace-nowrap tabular-nums">
          {kw(s.max_power_kw)}
          {s.dc_fast && <span className="ml-1 font-ui text-[10px] uppercase">DC</span>}
        </td>
        <td className="py-1.5 pl-4 text-right font-data text-[13px] tabular-nums">{s.listings}</td>
      </tr>
      {open && (
        <tr className="bg-ink/5">
          <td colSpan={7} className="px-3 py-3">
            {!detail ? (
              <span className="font-data text-[12px] text-ink-faint">…</span>
            ) : (
              <StationDetail d={detail} />
            )}
          </td>
        </tr>
      )}
    </>
  );
}

function StationDetail({ d }: { d: Detail }) {
  return (
    <div className="grid gap-4 font-data text-[12px] md:grid-cols-2">
      <div>
        <h3 className={H}>Location</h3>
        <p>{d.address ?? "No address"}</p>
        <p className="text-ink-muted">
          {d.station.lat.toFixed(5)}, {d.station.lng.toFixed(5)}
          {d.postcode ? ` · ${d.postcode}` : ""}
        </p>
        <p className="text-ink-muted">
          {d.access ?? "access unknown"} ·{" "}
          {d.is_operational === null ? "status unknown" : d.is_operational ? "operational" : "down"}
        </p>
        <p className="text-ink-faint">
          Added {fmtDate(d.created_at)} · updated {fmtDate(d.station.updated_at)}
        </p>
        <h3 className={`${H} mt-3`}>Listed by</h3>
        {d.listings.length === 0 && <p className="text-ink-faint">No source listings.</p>}
        {d.listings.map((l) => (
          <p key={`${l.source}/${l.source_key}`}>
            {l.source} <span className="text-ink-faint">#{l.source_key}</span>
            {l.source_name && l.source_name !== d.station.name ? ` · “${l.source_name}”` : ""}
            <span className="block text-ink-faint">
              first seen {fmtDate(l.first_seen_at)} · last {fmtDate(l.last_seen_at)}
            </span>
          </p>
        ))}
      </div>
      <div>
        <h3 className={H}>Chargers and connectors</h3>
        {d.chargers.map((c, i) => (
          <div key={c.id} className="mb-2">
            <div>
              {c.label ?? `Charger ${i + 1}`}
              {c.current_type && ` · ${c.current_type}`}
              {c.rated_power_kw !== null && ` · ${kw(c.rated_power_kw)}`}
              {c.inferred && <span className="ml-1 text-[10px] text-warn uppercase">inferred</span>}
              {c.status !== "active" && (
                <span className="ml-1 text-[10px] uppercase">{c.status}</span>
              )}
            </div>
            {c.connectors.map((k) => (
              <div key={k.id} className="pl-4 text-ink-muted">
                {k.standard ?? "Unknown standard"} · {kw(k.max_power_kw)}
                {k.format ? ` · ${k.format}` : ""}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

const H = "mb-1 font-ui text-[10px] font-bold tracking-[0.08em] text-ink-faint uppercase";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
        {label}
      </span>
      {children}
    </label>
  );
}

function Figure({ label, value, warn = false }: { label: string; value: number; warn?: boolean }) {
  return (
    <div>
      <div className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">{label}</div>
      <div
        className={
          warn && value > 0
            ? "bg-warn-ground px-1 font-data text-[15px] text-warn"
            : "font-data text-[15px]"
        }
      >
        {value.toLocaleString("en-IN")}
      </div>
    </div>
  );
}
