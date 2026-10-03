import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { formatRupees } from "../../lib/money";
import { formatKva, formatKw, kva, kw } from "../../lib/units";
import { AreaGrid } from "./AreaGrid";
import { BillForm, BillImage } from "./BillForm";
import { BillUpload } from "./BillUpload";
import { TrendChart } from "./TrendChart";
import {
  blankBill,
  detailOf,
  monthLabel,
  toBillIn,
  toMonth,
  type DraftConnector,
  type OwnerDraft,
  type PortfolioRow,
  type StationHome,
} from "./state";
import {
  Card,
  LoadingCards,
  ONE,
  Shell,
  WHOLE,
  primaryCls,
  secondaryCls,
  useRequireOwner,
} from "./ui";

const kwhText = (v: number) => `${WHOLE.format(v)} kWh`;
const range = (lo: number, hi: number) =>
  `${WHOLE.format(Math.floor(lo))} to ${WHOLE.format(Math.ceil(hi))} kWh`;
const signed = (v: number) => `${v < 0 ? "−" : "+"}${ONE.format(Math.abs(v))}%`;
const monthOf = (iso: string) => monthLabel(toMonth(iso));

function Num({ children }: { children: React.ReactNode }) {
  return <span className="font-cw-mono tabular-nums">{children}</span>;
}

// --- 1. Last month + forecast --------------------------------------------------

function LastMonth({ home }: { home: StationHome }) {
  const { last_month: last, forecast, station } = home;
  if (!last) return null;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card title={`Last month · ${monthOf(last.period)}`}>
        <span className="font-cw-mono text-[clamp(38px,6vw,60px)] leading-none font-medium tabular-nums">
          {WHOLE.format(last.kwh)} <span className="text-[0.4em] text-cw-muted">kWh</span>
        </span>
        <span className="text-cw-muted">
          Month <Num>{last.month_of_operation}</Num> of operation
        </span>
        {station.possibly_shared && (
          <p className="border-l-2 border-cw-accent pl-4 text-[15px]">
            This meter may include other load, so these figures may be higher than charging alone.
            They are kept out of averages for other stations.
          </p>
        )}
      </Card>
      <Card title={forecast ? `Next month · ${monthOf(forecast.target_month)}` : "Next month"}>
        {forecast ? (
          <>
            <span className="font-cw-mono text-[clamp(30px,5vw,48px)] leading-tight font-medium tabular-nums text-cw-accent">
              {range(forecast.band.p10_kwh, forecast.band.p90_kwh)}
            </span>
            <span className="text-cw-muted">
              Likely range: about eight times in ten it lands inside. Based on{" "}
              <Num>{forecast.readings_used}</Num> month{forecast.readings_used === 1 ? "" : "s"} of
              your bills and similar stations' usual growth (
              <span className="font-cw-mono">{forecast.model_version}</span>).
            </span>
          </>
        ) : (
          <span className="text-cw-muted">No forecast yet.</span>
        )}
      </Card>
    </div>
  );
}

// --- 3. Similar stations ---------------------------------------------------------

function Peers({ home }: { home: StationHome }) {
  const p = home.peer;
  return (
    <Card title="Compared with similar stations">
      {p.available && p.latest_band && p.percentile !== null ? (
        <>
          <p className="text-[22px] leading-snug font-medium">
            Your latest month is ahead of about <Num>{Math.round(p.percentile)}</Num> in 100 similar
            stations.
          </p>
          <p className="text-cw-muted">
            Similar stations delivered {range(p.latest_band.p10_kwh, p.latest_band.p90_kwh)} at this
            age (the middle 80%).
          </p>
          <p className="text-[15px] text-cw-muted">
            Sample: <Num>{p.n}</Num> stations · {p.basis}
          </p>
        </>
      ) : (
        <>
          <p className="text-[22px] leading-snug font-medium">
            {p.reason === "shared_meter"
              ? "Not compared: this meter may include other load."
              : "Not enough similar stations yet."}
          </p>
          <p className="text-cw-muted">{p.message}</p>
          <p className="text-[15px] text-cw-muted">
            Sample: <Num>{p.n}</Num> of <Num>{p.min_required}</Num> needed · {p.basis}
          </p>
        </>
      )}
    </Card>
  );
}

// --- 4. Money on the bill ---------------------------------------------------------

