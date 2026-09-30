import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../../api/client";
import { formatKw, formatKwhBound, kw, kwh } from "../../lib/units";
import { Answer, Answers, Screen } from "../public/flow/Question";
import {
  billMonths,
  blankDraft,
  clearDraft,
  loadDraft,
  monthFromIndex,
  monthIndex,
  monthLabel,
  saveDraft,
  toReadings,
  type MeterType,
  type OwnerDraft,
  type OwnerStation,
} from "./state";

/**
 * Station-owner upload: find your station, pick your connectors, say when it
 * went live, whether the meter is its own, and type up to six months of bills.
 *
 * Nothing on this side works anything out. The peer comparison and the
 * next-month band come back from POST /owner/submissions (app/domain/owner),
 * so the numbers an owner is shown are the ones that were stored. Energy is
 * kWh only - no rupee figure exists on this surface.
 *
 * Same rules as the assessment flow: one question per screen, no dropdowns,
 * 56px tap targets, every step a real URL.
 */

type StepId = "station" | "connectors" | "installed" | "meter" | "energy" | "consent" | "result";
const ORDER: StepId[] = [
  "station",
  "connectors",
  "installed",
  "meter",
  "energy",
  "consent",
  "result",
];
const isStep = (v: string): v is StepId => (ORDER as string[]).includes(v);

/** The latest month an owner can hold a full bill for: last calendar month. */
function lastFullMonth(): string {
  const now = new Date();
  return monthFromIndex(now.getFullYear() * 12 + now.getMonth() - 1);
}

const inputCls =
  "min-h-[56px] w-full border border-cw-line bg-cw-surface px-5 text-[18px] text-cw-text placeholder:text-cw-muted focus:border-cw-slate focus:outline-none";

const primaryCls =
  "inline-flex min-h-[58px] items-center justify-center bg-cw-accent px-7 text-[17px] font-semibold text-cw-ground transition-[filter] duration-200 hover:brightness-107 disabled:cursor-not-allowed disabled:opacity-40";

const choiceCls = (on: boolean) =>
  `flex min-h-[56px] flex-col gap-1 border p-5 text-left transition-colors duration-200 ${
    on ? "border-cw-accent bg-cw-surface-2" : "border-cw-line bg-cw-surface hover:border-cw-slate"
  }`;

function StationStep({
  draft,
  onPick,
  onNext,
}: {
  draft: OwnerDraft;
  onPick: (s: OwnerStation) => void;
  onNext: () => void;
}) {
  const [q, setQ] = useState("");
  const [list, setList] = useState<OwnerStation[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    const t = setTimeout(async () => {
      const { data } = await api.GET("/api/internal/owner/stations", {
        params: { query: { q, state: "Kerala", limit: 30 } },
      });
      if (!live) return;
      setFailed(!data);
      setList(data?.stations ?? []);
    }, 250);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [q]);

  return (
    <Screen question="Which station is yours?">
      <input
        type="search"
        className={inputCls}
        placeholder="Try Kochi, ChargeMOD or KSEB"
        aria-label="Search stations"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div role="list" className="flex flex-col gap-3">
        {failed && (
          <p className="text-cw-muted">We could not load stations. Try again in a moment.</p>
        )}
        {list?.length === 0 && !failed && (
          <p className="text-cw-muted">No station matches “{q}”. Try the town or the company.</p>
        )}
        {list?.map((s) => (
          <button
            key={s.id}
            type="button"
            role="listitem"
            aria-pressed={draft.station?.id === s.id}
            onClick={() => onPick(s)}
            className={choiceCls(draft.station?.id === s.id)}
          >
            <span className="text-[19px] font-medium">{s.name ?? "Unnamed station"}</span>
            <span className="text-cw-muted">
              {[s.operator, s.town].filter(Boolean).join(" · ")} ·{" "}
              <span className="font-cw-mono tabular-nums">{s.connectors.length}</span> connector
              {s.connectors.length === 1 ? "" : "s"}
            </span>
          </button>
        ))}
      </div>
      <div className="flex justify-end">
        <button type="button" className={primaryCls} disabled={!draft.station} onClick={onNext}>
          This is my station
        </button>
      </div>
    </Screen>
  );
}

