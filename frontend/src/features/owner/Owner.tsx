import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { Answer, Answers, Screen } from "../public/flow/Question";
import { BillForm, BillImage } from "./BillForm";
import { BillUpload } from "./BillUpload";
import { PlacePicker } from "./PlacePicker";
import {
  PRESETS,
  blankDraft,
  clearDraft,
  detailOf,
  expandConnectors,
  lastFullMonth,
  loadDraft,
  monthFromIndex,
  monthIndex,
  monthLabel,
  saveDraft,
  tariffImpliesOwnMeter,
  toBillIn,
  totalKw,
  type OwnerDraft,
  type Standard,
} from "./state";
import { Shell, choiceCls, inputCls, primaryCls, secondaryCls, useOwner } from "./ui";

/**
 * Owner onboarding: sign in with a phone number and a code, add one bill, tell us
 * about the station once, and land on the station's home page. One question per
 * screen, no dropdowns, 56px tap targets, every step a real URL.
 *
 * Nothing here works anything out. The forecast and the peer comparison come from
 * the API, and the fields are saved only after the owner ticks "These match my
 * bill" and the consent box.
 */

type StepId =
  | "phone"
  | "code"
  | "bill"
  | "details"
  | "name"
  | "place"
  | "connectors"
  | "live"
  | "meter"
  | "consent";
const ORDER: StepId[] = [
  "phone",
  "code",
  "bill",
  "details",
  "name",
  "place",
  "connectors",
  "live",
  "meter",
  "consent",
];
const isStep = (v: string): v is StepId => (ORDER as string[]).includes(v);

function NextRow({
  onNext,
  disabled,
  label = "Continue",
}: {
  onNext: () => void;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <div className="flex justify-end">
      <button type="button" className={primaryCls} disabled={disabled} onClick={onNext}>
        {label}
      </button>
    </div>
  );
}

function PhoneStep({
  draft,
  set,
  onSent,
}: {
  draft: OwnerDraft;
  set: (p: Partial<OwnerDraft>) => void;
  onSent: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const send = async () => {
    setBusy(true);
    setError(null);
    const { data, error: err } = await api.POST("/api/internal/owner/otp/request", {
      body: { phone: draft.phone },
    });
    setBusy(false);
    if (!data) return setError(detailOf(err, "We could not send a code. Try again in a moment."));
    onSent();
  };
  return (
    <Screen question="What is your mobile number?">
      <p className="max-w-[640px] text-cw-muted">
        We send a code to sign you in. No password and no email.
      </p>
      <input
        type="tel"
        inputMode="numeric"
        autoComplete="tel-national"
        className={`${inputCls} max-w-[420px] font-cw-mono tabular-nums`}
        placeholder="98765 43210"
        aria-label="Mobile number"
        value={draft.phone}
        onChange={(e) => set({ phone: e.target.value.replace(/[^\d+ ]/g, "") })}
      />
      {error && (
        <p role="alert" className="text-cw-negative">
          {error}
        </p>
      )}
      <NextRow
        onNext={() => void send()}
        disabled={busy || draft.phone.replace(/\D/g, "").length < 10}
        label={busy ? "Sending…" : "Send code"}
      />
    </Screen>
  );
}

function CodeStep({
  draft,
  onSignedIn,
}: {
  draft: OwnerDraft;
  onSignedIn: (stations: number) => void;
}) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const verify = async () => {
    setBusy(true);
    setError(null);
    const { data, error: err } = await api.POST("/api/internal/owner/otp/verify", {
      body: { phone: draft.phone, code },
    });
    setBusy(false);
    if (!data) return setError(detailOf(err, "That code is not right."));
    onSignedIn(data.station_count);
  };
  return (
    <Screen question="Enter the code we sent.">
      <input
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={8}
        className={`${inputCls} max-w-[300px] font-cw-mono tracking-[0.3em] tabular-nums`}
        aria-label="One-time code"
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
      />
      {import.meta.env.DEV && (
        <p className="text-[15px] text-cw-muted">Development build: the code is 000000.</p>
      )}
      {error && (
        <p role="alert" className="text-cw-negative">
          {error}
        </p>
      )}
      <NextRow
        onNext={() => void verify()}
        disabled={busy || code.length < 4}
        label={busy ? "Checking…" : "Sign in"}
      />
    </Screen>
  );
}