function BillMoney({ home }: { home: StationHome }) {
  const m = home.money;
  if (!m) return null;
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      {m.demand && (
        <Card title="Demand">
          <div className="flex flex-col gap-1">
            <span className="text-cw-muted">Contract</span>
            <Num>
              {m.demand.unit === "kVA"
                ? formatKva(kva(m.demand.contract))
                : formatKw(kw(m.demand.contract))}
            </Num>
            <span className="mt-2 text-cw-muted">Recorded maximum</span>
            <Num>
              {m.demand.unit === "kVA"
                ? formatKva(kva(m.demand.recorded))
                : formatKw(kw(m.demand.recorded))}
            </Num>
            <span className="mt-2 text-cw-muted">
              Peak used <Num>{ONE.format(m.demand.used_share * 100)}%</Num> of contract
            </span>
          </div>
          {m.demand.well_above_peak && (
            <p className="border-l-2 border-cw-accent pl-4">
              Your contract demand is well above your recorded peak. Fixed charges may be reducible
              by applying to your electricity board for a lower contract demand.
            </p>
          )}
        </Card>
      )}
      {m.power_factor && (
        <Card title="Power factor">
          {m.power_factor.power_factor !== null && (
            <span className="font-cw-mono text-[32px] tabular-nums">
              {m.power_factor.power_factor}
            </span>
          )}
          {m.power_factor.amount_paise !== null && m.power_factor.effect && (
            <p>
              {m.power_factor.effect === "penalty" ? "Penalty" : "Incentive"} on this bill:{" "}
              <Num>{formatRupees(m.power_factor.amount_paise)}</Num>
            </p>
          )}
        </Card>
      )}
      {m.time_of_day && (
        <Card title="Time of day">
          <dl className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-2">
            {(
              [
                ["Peak", m.time_of_day.peak_kwh],
                ["Normal", m.time_of_day.normal_kwh],
                ["Off-peak", m.time_of_day.offpeak_kwh],
              ] as const
            )
              .filter(([, v]) => v !== null)
              .map(([label, v]) => (
                <div key={label} className="contents">
                  <dt className="text-cw-muted">{label}</dt>
                  <dd className="text-right">
                    <Num>{kwhText(v ?? 0)}</Num>
                  </dd>
                </div>
              ))}
          </dl>
        </Card>
      )}
    </div>
  );
}

// --- 5. Track record ----------------------------------------------------------------

