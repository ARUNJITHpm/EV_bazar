import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { formatKva, formatKw, kva, kw } from "../../lib/units";
import { Card, Field, primaryCls, secondaryCls } from "./ui";
import { detailOf } from "./state";
import { startPrivateGridRequest, finishPrivateGridRequest } from "./grid-cache";

type Area = components["schemas"]["OwnerAreaOut"];
type Grid = components["schemas"]["OwnerGridOut"];
type GridIn = components["schemas"]["GridDetailsIn"];

const inputCls =
  "min-h-[48px] w-full border border-cw-line bg-cw-ground px-3 py-2 font-cw-mono text-cw-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cw-slate";
const todayIst = () => new Date(Date.now() + 330 * 60000).toISOString().slice(0, 10);
const recordedIst = (date: string) =>
  new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(date));
const numeric = (text: string) => (text.trim() === "" ? null : Number(text));

export function AreaCard({ area }: { area: Area }) {
  return (
    <Card title="Your area">
      <p className="text-cw-muted">
        Public context for{" "}
        {[area.district, area.state].filter(Boolean).join(", ") || "an unresolved area"}. Each
        source keeps its published coverage.
      </p>
      <dl className="divide-y divide-cw-line">
        {area.items.map((item) => (
          <div key={item.key} className="py-4">
            <dt className="font-medium">{item.label}</dt>
            <dd className="mt-1">
              <p className={item.value === null ? "text-cw-muted" : "font-cw-mono tabular-nums"}>
                {item.value ?? "Not available yet"}
              </p>
              {item.scope && <p className="text-cw-muted">{item.scope}</p>}
              <p className="mt-2 text-[15px] text-cw-muted">
                {item.source_url ? (
                  <a
                    href={item.source_url}
                    className="underline underline-offset-4"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {item.source_name}
                  </a>
                ) : (
                  item.source_name
                )}
                {item.reporting_period ? ` · ${item.reporting_period}` : ""}
                {item.retrieved_on ? ` · retrieved ${item.retrieved_on}` : ""}
              </p>
              <p className="text-[15px] text-cw-muted">{item.note}</p>
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function GridEditor({
  initial,
  busy,
  onSave,
  onCancel,
}: {
  initial: Grid["details"];
  busy: boolean;
  onSave: (values: Omit<GridIn, "consent_private">) => Promise<void>;
  onCancel: () => void;
}) {
  const [date, setDate] = useState(initial?.effective_on ?? todayIst());
  const [sanctioned, setSanctioned] = useState(String(initial?.sanctioned_load_kva ?? ""));
  const [connected, setConnected] = useState(String(initial?.connected_load_kw ?? ""));
  const [ownership, setOwnership] = useState<GridIn["transformer_ownership"]>(
    initial?.transformer_ownership ?? "unknown",
  );
  const [rating, setRating] = useState(String(initial?.transformer_rating_kva ?? ""));
  return (
    <form
      className="flex flex-col gap-5"
      onSubmit={(event) => {
        event.preventDefault();
        void onSave({
          expected_revision_id: initial?.id ?? null,
          effective_on: date,
          sanctioned_load_kva: numeric(sanctioned),
          connected_load_kw: numeric(connected),
          transformer_ownership: ownership,
          transformer_rating_kva: numeric(rating),
        });
      }}
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="grid-date" label="Details as of">
          <input
            id="grid-date"
            type="date"
            required
            max={todayIst()}
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field id="grid-sanctioned" label="Sanctioned load (kVA)" hint="Leave blank if unknown.">
          <input
            id="grid-sanctioned"
            type="number"
            min="0"
            max="1000000"
            step="any"
            value={sanctioned}
            onChange={(e) => setSanctioned(e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field
          id="grid-connected"
          label="Connected load (kW)"
          hint="kW and kVA describe different quantities."
        >
          <input
            id="grid-connected"
            type="number"
            min="0"
            max="1000000"
            step="any"
            value={connected}
            onChange={(e) => setConnected(e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field id="grid-ownership" label="Transformer">
          <select
            id="grid-ownership"
            value={ownership}
            onChange={(e) => setOwnership(e.target.value as GridIn["transformer_ownership"])}
            className={inputCls}
          >
            <option value="unknown">Unknown</option>
            <option value="own">Own transformer</option>
            <option value="shared">Shared transformer</option>
          </select>
        </Field>
        <Field
          id="grid-rating"
          label="Transformer rating (kVA)"
          hint="Nameplate rating, if known; this does not confirm spare capacity."
        >
          <input
            id="grid-rating"
            type="number"
            min="0.01"
            max="1000000"
            step="any"
            value={rating}
            onChange={(e) => setRating(e.target.value)}
            className={inputCls}
          />
        </Field>
      </div>
      <div className="flex flex-wrap gap-3">
        <button type="submit" disabled={busy} className={primaryCls}>
          {busy ? "Saving…" : "Save grid revision"}
        </button>
        <button type="button" disabled={busy} onClick={onCancel} className={secondaryCls}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export function AreaGrid({ stationId }: { stationId: number }) {
  const client = useQueryClient();
  const pendingRequest = useRef<AbortController | null>(null);
  useEffect(() => () => pendingRequest.current?.abort(), []);
  const [editing, setEditing] = useState(false);
  const [editorInitial, setEditorInitial] = useState<Grid["details"]>(null);
  const [consent, setConsent] = useState(false);
  const [outageMonth, setOutageMonth] = useState(todayIst().slice(0, 7));
  const [outageHours, setOutageHours] = useState("");
  const [outageRevision, setOutageRevision] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [asking, setAsking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const gridKey = ["owner-grid", stationId] as const;
  const area = useQuery({
    queryKey: ["owner-area", stationId],
    queryFn: async ({ signal }) => {
      const result = await api.GET("/api/internal/owner/stations/{station_id}/area", {
        params: { path: { station_id: stationId } },
        signal,
      });
      if (!result.data) throw new Error("Area context could not be loaded.");
      return result.data;
    },
    retry: false,
  });
  const grid = useQuery({
    queryKey: gridKey,
    queryFn: async ({ signal }) => {
      const result = await api.GET("/api/internal/owner/stations/{station_id}/grid", {
        params: { path: { station_id: stationId } },
        signal,
      });
      if (!result.data) throw new Error("Your grid details could not be loaded.");
      return result.data;
    },
    retry: false,
  });

  const saveGrid = async (values: Omit<GridIn, "consent_private">) => {
    if (!consent) return setError("Agree to private grid storage before saving.");
    const controller = startPrivateGridRequest();
    pendingRequest.current = controller;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.POST("/api/internal/owner/stations/{station_id}/grid", {
        params: { path: { station_id: stationId } },
        signal: controller.signal,
        body: { ...values, consent_private: true },
      });
      if (controller.signal.aborted) return;
      if (!result.data) {
        if (result.response.status === 409) await grid.refetch();
        return setError(detailOf(result.error, "Grid details could not be saved. Try again."));
      }
      client.setQueryData(gridKey, result.data);
      setEditing(false);
      setEditorInitial(null);
      setMessage("Grid revision saved privately.");
    } catch {
      setError("Connection lost. Your unsaved values are still in this form.");
    } finally {
      finishPrivateGridRequest(controller);
      setBusy(false);
    }
  };
  const saveOutage = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!consent) return setError("Agree to private grid storage before saving.");
    const controller = startPrivateGridRequest();
    pendingRequest.current = controller;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.POST("/api/internal/owner/stations/{station_id}/outages", {
        params: { path: { station_id: stationId } },
        signal: controller.signal,
        body: {
          consent_private: true,
          expected_revision_id: outageRevision,
          month: `${outageMonth}-01`,
          approximate_hours: numeric(outageHours),
        },
      });
      if (controller.signal.aborted) return;
      if (!result.data)
        return setError(
          detailOf(
            result.error,
            "Outage record could not be saved. Reload the month if another revision was saved.",
          ),
        );
      client.setQueryData(gridKey, result.data);
      setOutageRevision(
        result.data.outages.find((row) => row.month === `${outageMonth}-01`)?.id ?? null,
      );
      setMessage("Approximate outage hours saved privately.");
    } catch {
      setError("Connection lost. Your unsaved values are still in this form.");
    } finally {
      finishPrivateGridRequest(controller);
      setBusy(false);
    }
  };
  const withdraw = async () => {
    const controller = startPrivateGridRequest();
    pendingRequest.current = controller;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.DELETE("/api/internal/owner/stations/{station_id}/grid", {
        signal: controller.signal,
        params: { path: { station_id: stationId } },
      });
      if (controller.signal.aborted) return;
      if (!result.response.ok) return setError("Grid details could not be deleted. Try again.");
      await client.cancelQueries({ queryKey: gridKey });
      client.setQueryData<Grid>(gridKey, (old) =>
        old ? { ...old, consent_private: false, details: null, outages: [] } : old,
      );
      setEditing(false);
      setEditorInitial(null);
      setOutageHours("");
      setOutageRevision(null);
      setConsent(false);
      setAsking(false);
      setMessage("All grid and outage revisions deleted. Private grid consent withdrawn.");
    } catch {
      setError("Connection lost. Deletion could not be confirmed; reload before retrying.");
    } finally {
      finishPrivateGridRequest(controller);
      setBusy(false);
    }
  };
  const details = grid.data?.details;
  return (
    <>
      {area.data ? (
        <AreaCard area={area.data} />
      ) : (
        <Card title="Your area">
          <p role={area.isError ? "alert" : "status"}>
            {area.isError ? "Area context could not be loaded." : "Loading public area context…"}
          </p>
          {area.isError && (
            <button className={secondaryCls} onClick={() => void area.refetch()}>
              Retry area context
            </button>
          )}
        </Card>
      )}
      <Card title="Your private grid details">
        <p>
          Optional details you enter for your own station. These fields are kept out of public data,
          forecasts and other customers’ reports.
        </p>
        {grid.isPending ? (
          <p role="status">Loading grid details…</p>
        ) : grid.isError ? (
          <>
            <p role="alert">Your grid details could not be loaded.</p>
            <button className={secondaryCls} onClick={() => void grid.refetch()}>
              Retry grid details
            </button>
          </>
        ) : (
          <>
            {details ? (
              <dl className="grid gap-3 sm:grid-cols-2">
                <div>
                  <dt className="text-cw-muted">Sanctioned load</dt>
                  <dd className="font-cw-mono">
                    {details.sanctioned_load_kva === null
                      ? "Not recorded"
                      : formatKva(kva(details.sanctioned_load_kva))}
                  </dd>
                </div>
                <div>
                  <dt className="text-cw-muted">Connected load</dt>
                  <dd className="font-cw-mono">
                    {details.connected_load_kw === null
                      ? "Not recorded"
                      : formatKw(kw(details.connected_load_kw))}
                  </dd>
                </div>
                <div>
                  <dt className="text-cw-muted">Transformer</dt>
                  <dd>{details.transformer_ownership}</dd>
                </div>
                <div>
                  <dt className="text-cw-muted">Transformer rating</dt>
                  <dd className="font-cw-mono">
                    {details.transformer_rating_kva === null
                      ? "Not recorded"
                      : formatKva(kva(details.transformer_rating_kva))}
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-cw-muted">Recorded</dt>
                  <dd>
                    {recordedIst(details.recorded_at)} IST · details as of {details.effective_on}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="text-cw-muted">No grid details recorded.</p>
            )}
            {grid.data?.storage_available ? (
              <>
                <label className="flex min-h-[48px] items-start gap-3">
                  <input
                    type="checkbox"
                    className="mt-1.5 h-5 w-5 accent-cw-accent"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                  />
                  <span>
                    I agree to store these grid details privately for my station. I can withdraw
                    this consent and delete every revision below.
                  </span>
                </label>
                {editing ? (
                  <GridEditor
                    initial={editorInitial}
                    busy={busy || !consent}
                    onSave={saveGrid}
                    onCancel={() => {
                      setEditing(false);
                      setEditorInitial(null);
                    }}
                  />
                ) : (
                  <button
                    type="button"
                    className={secondaryCls}
                    onClick={() => {
                      setEditorInitial(details ?? null);
                      setEditing(true);
                    }}
                  >
                    {details ? "Edit grid details" : "Add grid details"}
                  </button>
                )}
                <div className="mt-4 border-t border-cw-line pt-5">
                  <h3 className="text-[20px] font-medium">Your approximate outage hours</h3>
                  <p className="text-cw-muted">
                    Your own monthly log. It is not calculated from the area's average supply hours.
                  </p>
                  {grid.data?.outages.map((row) => (
                    <p key={row.month} className="mt-2 font-cw-mono">
                      {row.month.slice(0, 7)} ·{" "}
                      {row.approximate_hours === null
                        ? "Not recorded"
                        : `${row.approximate_hours.toLocaleString("en-IN")} hours`}{" "}
                      <button
                        type="button"
                        className="ml-3 min-h-[44px] underline underline-offset-4"
                        onClick={() => {
                          setOutageMonth(row.month.slice(0, 7));
                          setOutageHours(String(row.approximate_hours ?? ""));
                          setOutageRevision(row.id);
                        }}
                      >
                        Correct {row.month.slice(0, 7)}
                      </button>
                    </p>
                  ))}
                  <form
                    onSubmit={(event) => void saveOutage(event)}
                    className="mt-4 grid gap-4 sm:grid-cols-2"
                  >
                    <Field id="outage-month" label="Month">
                      <input
                        id="outage-month"
                        type="month"
                        required
                        max={todayIst().slice(0, 7)}
                        value={outageMonth}
                        onChange={(e) => {
                          setOutageMonth(e.target.value);
                          const row = grid.data?.outages.find(
                            (r) => r.month === `${e.target.value}-01`,
                          );
                          setOutageRevision(row?.id ?? null);
                          setOutageHours(String(row?.approximate_hours ?? ""));
                        }}
                        className={inputCls}
                      />
                    </Field>
                    <Field
                      id="outage-hours"
                      label="Approximate hours without supply"
                      hint="Blank means unknown; enter 0 only if you observed no outage."
                    >
                      <input
                        id="outage-hours"
                        type="number"
                        min="0"
                        max="744"
                        step="any"
                        value={outageHours}
                        onChange={(e) => setOutageHours(e.target.value)}
                        className={inputCls}
                      />
                    </Field>
                    <button type="submit" disabled={busy || !consent} className={primaryCls}>
                      {busy ? "Saving…" : "Save outage revision"}
                    </button>
                  </form>
                </div>
              </>
            ) : (
              <p className="text-cw-muted">
                {grid.data?.storage_reason ??
                  "Private grid storage needs reviewed station ownership evidence."}
              </p>
            )}
            {grid.data?.consent_private && (
              <div className="mt-4 border-t border-cw-line pt-5">
                {asking ? (
                  <>
                    <p>
                      Delete every grid and outage revision for this station and withdraw private
                      grid consent? Your bills and station stay.
                    </p>
                    <div className="mt-3 flex flex-wrap gap-3">
                      <button
                        disabled={busy}
                        className={primaryCls}
                        onClick={() => void withdraw()}
                      >
                        Yes, delete grid details
                      </button>
                      <button
                        disabled={busy}
                        className={secondaryCls}
                        onClick={() => setAsking(false)}
                      >
                        Cancel deletion
                      </button>
                    </div>
                  </>
                ) : (
                  <button disabled={busy} className={secondaryCls} onClick={() => setAsking(true)}>
                    Withdraw grid consent and delete details
                  </button>
                )}
              </div>
            )}
          </>
        )}
        {error && (
          <p role="alert" className="text-cw-negative">
            {error}
          </p>
        )}
        {message && <p role="status">{message}</p>}
      </Card>
    </>
  );
}