function BillStep({
  draft,
  set,
  onNext,
}: {
  draft: OwnerDraft;
  set: (p: Partial<OwnerDraft>) => void;
  onNext: () => void;
}) {
  return (
    <Screen question="Add this month's electricity bill.">
      <BillUpload
        onUploaded={(u) => {
          set({ bill: { ...draft.bill, imageId: u.imageId, imageType: u.contentType } });
          onNext();
        }}
        onTypeInstead={() => {
          set({ bill: { ...draft.bill, imageId: null, imageType: null } });
          onNext();
        }}
      />
    </Screen>
  );
}

function DetailsStep({
  draft,
  set,
  onNext,
}: {
  draft: OwnerDraft;
  set: (p: Partial<OwnerDraft>) => void;
  onNext: () => void;
}) {
  const b = draft.bill;
  const ok = !!toBillIn(b) && b.confirmed;
  return (
    <Screen question="Check the figures against your bill.">
      <div className={b.imageId ? "grid gap-8 lg:grid-cols-2" : ""}>
        <BillImage id={b.imageId} type={b.imageType} />
        <BillForm
          bill={b}
          set={(p) => set({ bill: { ...b, ...p } })}
          connectors={draft.connectors}
          error={null}
        />
      </div>
      <NextRow onNext={onNext} disabled={!ok} />
    </Screen>
  );
}

function NameStep({
  draft,
  set,
  onNext,
}: {
  draft: OwnerDraft;
  set: (p: Partial<OwnerDraft>) => void;
  onNext: () => void;
}) {
  return (
    <Screen question="What is the station called?">
      <input
        className={`${inputCls} max-w-[560px]`}
        aria-label="Station name"
        maxLength={120}
        value={draft.name}
        onChange={(e) => set({ name: e.target.value })}
      />
      <NextRow onNext={onNext} disabled={draft.name.trim() === ""} />
    </Screen>
  );
}

