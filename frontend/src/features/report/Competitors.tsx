import { formatKw, kw } from "../../lib/units";
import type { ReportPayload } from "./payload";
import { Figure, NUM, Note, Section, TD, TH, Table } from "./parts";

/**
 * 07 — the nearest stations by distance. Inventory and specification only:
 * whether those stations are busy is a different fact, and it joins the
 * table when the poller has observed them, never before.
 */

function km(m: number): string {
  return m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1)} km`;
}

export function Competitors({ payload }: { payload: ReportPayload }) {
  const c = payload.competitors;
  return (
    <Section num="07" title="Competitors" heading="Who else is already nearby." id="competitors">
      <div className="mb-5 flex flex-wrap gap-x-10 gap-y-5">
        <Figure label="Stations within 3 km" value={String(c.within_3km)} small />
        {c.within_5km != null && (
          <Figure label="Stations within 5 km" value={String(c.within_5km)} small />
        )}
        {c.dc_fast_within_3km != null && (
          <Figure label="Fast chargers within 3 km" value={String(c.dc_fast_within_3km)} small />
        )}
      </div>
      {c.nearest.length === 0 ? (
        <Note>No charging station is recorded within 5 km of this site.</Note>
      ) : (
        <Table minWidth="34rem">
          <thead>
            <tr>
              <th className={`${TH} ${NUM}`}>Distance</th>
              <th className={TH}>Station</th>
              <th className={TH}>Operator</th>
              <th className={`${TH} ${NUM}`}>Max power</th>
              <th className={`${TH} ${NUM}`}>Points</th>
              <th className={TH}>Observed use</th>
            </tr>
          </thead>
          <tbody>
            {c.nearest.map((r) => (
              <tr key={`${r.name}-${r.distance_m}`}>
                <td className={`${TD} ${NUM}`}>{km(r.distance_m)}</td>
                <td className={TD}>{r.name}</td>
                <td className={TD}>{r.operator}</td>
                <td className={`${TD} ${NUM}`}>{formatKw(kw(r.max_power_kw))}</td>
                <td className={`${TD} ${NUM}`}>{r.points}</td>
                <td className={`${TD} text-[15px] text-cw-paper-muted`}>not yet observed</td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <Note className="mt-3">Source: {c.source}.</Note>
    </Section>
  );
}
