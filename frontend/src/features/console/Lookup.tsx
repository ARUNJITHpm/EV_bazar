import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";

import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/**
 * PART C — "show me the working".
 *
 * The one screen that explains the system to a human: put in a coordinate, get
 * the district, and see every question that was asked, which table answered it,
 * and which answer decided the outcome.
 *
 * It is also the panel to open when somebody disputes a district. The answer on
 * its own is unarguable-with; the trail underneath it is not.
 */

type Step = {
  n: number;
  question: string;
  looked_in: string;
  using: string;
  answer: string;
  decisive: boolean;
};

type FieldSource = { field: string; value: string; source: string; note: string };

type Layer = {
  name: string;
  feature_count: number;
  licence: string;
  source_url: string;
  downloaded_at: string;
};

type PointOut = {
  lat: number;
  lng: number;
  supplied_pincode: string | null;
  resolved: boolean;
  district: string | null;
  lgd_district_code: number | null;
  state_name: string | null;
  lgd_state_code: number | null;
  distance_m: number;
  method: string;
  confidence: string;
  boundary_ambiguous: boolean;
  neighbour: {
    name: string;
    state_name: string;
    lgd_district_code: number;
    distance_m: number;
  } | null;
  pincode_at_point: string[];
  pin_conflict: boolean;
  overridden_district: string | null;
  reasons: string[];
  steps: Step[];
  fields: FieldSource[];
  layers: Layer[];
};

type Query = { lat: string; lng: string; pincode: string };

/**
 * Real places with instructive answers. Each one exercises a different branch,
 * so clicking through them is the fastest way to understand what the resolver
 * actually does — including the two cases where it refuses.
 */
/** Kochi. Also what the panel opens on, so the screen is never blank. */
const DEFAULT_QUERY: Query = { lat: "9.9312", lng: "76.2673", pincode: "" };

const EXAMPLES: { label: string; note: string; q: Query }[] = [
  {
    label: "Kochi",
    note: "the ordinary case — inside exactly one district",
    q: DEFAULT_QUERY,
  },
  {
    label: "Kochi + wrong PIN",
    note: "PIN says Thrissur, coordinates say Ernakulam — the PIN wins",
    q: { lat: "9.9312", lng: "76.2673", pincode: "680001" },
  },
  {
    label: "Walayar (KL/TN line)",
    note: "a state border on NH-544 — two tariff regimes within metres",
    q: { lat: "10.828", lng: "76.846", pincode: "" },
  },
  {
    label: "Bengaluru",
    note: "another state, to see the LGD codes change",
    q: { lat: "12.9716", lng: "77.5946", pincode: "" },
  },
  {
    label: "Arabian Sea",
    note: "nothing within 5 km — refused rather than guessed",
    q: { lat: "12.0", lng: "70.0", pincode: "" },
  },
];

const EMPTY: Query = { lat: "", lng: "", pincode: "" };