function PlaceStep({
  draft,
  set,
  onNext,
}: {
  draft: OwnerDraft;
  set: (p: Partial<OwnerDraft>) => void;
  onNext: () => void;
}) {
  return (
    <Screen question="Where is it?">
      <PlacePicker
        pin={draft.pin}
        address={draft.address}
        onChange={(p) => set({ pin: p.pin, address: p.address })}
      />
      <NextRow onNext={onNext} disabled={!draft.pin} />
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
  const [custom, setCustom] = useState<{ standard: Standard; kw: string }>({
    standard: "CCS2",
    kw: "",
  });
  const add = (standard: Standard, power_kw: number) => {
    const at = draft.connectors.findIndex(
      (c) => c.standard === standard && c.power_kw === power_kw,
    );
    set({
      connectors:
        at >= 0
          ? draft.connectors.map((c, i) => (i === at ? { ...c, count: c.count + 1 } : c))
          : [...draft.connectors, { standard, power_kw, count: 1 }],
    });
  };
  const remove = (i: number) =>
    set({
      connectors: draft.connectors
        .map((c, j) => (j === i ? { ...c, count: c.count - 1 } : c))
        .filter((c) => c.count > 0),
    });
  const kw = Number(custom.kw);
  const standards: Standard[] = ["CCS2", "Type 2 AC", "CHAdeMO", "GB/T", "Other"];
  return (
    <Screen question="Which connectors does it have?">
      <p className="max-w-[640px] text-cw-muted">Tap once for each connector.</p>
      <Answers cols={3}>
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            className={choiceCls(false)}
            onClick={() => add(p.standard, p.power_kw)}
          >
            <span className="text-[19px] font-medium">{p.label}</span>
            <span className="text-cw-muted">Tap to add</span>
          </button>
        ))}
      </Answers>
      <div className="flex max-w-[640px] flex-col gap-3">
        <p className="text-[15px] text-cw-muted">Something else</p>
        <div className="flex flex-wrap gap-3">
          {standards.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={custom.standard === s}
              className={`min-h-[56px] border px-5 ${
                custom.standard === s
                  ? "border-cw-accent bg-cw-surface-2"
                  : "border-cw-line bg-cw-surface"
              }`}
              onClick={() => setCustom({ ...custom, standard: s })}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-3">
          <input
            inputMode="decimal"
            className={`${inputCls} font-cw-mono tabular-nums`}
            placeholder="kW"
            aria-label="Power in kW"
            value={custom.kw}
            onChange={(e) => setCustom({ ...custom, kw: e.target.value.replace(/[^\d.]/g, "") })}
          />
          <button
            type="button"
            className={secondaryCls}
            disabled={!(kw > 0 && kw <= 1000)}
            onClick={() => {
              add(custom.standard, kw);
              setCustom({ ...custom, kw: "" });
            }}
          >
            Add
          </button>
        </div>
      </div>
      {draft.connectors.length > 0 && (
        <ul className="flex max-w-[640px] flex-col gap-3" aria-label="Connectors added">
          {draft.connectors.map((c, i) => (
            <li
              key={`${c.standard}-${c.power_kw}`}
              className="flex min-h-[56px] items-center justify-between gap-4 border border-cw-line bg-cw-surface px-5"
            >
              <span>
                <span className="font-cw-mono tabular-nums">{c.count}</span> × {c.standard}{" "}
                <span className="font-cw-mono tabular-nums">{c.power_kw} kW</span>
              </span>
              <button
                type="button"
                className="inline-flex min-h-[56px] min-w-[56px] items-center justify-center text-[24px] text-cw-muted"
                aria-label={`Remove one ${c.standard} ${c.power_kw} kW`}
                onClick={() => remove(i)}
              >
                −
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="text-cw-muted">
        Total <span className="font-cw-mono tabular-nums">{totalKw(draft.connectors)} kW</span>
      </p>
      <NextRow onNext={onNext} disabled={draft.connectors.length === 0} />
    </Screen>
  );
}

function LiveStep({
  draft,
  set,
  onNext,
}: {
  draft: OwnerDraft;
  set: (p: Partial<OwnerDraft>) => void;
  onNext: () => void;
}) {
  const billMonth = draft.bill.period ?? lastFullMonth();
  const value = draft.wentLive ?? billMonth;
  const step = (d: number) => {
    const next = monthIndex(value) + d;
    if (next <= monthIndex(billMonth)) set({ wentLive: monthFromIndex(next) });
  };
  const stepper =
    "inline-flex min-h-[56px] min-w-[56px] items-center justify-center border border-cw-line bg-cw-surface text-[24px] transition-colors duration-200 hover:border-cw-slate";
  return (
    <Screen question="Which month did it start charging?">
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
        <span className="font-cw-mono tabular-nums">
          {monthIndex(billMonth) - monthIndex(value) + 1}
        </span>{" "}
        months of operation by {monthLabel(billMonth)}
      </p>
      <NextRow
        onNext={() => {
          set({ wentLive: value });
          onNext();
        }}
      />
    </Screen>
  );
}

function MeterStep({ onPick }: { onPick: (m: "separate" | "shared" | "unsure") => void }) {
  return (
    <Screen question="Does the charger have its own meter?">
      <Answers cols={3}>
        <Answer
          title="Yes"
          sub="The bill shows only charging."
          onClick={() => onPick("separate")}
        />
        <Answer
          title="No, shared"
          sub="With a shop, office or building."
          onClick={() => onPick("shared")}
        />
        <Answer
          title="Not sure"
          sub="We will flag your figures as possibly including other load."
          onClick={() => onPick("unsure")}
        />
      </Answers>
    </Screen>
  );
}

function ConsentStep({
  draft,
  set,
  busy,
  error,
  onSubmit,
}: {
  draft: OwnerDraft;
  set: (p: Partial<OwnerDraft>) => void;
  busy: boolean;
  error: string | null;
  onSubmit: () => void;
}) {
  return (
    <Screen question="One last thing.">
      <label className="flex max-w-[680px] cursor-pointer gap-4 border border-cw-line bg-cw-surface p-6">
        <input
          type="checkbox"
          className="mt-1 h-6 w-6 shrink-0 accent-cw-accent"
          checked={draft.consent}
          onChange={(e) => set({ consent: e.target.checked })}
        />
        <span>
          <span className="block text-[19px] font-medium">
            Use my figures to benchmark and forecast my station.
          </span>
          <span className="text-cw-muted">
            Only published as anonymised district averages of 10 or more stations.
          </span>
        </span>
      </label>
      {error && (
        <p role="alert" className="text-cw-negative">
          {error}
        </p>
      )}
      <NextRow
        onNext={onSubmit}
        disabled={!draft.consent || busy}
        label={busy ? "Setting up your station…" : "Show my station"}
      />
    </Screen>
  );
}

export function Owner() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const params = useParams();
  const raw = params.step ?? "phone";
  const step: StepId = isStep(raw) ? raw : "phone";
  const me = useOwner();

  const [draft, setDraft] = useState<OwnerDraft>(loadDraft);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => saveDraft(draft), [draft]);

  const set = useCallback((p: Partial<OwnerDraft>) => setDraft((d) => ({ ...d, ...p })), []);
  const go = useCallback((id: StepId) => navigate(`/owner/${id}`), [navigate]);

  const ownMeter = tariffImpliesOwnMeter(draft.bill.tariff);
  const order = ownMeter ? ORDER.filter((s) => s !== "meter") : ORDER;
  const at = Math.max(order.indexOf(step), 0);
  const next = () => go(order[Math.min(at + 1, order.length - 1)] ?? "phone");

  // Already signed in: skip the phone screens. A returning owner goes to their
  // stations; someone new goes straight to the bill.
  useEffect(() => {
    if (me.isPending || !me.data) return;
    if (step === "phone" || step === "code") {
      navigate(me.data.station_count > 0 ? "/owner/home" : "/owner/bill", { replace: true });
    }
  }, [me.isPending, me.data, step, navigate]);

  // A link into the middle of the flow with nothing behind it goes back to the start.
  const needsSession = step !== "phone" && step !== "code";
  const missing =
    (needsSession && !me.isPending && !me.data) ||
    (order.indexOf(step) > order.indexOf("details") &&
      !(toBillIn(draft.bill) && draft.bill.confirmed)) ||
    (step === "connectors" && !draft.pin) ||
    (order.indexOf(step) > order.indexOf("connectors") && draft.connectors.length === 0);
  useEffect(() => {
    if (missing) navigate("/owner", { replace: true });
  }, [missing, navigate]);

  const submit = async () => {
    const bill = toBillIn(draft.bill);
    if (!bill || !draft.pin || !draft.wentLive) return;
    setBusy(true);
    setError(null);
    const { data, error: err } = await api.POST("/api/internal/owner/onboard", {
      body: {
        station: {
          name: draft.name.trim(),
          address: draft.address || null,
          lat: draft.pin.lat,
          lng: draft.pin.lng,
          went_live: draft.wentLive,
        },
        connectors: expandConnectors(draft.connectors),
        bill,
        meter_answer: ownMeter ? null : draft.meter,
        consent_aggregate: draft.consent,
      },
    });
    setBusy(false);
    if (!data) {
      setError(detailOf(err, "We could not save that. Check the figures and try again."));
      return;
    }
    clearDraft();
    setDraft(blankDraft());
    await client.invalidateQueries({ queryKey: ["owner-me"] });
    navigate(`/owner/station/${data.station_id}`, { replace: true });
  };

  const body = (() => {
    switch (step) {
      case "phone":
        return <PhoneStep draft={draft} set={set} onSent={() => go("code")} />;
      case "code":
        return (
          <CodeStep
            draft={draft}
            onSignedIn={async (stations) => {
              await client.invalidateQueries({ queryKey: ["owner-me"] });
              navigate(stations > 0 ? "/owner/home" : "/owner/bill", { replace: true });
            }}
          />
        );
      case "bill":
        return <BillStep draft={draft} set={set} onNext={next} />;
      case "details":
        return <DetailsStep draft={draft} set={set} onNext={next} />;
      case "name":
        return <NameStep draft={draft} set={set} onNext={next} />;
      case "place":
        return <PlaceStep draft={draft} set={set} onNext={next} />;
      case "connectors":
        return <ConnectorsStep draft={draft} set={set} onNext={next} />;
      case "live":
        return <LiveStep draft={draft} set={set} onNext={next} />;
      case "meter":
        return (
          <MeterStep
            onPick={(m) => {
              set({ meter: m });
              next();
            }}
          />
        );
      case "consent":
        return (
          <ConsentStep
            draft={draft}
            set={set}
            busy={busy}
            error={error}
            onSubmit={() => void submit()}
          />
        );
    }
  })();

  return (
    <Shell
      progress={{ at: at + 1, of: order.length }}
      back={step !== "phone" && step !== "bill" ? () => navigate(-1) : undefined}
    >
      <div className="flex flex-grow flex-col justify-center">{body}</div>
    </Shell>
  );
}