function ConnectorsStep({
  draft,
  set,
  onNext,
}: {
  draft: OwnerDraft;
  set: (p: Partial<OwnerDraft>) => void;
  onNext: () => void;
}) {
  const conns = draft.station?.connectors ?? [];
  const toggle = (id: number) =>
    set({
      connectors: draft.connectors.includes(id)
        ? draft.connectors.filter((x) => x !== id)
        : [...draft.connectors, id].sort((a, b) => a - b),
    });
  return (
    <Screen question="Which connectors do you own?">
      <p className="max-w-[640px] text-cw-muted">
        Pick every connector billed on the electricity connection you will upload.
      </p>
      <Answers cols={3}>
        {conns.map((c, i) => (
          <button
            key={c.id}
            type="button"
            aria-pressed={draft.connectors.includes(c.id)}
            onClick={() => toggle(c.id)}
            className={choiceCls(draft.connectors.includes(c.id))}
          >
            <span className="font-cw-mono text-[22px] font-medium tabular-nums">
              {formatKw(kw(c.power_kw))}
            </span>
            <span className="text-cw-muted">
              {c.standard ? `${c.standard} · ` : ""}Connector {i + 1}
            </span>
          </button>
        ))}
      </Answers>
      <div className="flex justify-end">
        <button
          type="button"
          className={primaryCls}
          disabled={draft.connectors.length === 0}
          onClick={onNext}
        >
          Continue
        </button>
      </div>
    </Screen>
  );
}

function InstalledStep({
  draft,
  set,
  onNext,
}: {
  draft: OwnerDraft;
  set: (p: Partial<OwnerDraft>) => void;
  onNext: () => void;
}) {
  const latest = lastFullMonth();
  const value = draft.installMonth ?? monthFromIndex(monthIndex(latest) - 11);
  const step = (d: number) => {
    const next = monthIndex(value) + d;
    if (next <= monthIndex(latest)) set({ installMonth: monthFromIndex(next) });
  };
  const months = monthIndex(latest) - monthIndex(value) + 1;
  const stepper =
    "inline-flex min-h-[56px] min-w-[56px] items-center justify-center border border-cw-line bg-cw-surface text-[24px] transition-colors duration-200 hover:border-cw-slate";
  return (
    <Screen question="When did it start charging?">
      <p className="max-w-[640px] text-cw-muted">
        The month the station first went live. Usage grows as drivers find a station, so we compare
        you with stations of the same age.
      </p>
      <div className="flex items-center gap-4">
        <button
          type="button"
          className={stepper}
          aria-label="Earlier month"
          onClick={() => step(-1)}
        >
          −
        </button>
        <output className="min-w-[160px] text-center font-cw-mono text-[28px] font-medium">
          {monthLabel(value)}
        </output>
        <button type="button" className={stepper} aria-label="Later month" onClick={() => step(1)}>
          +
        </button>
      </div>
      <p className="text-cw-muted">
        <span className="font-cw-mono tabular-nums">{months}</span> months of operation by{" "}
        {monthLabel(latest)}
      </p>
      <div className="flex justify-end">
        <button
          type="button"
          className={primaryCls}
          onClick={() => {
            set({ installMonth: value });
            onNext();
          }}
        >
          Continue
        </button>
      </div>
    </Screen>
  );
}

function MeterStep({ onPick }: { onPick: (m: MeterType) => void }) {
  return (
    <Screen question="Does the charger have its own electricity meter?">
      <Answers cols={3}>
        <Answer
          title="Yes, its own meter"
          sub="The bill shows only charging."
          onClick={() => onPick("separate")}
        />
        <Answer
          title="No, it shares a meter"
          sub="With a shop, office or building."
          onClick={() => onPick("shared")}
        />
        <Answer
          title="Not sure"
          sub="We will treat the figures as possibly including other load."
          onClick={() => onPick("unsure")}
        />
      </Answers>
    </Screen>
  );
}

function EnergyStep({
  draft,
  set,
  onNext,
}: {
  draft: OwnerDraft;
  set: (p: Partial<OwnerDraft>) => void;
  onNext: () => void;
}) {
  const months = billMonths(lastFullMonth());
  const usable = toReadings(draft).length;
  return (
    <Screen question="How much energy did the charger use each month?">
      <p className="max-w-[640px] text-cw-muted">
        Read the kWh from your electricity bill. Leave a month empty if you do not have it. One
        month is enough to start; six gives a tighter range.
      </p>
      <div className="flex max-w-[560px] flex-col gap-3">
        {months.map((m) => {
          const off = !!draft.installMonth && monthIndex(m) < monthIndex(draft.installMonth);
          return (
            <div key={m} className={`flex items-center gap-4 ${off ? "opacity-40" : ""}`}>
              <label htmlFor={`kwh-${m}`} className="w-[120px] shrink-0">
                {monthLabel(m)}
                {off && <span className="block text-[13px] text-cw-muted">not live yet</span>}
              </label>
              <input
                id={`kwh-${m}`}
                inputMode="numeric"
                disabled={off}
                className={`${inputCls} font-cw-mono tabular-nums`}
                placeholder="kWh"
                value={draft.readings[m] ?? ""}
                onChange={(e) =>
                  set({
                    readings: { ...draft.readings, [m]: e.target.value.replace(/[^\d.,]/g, "") },
                  })
                }
              />
            </div>
          );
        })}
      </div>
      <div className="flex justify-end">
        <button type="button" className={primaryCls} disabled={usable === 0} onClick={onNext}>
          Continue
        </button>
      </div>
    </Screen>
  );
}

