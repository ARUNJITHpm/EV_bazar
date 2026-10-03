import { useState } from "react";

import { Field, inputCls, secondaryCls } from "./ui";
import {
  historyMonths,
  lastFullMonth,
  monthFromIndex,
  monthIndex,
  monthLabel,
  totalKw,
  type DraftConnector,
  type OwnerDraft,
} from "./state";
import { WHOLE } from "./ui";

type Bill = OwnerDraft["bill"];

/** The bill image, shown beside the form so each field can be checked against it. */
export function BillImage({ id, type }: { id: string | null; type: string | null }) {
  if (!id) return null;
  const src = `/api/internal/owner/bill-images/${id}`;
  return (
    <div className="flex flex-col gap-3 border border-cw-line bg-cw-surface p-4">
      {/* "Saved", never "read": nothing is extracted from the file in this
          version, and the owner types every figure (see BillUpload). */}
      <p className="cw-rise m-0 text-[15px] text-cw-text">
        Bill saved. That&apos;s the hardest part done. Check the figures against it.
      </p>
      {type === "application/pdf" ? (
        <object
          data={src}
          type="application/pdf"
          className="h-[60vh] w-full"
          aria-label="Your bill"
        >
          <a href={src} className="text-cw-slate underline" target="_blank" rel="noreferrer">
            Open your bill (PDF)
          </a>
        </object>
      ) : (
        <img
          src={src}
          alt="This bill image has been deleted."
          className="max-h-[70vh] w-full object-contain text-cw-muted"
        />
      )}
      <a
        href={src}
        target="_blank"
        rel="noreferrer"
        className="inline-flex min-h-[44px] items-center text-[15px] text-cw-slate"
      >
        Open full size
      </a>
    </div>
  );
}

const num = (v: string) => v.replace(/[^\d.,]/g, "");

/**
 * The bill's fields, for the owner to confirm or correct. Only the month and the
 * units are required; everything under "More from your bill" is optional and a
 * card on the home page hides itself when its fields were left blank.
 *
 * Nothing is saved from here: the parent sends the fields only after the
 * confirmation box is ticked.
 */