function TrackRecord({ home }: { home: StationHome }) {
  const rows = home.track_record;
  return (
    <Card title="Forecast track record">
      {rows.length === 0 ? (
        <p className="text-cw-muted">
          No forecast has met its bill yet. The first appears once next month's bill is in.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left">
            <thead className="text-[14px] text-cw-muted">
              <tr>
                <th className="py-2 pr-4 font-normal">Month</th>
                <th className="py-2 pr-4 font-normal">We forecast</th>
                <th className="py-2 pr-4 text-right font-normal">Bill said</th>
                <th className="py-2 pr-4 text-right font-normal">Error</th>
                <th className="py-2 font-normal">Range</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.target_month} className="border-t border-cw-line">
                  <td className="py-3 pr-4">{monthOf(r.target_month)}</td>
                  <td className="py-3 pr-4">
                    <Num>{range(r.band.p10_kwh, r.band.p90_kwh)}</Num>
                  </td>
                  <td className="py-3 pr-4 text-right">
                    <Num>{kwhText(r.actual_kwh)}</Num>
                  </td>
                  <td className="py-3 pr-4 text-right">
                    <Num>{signed(r.error_pct)}</Num>
                  </td>
                  <td className="py-3">
                    <span className={r.inside_range ? "text-cw-positive" : "text-cw-negative"}>
                      {r.inside_range ? "● Inside" : "▲ Missed"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-[14px] text-cw-muted">
        Each forecast is shown as it was made, never recalculated afterwards. Error is the bill
        against the middle of the forecast.
      </p>
    </Card>
  );
}

// --- 7. All stations ------------------------------------------------------------------

type SortKey = "name" | "last_kwh" | "change_pct" | "peer_percentile";

export function Portfolio({ rows, current }: { rows: PortfolioRow[]; current?: number }) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "name", dir: 1 });
  const sorted = useMemo(() => {
    const list = [...rows];
    list.sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      return (av < bv ? -1 : av > bv ? 1 : 0) * sort.dir;
    });
    return list;
  }, [rows, sort]);
  const head = (key: SortKey, label: string, right = false) => (
    <th
      className={`py-2 pr-4 font-normal ${right ? "text-right" : ""}`}
      aria-sort={sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        className="inline-flex min-h-[44px] items-center gap-1.5 text-cw-muted hover:text-cw-text"
        onClick={() => setSort({ key, dir: sort.key === key && sort.dir === 1 ? -1 : 1 })}
      >
        {label}
        <span aria-hidden="true">{sort.key === key ? (sort.dir === 1 ? "▲" : "▼") : "↕"}</span>
      </button>
    </th>
  );
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[600px] text-left">
        <thead className="text-[14px]">
          <tr>
            {head("name", "Station")}
            {head("last_kwh", "Last month", true)}
            {head("change_pct", "Change", true)}
            {head("peer_percentile", "Position vs peers", true)}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr
              key={r.station_id}
              className={`border-t border-cw-line ${r.station_id === current ? "bg-cw-surface-2" : ""}`}
            >
              <td className="py-3 pr-4">
                <Link
                  to={`/owner/station/${r.station_id}`}
                  className="inline-flex min-h-[44px] flex-col justify-center text-cw-text"
                >
                  <span>{r.name}</span>
                  {r.district && <span className="text-[14px] text-cw-muted">{r.district}</span>}
                </Link>
              </td>
              <td className="py-3 pr-4 text-right">
                {r.last_kwh === null ? (
                  <span className="text-cw-muted">No bill yet</span>
                ) : (
                  <>
                    <Num>{kwhText(r.last_kwh)}</Num>
                    {r.last_period && (
                      <span className="block text-[13px] text-cw-muted">
                        {monthOf(r.last_period)}
                      </span>
                    )}
                  </>
                )}
              </td>
              <td className="py-3 pr-4 text-right">
                {r.change_pct === null ? "–" : <Num>{signed(r.change_pct)}</Num>}
              </td>
              <td className="py-3 pr-4 text-right">
                {r.peer_percentile !== null ? (
                  <>
                    <Num>{Math.round(r.peer_percentile)}</Num> / 100
                    <span className="block text-[13px] text-cw-muted">
                      of <Num>{r.peer_n}</Num> stations
                    </span>
                  </>
                ) : (
                  <span className="text-cw-muted">
                    {r.possibly_shared ? "Shared meter" : "Not enough peers"}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function usePortfolio() {
  return useQuery({
    queryKey: ["owner-stations"],
    queryFn: async () => (await api.GET("/api/internal/owner/stations")).data ?? [],
  });
}

// --- pages ----------------------------------------------------------------------------

/** /owner/home: a single station goes straight to its page; several show the table. */
export function OwnerHome() {
  const me = useRequireOwner();
  const stations = usePortfolio();
  const navigate = useNavigate();
  const rows = stations.data;
  useEffect(() => {
    if (!rows) return;
    if (rows.length === 0) navigate("/owner/bill", { replace: true });
    else if (rows.length === 1 && rows[0]) {
      navigate(`/owner/station/${rows[0].station_id}`, { replace: true });
    }
  }, [rows, navigate]);
  return (
    <Shell>
      <div className="flex max-w-[1000px] flex-col gap-8">
        <h1 className="text-[clamp(30px,4.6vw,48px)] leading-tight font-medium">Your stations</h1>
        {me.isPending || stations.isPending ? (
          <LoadingCards label="Loading your stations…" />
        ) : rows && rows.length > 1 ? (
          <>
            <Card>
              <Portfolio rows={rows} />
            </Card>
            <div>
              <Link to="/owner/bill" className={secondaryCls}>
                Add another station
              </Link>
            </div>
          </>
        ) : null}
      </div>
    </Shell>
  );
}

export function StationPage() {
  const { id } = useParams();
  const me = useRequireOwner();
  const stations = usePortfolio();
  const home = useQuery({
    queryKey: ["owner-home", id],
    enabled: !!id && !!me.data,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/internal/owner/stations/{station_id}/home", {
        params: { path: { station_id: Number(id) } },
      });
      if (!data) throw new Error(String(response.status));
      return data;
    },
  });
  const h = home.data;
  return (
    <Shell>
      <div className="flex max-w-[1100px] flex-col gap-8">
        {home.isPending ? (
          <LoadingCards label="Loading your station…" cards={3} />
        ) : !h ? (
          <p role="alert" className="text-cw-negative">
            We could not open that station.{" "}
            <Link to="/owner/home" className="underline">
              Back to your stations
            </Link>
          </p>
        ) : (
          <>
            <header className="flex flex-col gap-1">
              <h1 className="text-[clamp(30px,4.6vw,48px)] leading-tight font-medium">
                {h.station.name}
              </h1>
              <p className="text-cw-muted">
                {[h.station.district, h.station.state].filter(Boolean).join(", ")}
                {h.station.district ? " · " : ""}
                Live since {monthLabel(toMonth(h.station.went_live))} ·{" "}
                <Num>{h.station.connectors.length}</Num> connector
                {h.station.connectors.length === 1 ? "" : "s"}
              </p>
            </header>
            <LastMonth home={h} />
            <AreaGrid key={h.station.id} stationId={h.station.id} />
            <Card title="Trend">
              <TrendChart home={h} />
            </Card>
            <Peers home={h} />
            <BillMoney home={h} />
            <TrackRecord home={h} />
            {stations.data && stations.data.length > 1 && (
              <Card title="All your stations">
                <Portfolio rows={stations.data} current={h.station.id} />
              </Card>
            )}
            <DeleteData />
          </>
        )}
      </div>
      {id && (
        <div className="fixed inset-x-0 bottom-0 z-10 border-t border-cw-line bg-cw-ground/95 px-[clamp(24px,7vw,112px)] py-3 backdrop-blur">
          <Link to={`/owner/station/${id}/bill`} className={`${primaryCls} w-full sm:w-auto`}>
            Upload next month's bill
          </Link>
        </div>
      )}
    </Shell>
  );
}