function ConsentStep({
  draft,
  set,
  onSubmit,
  busy,
  error,
}: {
  draft: OwnerDraft;
  set: (p: Partial<OwnerDraft>) => void;
  onSubmit: () => void;
  busy: boolean;
  error: string | null;
}) {
  const box = "mt-1 h-6 w-6 shrink-0 accent-cw-accent";
  return (
    <Screen question="How may we use your figures?">
      <label className="flex max-w-[680px] cursor-pointer gap-4 border border-cw-line bg-cw-surface p-6">
        <input
          type="checkbox"
          className={box}
          checked={draft.consentAggregate}
          onChange={(e) => set({ consentAggregate: e.target.checked })}
        />
        <span>
          <span className="block text-[19px] font-medium">Include me in anonymous averages</span>
          <span className="text-cw-muted">
            Required. Your figures help other owners see what stations like yours deliver. Your
            station is never named.
          </span>
        </span>
      </label>
      <label className="flex max-w-[680px] cursor-pointer gap-4 border border-cw-line bg-cw-surface p-6">
        <input
          type="checkbox"
          className={box}
          checked={draft.consentPublic}
          onChange={(e) => set({ consentPublic: e.target.checked })}
        />
        <span>
          <span className="block text-[19px] font-medium">Show my station as a verified owner</span>
          <span className="text-cw-muted">Optional. You can leave this off.</span>
        </span>
      </label>
      {error && (
        <p role="alert" className="text-cw-negative">
          {error}
        </p>
      )}
      <div className="flex justify-end">
        <button
          type="button"
          className={primaryCls}
          disabled={!draft.consentAggregate || busy}
          onClick={onSubmit}
        >
          {busy ? "Working it out…" : "Show my range"}
        </button>
      </div>
    </Screen>
  );
}

function ResultStep({ draft, onRestart }: { draft: OwnerDraft; onRestart: () => void }) {
  const r = draft.result;
  if (!r) return null;
  const f = r.forecast;
  return (
    <Screen question={`Expect ${monthLabel(r.next_month)} to land in this range.`}>
      <div className="flex flex-col gap-3 border border-cw-line bg-cw-surface p-8">
        <span className="text-cw-muted">Your station, next month</span>
        <span className="font-cw-mono text-[clamp(30px,5.5vw,52px)] font-medium tabular-nums text-cw-accent">
          {formatKwhBound(kwh(f.p10_kwh), "low")} to {formatKwhBound(kwh(f.p90_kwh), "high")}
        </span>
        <span className="text-cw-muted">Nine times in ten it lands inside this range.</span>
      </div>
      <div className="flex flex-col gap-3 border border-cw-line bg-cw-surface p-8">
        <span className="text-cw-muted">Against stations of the same age and power</span>
        <p className="text-[22px] font-medium">
          Your latest month is ahead of about{" "}
          <span className="font-cw-mono tabular-nums">{Math.round(r.peer_percentile)}</span> in 100
          comparable stations.
        </p>
        <span className="text-cw-muted">
          Comparable stations deliver {formatKwhBound(kwh(r.peer.p10_kwh), "low")} to{" "}
          {formatKwhBound(kwh(r.peer.p90_kwh), "high")} in {monthLabel(r.next_month)}.
        </span>
      </div>
      <p className="max-w-[680px] text-[14px] text-cw-muted">
        Based on {r.readings_used} month{r.readings_used === 1 ? "" : "s"} of your bills
        {r.readings_ignored > 0 &&
          ` (${r.readings_ignored} ignored: before go-live, or more than your connectors could deliver)`}
        . Peer curve <span className="font-cw-mono">{r.model_version}</span>, an early estimate that
        sharpens as more owners upload.
      </p>
      <div className="flex justify-end">
        <button type="button" className={primaryCls} onClick={onRestart}>
          Start again
        </button>
      </div>
    </Screen>
  );
}

