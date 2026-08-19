import { formatRupeesCompact, formatRupeesPrecise } from "../../lib/money";
import { formatKva, formatUtilisation, kva } from "../../lib/units";
import type { ReportPayload, Scenario } from "./payload";

/**
 * Section 4 — three scenarios, one engine. Every number here is rendered from
 * the payload the ROI engine produced (AGENTS.md rule 1); this component does
 * no arithmetic beyond formatting. The three India-specific levers the engine
 * models (OVERVIEW.md §3) each get one quiet line: the fleet anchor, the
 * sanctioned-load recommendation, and selling-price sensitivity.
 */
export function Financials({ payload }: { payload: ReportPayload }) {
  const f = payload.financials;
  return (
    <section data-report-section="financials" className="border-b border-rule py-8">
      <h2 className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
        4 · Financials
      </h2>
      <p className="num mt-2 text-[13px] text-ink-muted">
        capex {formatRupeesCompact(f.capex_paise)} · selling price{" "}
        {formatRupeesPrecise(f.selling_price_paise_kwh)}/kWh · energy tariff{" "}
        {formatRupeesPrecise(f.energy_tariff_paise_kwh)}/kWh
      </p>

      <div className="overflow-x-auto">
        <table className="mt-4 w-full min-w-[34rem] border-t border-rule text-[13px]">
          <thead>
            <tr className="border-b border-rule text-left font-ui text-[11px] tracking-[0.08em] text-ink-muted uppercase">
              <th className="py-1.5 pr-4 font-bold">Scenario</th>
              <th className="py-1.5 pr-4 text-right font-bold">Utilisation</th>
              <th className="py-1.5 pr-4 text-right font-bold">kWh / year</th>
              <th className="py-1.5 pr-4 text-right font-bold">NPV, 10 yr</th>
              <th className="py-1.5 pr-4 text-right font-bold">IRR</th>
              <th className="py-1.5 text-right font-bold">Payback</th>
            </tr>
          </thead>
          <tbody>
            {f.scenarios.map((s) => (
              <ScenarioRow key={s.label} s={s} />
            ))}
          </tbody>
        </table>
      </div>

      <dl className="mt-6 max-w-[34rem] border-t border-rule">
        <div className="border-b border-rule py-2">
          <dt className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
            Fleet anchor scenario
          </dt>
          <dd className="mt-1 text-[0.9375rem] text-ink-muted">
            With a take-or-pay contract of{" "}
            <span className="num text-ink">
              {f.anchor_note.kwh_year.toLocaleString("en-IN")} kWh/yr
            </span>{" "}
            (Technopark campus or a 3W fleet): NPV{" "}
            <span className="num text-ink">{formatRupeesCompact(f.anchor_note.npv_paise)}</span>,
            IRR <span className="num text-ink">{f.anchor_note.irr_pct}%</span>. The anchor de-risks
            NPV and IRR; breakeven is unchanged by design — it answers how busy retail must be.
          </dd>
        </div>
        <div className="border-b border-rule py-2">
          <dt className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
            Sanctioned load
          </dt>
          <dd className="mt-1 text-[0.9375rem] text-ink-muted">
            Full load needs{" "}
            <span className="num text-ink">{formatKva(kva(f.sanctioned_load.full_kva))}</span>.{" "}
            {f.sanctioned_load.recommended_label} charging runs on{" "}
            <span className="num text-ink">
              {formatKva(kva(f.sanctioned_load.recommended_kva))}
            </span>{" "}
            and saves{" "}
            <span className="num text-ink">
              {formatRupeesCompact(f.sanctioned_load.saving_paise_year)}/yr
            </span>{" "}
            in demand charges — recommended. Battery-buffered reaches{" "}
            <span className="num text-ink">{formatKva(kva(f.sanctioned_load.buffered_kva))}</span>{" "}
            if the connection is the constraint.
          </dd>
        </div>
        <div className="border-b border-rule py-2">
          <dt className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
            Selling-price sensitivity
          </dt>
          <dd className="num mt-1 text-[13px] text-ink-muted">
            {f.price_sensitivity.map((p, i) => (
              <span key={p.price_paise_kwh}>
                {i > 0 && " · "}
                {formatRupeesPrecise(p.price_paise_kwh)}/kWh →{" "}
                <span className="text-ink">{formatUtilisation(p.breakeven_utilisation)}</span>
              </span>
            ))}
          </dd>
        </div>
      </dl>
    </section>
  );
}

function ScenarioRow({ s }: { s: Scenario }) {
  return (
    <tr className="border-b border-rule">
      <td className="py-1.5 pr-4 font-text">{s.label}</td>
      <td className="py-1.5 pr-4 text-right">{formatUtilisation(s.utilisation)}</td>
      <td className="py-1.5 pr-4 text-right">{s.kwh_year.toLocaleString("en-IN")}</td>
      <td className="py-1.5 pr-4 text-right">{formatRupeesCompact(s.npv_paise)}</td>
      <td className="py-1.5 pr-4 text-right">{s.irr_pct === null ? "—" : `${s.irr_pct}%`}</td>
      <td className="py-1.5 text-right">
        {s.payback_years === null ? "beyond horizon" : `${s.payback_years} yr`}
      </td>
    </tr>
  );
}