export function Lookup() {
  const [form, setForm] = useState<Query>(DEFAULT_QUERY);
  const [submitted, setSubmitted] = useState<Query>(DEFAULT_QUERY);

  const point = useQuery<PointOut>({
    queryKey: ["lookup-point", submitted],
    enabled: submitted.lat !== "" && submitted.lng !== "",
    queryFn: async () => {
      const params = new URLSearchParams({ lat: submitted.lat, lng: submitted.lng });
      if (submitted.pincode) params.set("pincode", submitted.pincode);
      const res = await fetch(`/api/internal/lookup/point?${params}`, {
        credentials: "include",
      });
      if (!res.ok) {
        const body: unknown = await res.json().catch(() => null);
        throw new Error(describe(res.status, body));
      }
      return (await res.json()) as PointOut;
    },
    retry: false,
  });

  function run(q: Query) {
    setForm(q);
    setSubmitted(q);
  }

  return (
    <>
      <PanelHeader
        title="Lookup"
        note="A coordinate in, a district out — and every step in between. Which question was asked, which table answered it, and which answer was decisive. This is the panel to open when somebody disputes a district: the answer alone is unarguable-with, the trail underneath it is not."
      />
      <Glossary
        terms={[
          "Point-in-polygon",
          "Polygon",
          "LGD",
          "PIN polygon",
          "Confidence",
          "PostGIS",
          "Geocoding",
        ]}
      />

      <section className="max-w-4xl">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(form);
          }}
        >
          <Field
            label="Latitude"
            value={form.lat}
            onChange={(lat) => setForm({ ...form, lat })}
            placeholder="9.9312"
          />
          <Field
            label="Longitude"
            value={form.lng}
            onChange={(lng) => setForm({ ...form, lng })}
            placeholder="76.2673"
          />
          <Field
            label="PIN (optional)"
            value={form.pincode}
            onChange={(pincode) => setForm({ ...form, pincode })}
            placeholder="682035"
            width="w-28"
          />
          <button
            type="submit"
            className="border border-rule-strong px-3 py-1.5 font-ui text-[13px] hover:bg-ground-sunk"
          >
            Resolve
          </button>
          <button
            type="button"
            onClick={() => run(EMPTY)}
            className="font-ui text-[12px] text-ink-muted underline underline-offset-2 hover:text-ink"
          >
            Clear
          </button>
        </form>

        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              type="button"
              title={ex.note}
              onClick={() => run(ex.q)}
              className="border border-rule px-2 py-1 font-data text-[11px] text-ink-muted hover:bg-ground-sunk hover:text-ink"
            >
              {ex.label}
            </button>
          ))}
        </div>
        <p className="mt-1.5 font-data text-[11px] text-ink-faint">
          Hover an example to see which branch it exercises. Two of them are deliberate refusals.
        </p>
      </section>

      {point.isPending && submitted.lat !== "" && (
        <p className="mt-6 font-data text-[13px] text-ink-faint">…</p>
      )}

      {point.isError && (
        <p className="mt-6 max-w-3xl bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          {point.error.message}
        </p>
      )}

      {point.data && <Result data={point.data} />}
    </>
  );
}