export function Owner() {
  const navigate = useNavigate();
  const params = useParams();
  const raw = params.step ?? "station";
  const step: StepId = isStep(raw) ? raw : "station";
  const at = ORDER.indexOf(step);

  const [draft, setDraft] = useState<OwnerDraft>(loadDraft);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => saveDraft(draft), [draft]);

  const set = useCallback((p: Partial<OwnerDraft>) => setDraft((d) => ({ ...d, ...p })), []);
  const go = useCallback((id: StepId) => navigate(`/owner/${id}`), [navigate]);
  const next = () => go(ORDER[Math.min(at + 1, ORDER.length - 1)] ?? "station");

  // A link into the middle of the flow with nothing stored goes back to the
  // first question rather than showing an empty screen.
  const missing =
    (at >= 1 && !draft.station) ||
    (at >= 2 && draft.connectors.length === 0) ||
    (at >= 5 && (!draft.meter || toReadings(draft).length === 0)) ||
    (step === "result" && !draft.result);
  useEffect(() => {
    if (missing) navigate("/owner", { replace: true });
  }, [missing, navigate]);

  const submit = async () => {
    if (!draft.station || !draft.installMonth || !draft.meter) return;
    setBusy(true);
    setError(null);
    const { data, error: err } = await api.POST("/api/internal/owner/submissions", {
      body: {
        station_id: draft.station.id,
        connector_ids: draft.connectors,
        install_month: draft.installMonth,
        meter_type: draft.meter,
        readings: toReadings(draft),
        consent_aggregate: draft.consentAggregate,
        consent_public: draft.consentPublic,
      },
    });
    setBusy(false);
    if (!data) {
      const detail = (err as { detail?: unknown } | undefined)?.detail;
      setError(
        typeof detail === "string"
          ? detail
          : "We could not use those figures. Check the months and the kWh.",
      );
      return;
    }
    set({ result: data });
    go("result");
  };

  const body = (() => {
    switch (step) {
      case "station":
        return (
          <StationStep
            draft={draft}
            onPick={(s) =>
              setDraft((d) => ({
                ...d,
                station: s,
                connectors: d.station?.id === s.id ? d.connectors : [],
              }))
            }
            onNext={next}
          />
        );
      case "connectors":
        return <ConnectorsStep draft={draft} set={set} onNext={next} />;
      case "installed":
        return <InstalledStep draft={draft} set={set} onNext={next} />;
      case "meter":
        return (
          <MeterStep
            onPick={(m) => {
              set({ meter: m });
              next();
            }}
          />
        );
      case "energy":
        return <EnergyStep draft={draft} set={set} onNext={next} />;
      case "consent":
        return <ConsentStep draft={draft} set={set} onSubmit={submit} busy={busy} error={error} />;
      case "result":
        return (
          <ResultStep
            draft={draft}
            onRestart={() => {
              clearDraft();
              setDraft(blankDraft());
              navigate("/owner", { replace: true });
            }}
          />
        );
    }
  })();

  return (
    <div className="cw-surface-root relative flex min-h-dvh flex-col bg-cw-ground font-cw-sans text-[17px] leading-[1.6] text-cw-text antialiased">
      <header className="flex items-center justify-between gap-6 px-[clamp(24px,7vw,112px)] py-5">
        <Link
          to="/"
          className="inline-flex min-h-[44px] items-center font-cw-mono text-[clamp(18px,1.6vw,21px)] font-medium tracking-[0.08em] text-cw-text uppercase"
        >
          Chargeworthy
        </Link>
        <span className="font-cw-mono text-[14px] tracking-[0.08em] text-cw-muted">
          {step === "result" ? "RESULT" : `${String(at + 1).padStart(2, "0")} / 06`}
        </span>
      </header>
      <div className="h-0.5 bg-cw-line">
        <div
          className="h-0.5 bg-cw-slate transition-[width] duration-[420ms] ease-(--cw-ease)"
          style={{ width: `${Math.min(((at + 1) / 6) * 100, 100)}%` }}
        />
      </div>
      {step !== "station" && step !== "result" && (
        <div className="px-[clamp(24px,7vw,112px)] pt-3.5">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="inline-flex min-h-[56px] items-center px-1 text-[17px] text-cw-muted transition-colors duration-200 hover:text-cw-text"
          >
            ← Back
          </button>
        </div>
      )}
      <main className="flex flex-grow flex-col justify-center px-[clamp(24px,7vw,112px)] pt-[clamp(24px,5vw,56px)] pb-[clamp(48px,7vw,72px)]">
        {body}
      </main>
    </div>
  );
}