/** Erase the account and everything in it. Two taps, no browser dialog. */
function DeleteData() {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const client = useQueryClient();
  const erase = async () => {
    setBusy(true);
    setError(null);
    const { response } = await api.DELETE("/api/internal/owner/me");
    setBusy(false);
    if (!response.ok) return setError("We could not delete your data. Try again in a moment.");
    client.clear();
    navigate("/owner", { replace: true });
  };
  if (!asking) {
    return (
      <button type="button" className={secondaryCls} onClick={() => setAsking(true)}>
        Delete my data
      </button>
    );
  }
  return (
    <Card title="Delete my data">
      <p>
        This erases your phone number, every station, bill, bill image and forecast on your account,
        including all private grid and outage revisions and their consent records. It cannot be
        undone.
      </p>
      {error && (
        <p role="alert" className="text-cw-negative">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <button type="button" className={primaryCls} disabled={busy} onClick={() => void erase()}>
          {busy ? "Deleting…" : "Yes, delete everything"}
        </button>
        <button type="button" className={secondaryCls} onClick={() => setAsking(false)}>
          Cancel
        </button>
      </div>
    </Card>
  );
}

/** A returning owner: upload the next bill, check it, save it. */
export function BillPage() {
  const { id } = useParams();
  const me = useRequireOwner();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [bill, setBill] = useState<OwnerDraft["bill"]>(blankBill);
  const [stage, setStage] = useState<"upload" | "form">("upload");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const home = useQuery({
    queryKey: ["owner-home", id],
    enabled: !!id && !!me.data,
    queryFn: async () =>
      (
        await api.GET("/api/internal/owner/stations/{station_id}/home", {
          params: { path: { station_id: Number(id) } },
        })
      ).data ?? null,
  });
  const connectors: DraftConnector[] = (home.data?.station.connectors ?? []).map((c) => ({
    standard: c.standard as DraftConnector["standard"],
    power_kw: c.power_kw,
    count: 1,
  }));

  const save = async () => {
    const body = toBillIn(bill);
    if (!body || !id) return;
    setBusy(true);
    setError(null);
    const { data, error: err } = await api.POST("/api/internal/owner/stations/{station_id}/bills", {
      params: { path: { station_id: Number(id) } },
      body: { bill: body },
    });
    setBusy(false);
    if (!data) return setError(detailOf(err, "We could not save that bill. Check the figures."));
    await client.invalidateQueries({ queryKey: ["owner-home", id] });
    await client.invalidateQueries({ queryKey: ["owner-stations"] });
    navigate(`/owner/station/${id}`, { replace: true });
  };

  return (
    <Shell back={() => navigate(`/owner/station/${id}`)}>
      <div className="flex max-w-[1000px] flex-col gap-8">
        <h1 className="text-[clamp(30px,4.6vw,48px)] leading-tight font-medium">
          {stage === "upload" ? "Upload the next bill." : "Check the figures against your bill."}
        </h1>
        {stage === "upload" ? (
          <BillUpload
            onUploaded={(u) => {
              setBill({ ...bill, imageId: u.imageId, imageType: u.contentType });
              setStage("form");
            }}
            onTypeInstead={() => setStage("form")}
          />
        ) : (
          <>
            <div className={bill.imageId ? "grid gap-8 lg:grid-cols-2" : ""}>
              <BillImage id={bill.imageId} type={bill.imageType} />
              <BillForm
                bill={bill}
                set={(p) => setBill({ ...bill, ...p })}
                connectors={connectors}
                error={error}
              />
            </div>
            <div className="flex justify-end">
              <button
                type="button"
                className={primaryCls}
                disabled={busy || !toBillIn(bill) || !bill.confirmed}
                onClick={() => void save()}
              >
                {busy ? "Saving…" : "Save this bill"}
              </button>
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}