function Result({ data }: { data: PointOut }) {
  return (
    <>
      {/* --- the answer ---------------------------------------------------- */}
      <section className="mt-8 max-w-4xl">
        <SectionTitle>Answer</SectionTitle>
        <div className="border border-rule p-4">
          {data.resolved ? (
            <>
              <p className="font-ui text-[24px] leading-tight">{data.district}</p>
              <p className="font-data text-[13px] text-ink-muted">
                {data.state_name} · district code {data.lgd_district_code} · state code{" "}
                {data.lgd_state_code}
              </p>
            </>
          ) : (
            <p className="font-ui text-[24px] leading-tight text-warn">no district</p>
          )}

          <dl className="mt-4 grid grid-cols-2 gap-x-8 sm:grid-cols-4">
            <Stat label="Method" value={data.method} />
            <Stat label="Confidence" value={data.confidence} warn={data.confidence !== "high"} />
            <Stat
              label="Inside the polygon"
              value={data.distance_m === 0 ? "yes" : `no — ${data.distance_m.toFixed(0)} m outside`}
              warn={data.distance_m > 0}
            />
            <Stat
              label="Near a border"
              value={data.boundary_ambiguous ? "yes" : "no"}
              warn={data.boundary_ambiguous}
            />
          </dl>

          {data.overridden_district && (
            <p className="mt-3 bg-warn-ground px-2 py-1 font-data text-[12px] text-warn">
              The coordinates landed in {data.overridden_district}, but the PIN the customer gave
              belongs to {data.district} — so the PIN won. A PIN comes from the customer; the
              coordinates come from a geocoder.
            </p>
          )}

          {data.neighbour && (
            <p className="mt-3 bg-warn-ground px-2 py-1 font-data text-[12px] text-warn">
              {data.neighbour.name} ({data.neighbour.state_name}) is only{" "}
              {data.neighbour.distance_m.toFixed(0)} m away — if that is a different state, it is a
              different electricity tariff entirely.
            </p>
          )}
        </div>

        {data.reasons.length > 0 && (
          <ul className="mt-3 space-y-1">
            {data.reasons.map((r) => (
              <li key={r} className="max-w-prose font-data text-[12px] text-ink-muted">
                · {r}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* --- the working --------------------------------------------------- */}
      <section className="mt-8 max-w-4xl">
        <SectionTitle>How it got there</SectionTitle>
        <table className="w-full border-t border-rule text-left">
          <thead>
            <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
              <th className="w-6 py-1 font-medium">#</th>
              <th className="py-1 font-medium">Question</th>
              <th className="py-1 font-medium">Looked in</th>
              <th className="py-1 font-medium">Answer</th>
            </tr>
          </thead>
          <tbody>
            {data.steps.map((s) => (
              <tr
                key={s.n}
                className={cn("border-t border-rule align-top", s.decisive && "bg-ground-sunk")}
              >
                <td className="py-2 font-data text-[12px] text-ink-faint">{s.n}</td>
                <td className="py-2 pr-4 text-[13px]">
                  {s.question}
                  {s.decisive && (
                    <span className="ml-2 font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                      decisive
                    </span>
                  )}
                </td>
                <td className="py-2 pr-4 font-data text-[12px] text-ink-muted">
                  {s.looked_in}
                  <span className="block text-[11px] text-ink-faint">{s.using}</span>
                </td>
                <td className="py-2 font-data text-[12px]">{s.answer}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* --- provenance ---------------------------------------------------- */}
      <section className="mt-8 max-w-4xl">
        <SectionTitle>Where each value came from</SectionTitle>
        <table className="w-full border-t border-rule text-left">
          <thead>
            <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
              <th className="py-1 font-medium">Field</th>
              <th className="py-1 font-medium">Value</th>
              <th className="py-1 font-medium">Table · column</th>
              <th className="py-1 font-medium">Why</th>
            </tr>
          </thead>
          <tbody>
            {data.fields.map((f) => (
              <tr key={f.field} className="border-t border-rule align-top">
                <td className="py-2 pr-4 font-data text-[12px]">{f.field}</td>
                <td className="py-2 pr-4 font-data text-[12px]">{f.value}</td>
                <td className="py-2 pr-4 font-data text-[12px] text-ink-muted">{f.source}</td>
                <td className="py-2 text-[12px] text-ink-muted">{f.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* --- the map data itself ------------------------------------------- */}
      <section className="mt-8 max-w-4xl">
        <SectionTitle>The map layers underneath</SectionTitle>
        <table className="w-full border-t border-rule text-left">
          <thead>
            <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
              <th className="py-1 font-medium">Layer</th>
              <th className="py-1 text-right font-medium">Shapes</th>
              <th className="py-1 font-medium">Licence</th>
              <th className="py-1 font-medium">Downloaded</th>
            </tr>
          </thead>
          <tbody>
            {data.layers.map((l) => (
              <tr key={l.name} className="border-t border-rule align-top">
                <td className="py-1.5 font-data text-[12px]">{l.name}</td>
                <td className="py-1.5 text-right font-data text-[12px] tabular-nums">
                  {l.feature_count.toLocaleString()}
                </td>
                <td className="py-1.5 font-data text-[12px] text-ink-muted">{l.licence}</td>
                <td className="py-1.5 font-data text-[12px] text-ink-muted tabular-nums">
                  {l.downloaded_at.slice(0, 10)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
          Every layer is recorded with its source URL and checksum so a report written today can
          still say which boundaries produced it — districts get split, and “the current ones” is
          not an answer a year later.
        </p>
      </section>

      <details className="mt-8 max-w-4xl">
        <summary className="cursor-pointer font-ui text-[12px] text-ink-muted">
          Raw response
        </summary>
        <pre className="mt-2 overflow-x-auto bg-ground-sunk p-3 font-data text-[11px]">
          {JSON.stringify(data, null, 2)}
        </pre>
      </details>
    </>
  );
}

function describe(status: number, body: unknown): string {
  if (status === 422) {
    return "Out of range. Latitude must be 6–37.5 and longitude 68–97.5 — India's bounding box. A swapped pair is the commonest way this goes wrong.";
  }
  const detail =
    typeof body === "object" && body !== null && "detail" in body
      ? String((body as { detail: unknown }).detail)
      : "";
  return `Lookup failed (${status}). ${detail}`.trim();
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  width = "w-32",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  width?: string;
}) {
  return (
    <label className="block">
      <span className="block font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
        {label}
      </span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn(
          "mt-1 border border-rule bg-ground px-2 py-1 font-data text-[13px]",
          "focus:border-rule-strong focus:outline-none",
          width,
        )}
      />
    </label>
  );
}

function Stat({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div>
      <dt className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">{label}</dt>
      <dd
        className={cn("font-data text-[13px]", warn ? "bg-warn-ground px-1 text-warn" : "text-ink")}
      >
        {value}
      </dd>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-2 font-ui text-[10px] font-bold tracking-[0.08em] text-ink-faint uppercase">
      {children}
    </h2>
  );
}