export function BillForm({
  bill,
  set,
  connectors,
  error,
}: {
  bill: Bill;
  set: (p: Partial<Bill>) => void;
  /** Known connectors, so the units ceiling can be shown; empty during onboarding. */
  connectors: DraftConnector[];
  error: string | null;
}) {
  const latest = lastFullMonth();
  const period = bill.period ?? latest;
  const step = (d: number) => {
    const next = monthIndex(period) + d;
    if (next <= monthIndex(latest)) set({ period: monthFromIndex(next) });
  };
  const [more, setMore] = useState(false);
  const stepper =
    "inline-flex min-h-[56px] min-w-[56px] items-center justify-center border border-cw-line bg-cw-surface text-[24px] transition-colors duration-200 hover:border-cw-slate";
  const kw = totalKw(connectors);

  return (
    <div className="flex max-w-[640px] flex-col gap-7">
      <Field id="bill-month" label="Billing month">
        <div className="flex items-center gap-4">
          <button
            type="button"
            className={stepper}
            aria-label="Earlier month"
            onClick={() => step(-1)}
          >
            −
          </button>
          <output
            id="bill-month"
            className="min-w-[160px] text-center font-cw-mono text-[26px] font-medium"
          >
            {monthLabel(period)}
          </output>
          <button
            type="button"
            className={stepper}
            aria-label="Later month"
            onClick={() => step(1)}
          >
            +
          </button>
        </div>
      </Field>

      <Field
        id="bill-kwh"
        label="Units consumed (kWh)"
        hint={
          kw > 0
            ? `Between 0 and ${WHOLE.format(kw * 744)} kWh for your connectors.`
            : "As printed on the bill."
        }
      >
        <input
          id="bill-kwh"
          inputMode="decimal"
          className={`${inputCls} font-cw-mono tabular-nums`}
          placeholder="kWh"
          value={bill.kwh}
          onChange={(e) => set({ kwh: num(e.target.value), period })}
        />
      </Field>

      <button
        type="button"
        className={secondaryCls}
        aria-expanded={more}
        onClick={() => setMore((m) => !m)}
      >
        {more ? "Hide the rest of the bill" : "More from your bill (optional)"}
      </button>

      {more && (
        <div className="flex flex-col gap-7">
          <Field
            id="bill-tariff"
            label="Tariff category"
            hint="For example LT-VI EV charging. An EV category tells us it has its own meter."
          >
            <input
              id="bill-tariff"
              className={inputCls}
              value={bill.tariff}
              onChange={(e) => set({ tariff: e.target.value })}
            />
          </Field>
          <Field id="bill-board" label="Electricity board" hint="KSEB, TANGEDCO, BESCOM…">
            <input
              id="bill-board"
              className={inputCls}
              value={bill.board}
              onChange={(e) => set({ board: e.target.value })}
            />
          </Field>
          <Field id="bill-consumer" label="Consumer number" hint="We keep only the last 4 digits.">
            <input
              id="bill-consumer"
              className={`${inputCls} font-cw-mono`}
              value={bill.consumerNumber}
              onChange={(e) => set({ consumerNumber: e.target.value })}
            />
          </Field>

          <fieldset className="flex flex-col gap-4">
            <legend className="mb-2 text-[17px] font-medium">Demand</legend>
            <div className="flex gap-3">
              {(["kVA", "kW"] as const).map((u) => (
                <button
                  key={u}
                  type="button"
                  aria-pressed={bill.demandUnit === u}
                  onClick={() => set({ demandUnit: u })}
                  className={`min-h-[56px] flex-1 border px-5 font-cw-mono ${
                    bill.demandUnit === u
                      ? "border-cw-accent bg-cw-surface-2"
                      : "border-cw-line bg-cw-surface"
                  }`}
                >
                  {u}
                </button>
              ))}
            </div>
            <Field id="bill-contract" label={`Contract / sanctioned demand (${bill.demandUnit})`}>
              <input
                id="bill-contract"
                inputMode="decimal"
                className={`${inputCls} font-cw-mono tabular-nums`}
                value={bill.contractDemand}
                onChange={(e) => set({ contractDemand: num(e.target.value) })}
              />
            </Field>
            <Field id="bill-recorded" label={`Recorded maximum demand (${bill.demandUnit})`}>
              <input
                id="bill-recorded"
                inputMode="decimal"
                className={`${inputCls} font-cw-mono tabular-nums`}
                value={bill.recordedDemand}
                onChange={(e) => set({ recordedDemand: num(e.target.value) })}
              />
            </Field>
          </fieldset>

          <fieldset className="flex flex-col gap-4">
            <legend className="mb-2 text-[17px] font-medium">Power factor</legend>
            <Field id="bill-pf" label="Power factor, between 0 and 1">
              <input
                id="bill-pf"
                inputMode="decimal"
                className={`${inputCls} font-cw-mono tabular-nums`}
                placeholder="0.95"
                value={bill.powerFactor}
                onChange={(e) => set({ powerFactor: num(e.target.value) })}
              />
            </Field>
            <div className="flex gap-3">
              {(["penalty", "incentive"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  aria-pressed={bill.pfEffect === k}
                  onClick={() => set({ pfEffect: bill.pfEffect === k ? null : k })}
                  className={`min-h-[56px] flex-1 border px-5 capitalize ${
                    bill.pfEffect === k
                      ? "border-cw-accent bg-cw-surface-2"
                      : "border-cw-line bg-cw-surface"
                  }`}
                >
                  {k}
                </button>
              ))}
            </div>
            <Field id="bill-pf-amt" label="Penalty or incentive amount (₹)">
              <input
                id="bill-pf-amt"
                inputMode="decimal"
                className={`${inputCls} font-cw-mono tabular-nums`}
                value={bill.pfAmountRupees}
                onChange={(e) => set({ pfAmountRupees: num(e.target.value) })}
              />
            </Field>
          </fieldset>

          <fieldset className="flex flex-col gap-4">
            <legend className="mb-2 text-[17px] font-medium">Time-of-day units (kWh)</legend>
            {(
              [
                ["todPeak", "Peak"],
                ["todNormal", "Normal"],
                ["todOffPeak", "Off-peak"],
              ] as const
            ).map(([key, label]) => (
              <Field key={key} id={`bill-${key}`} label={label}>
                <input
                  id={`bill-${key}`}
                  inputMode="decimal"
                  className={`${inputCls} font-cw-mono tabular-nums`}
                  value={bill[key]}
                  onChange={(e) => set({ [key]: num(e.target.value) })}
                />
              </Field>
            ))}
          </fieldset>

          <fieldset className="flex flex-col gap-4">
            <legend className="mb-2 text-[17px] font-medium">
              Past months printed on the bill (kWh)
            </legend>
            {historyMonths(period).map((m) => (
              <div key={m} className="flex items-center gap-4">
                <label htmlFor={`hist-${m}`} className="w-[120px] shrink-0">
                  {monthLabel(m)}
                </label>
                <input
                  id={`hist-${m}`}
                  inputMode="decimal"
                  className={`${inputCls} font-cw-mono tabular-nums`}
                  value={bill.history[m] ?? ""}
                  onChange={(e) => set({ history: { ...bill.history, [m]: num(e.target.value) } })}
                />
              </div>
            ))}
          </fieldset>
        </div>
      )}

      <label className="flex cursor-pointer gap-4 border border-cw-line bg-cw-surface p-6">
        <input
          type="checkbox"
          className="mt-1 h-6 w-6 shrink-0 accent-cw-accent"
          checked={bill.confirmed}
          onChange={(e) => set({ confirmed: e.target.checked })}
        />
        <span>
          <span className="block text-[19px] font-medium">These match my bill</span>
          <span className="text-cw-muted">
            We save only what you confirm here, and nothing is read from the image for you.
          </span>
        </span>
      </label>

      {error && (
        <p role="alert" className="text-cw-negative">
          {error}
        </p>
      )}
    </div>
  );
}
