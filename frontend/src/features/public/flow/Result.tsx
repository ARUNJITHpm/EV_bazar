import { Link } from "react-router-dom";

import { formatRupeesPrecise, type Paise } from "../../../lib/money";
import { formatUtilisation } from "../../../lib/units";
import { DEMO_REPORT_ID } from "../../report/payload";
import { placeName, type AssessOut } from "./state";

/**
 * The flow's last screen - the shipped teaser, dressed for the new surface.
 *
 * Per design/DECISIONS.md (a): the hero number is the breakeven threshold
 * (arithmetic), never a projected return - no model ran, so there is no
 * band to show and no point estimate to hide one behind. The copper is
 * spent here, on the one figure the screen exists to deliver.
 */

export function Result({ out, onRestart }: { out: AssessOut; onRestart: () => void }) {
  if (out.waitlisted) {
    return (
      <Shell>
        <div className="flex flex-col gap-[18px]">
          <Eyebrow>On the waitlist</Eyebrow>
          <h1 className="max-w-[720px] text-[clamp(28px,4.6vw,44px)] leading-[1.15] font-medium">
            We will not guess at this one.
          </h1>
          <p className="max-w-[720px] text-[clamp(17px,2.2vw,19px)] leading-[1.55] text-cw-muted">
            {out.waitlist_reason}
          </p>
          {out.district && (
            <p className="font-cw-mono text-[14px] text-cw-muted">
              {placeName(out.district, out.state)} · request #{out.requests} for this spot
            </p>
          )}
        </div>
        <Footer onRestart={onRestart} />
      </Shell>
    );
  }

  const t = out.teaser;
  if (!t) return null;

  return (
    <Shell>
      <div className="flex flex-col gap-[18px]">
        <Eyebrow>What this site must do</Eyebrow>
        {t.breakeven_utilisation != null ? (
          <>
            <div className="font-cw-mono text-[clamp(48px,8vw,84px)] leading-none font-medium tracking-[-0.03em] text-cw-accent">
              {formatUtilisation(t.breakeven_utilisation)}
            </div>
            <p className="max-w-[720px] text-[clamp(17px,2.2vw,19px)] leading-[1.55]">
              Utilisation to break even — sell this share of what{" "}
              <span className="font-cw-mono">{t.connectors}</span> ×{" "}
              <span className="font-cw-mono">{t.rated_kw_each}</span> kW chargers could deliver,
              about <span className="font-cw-mono">{Math.round(t.breakeven_kwh_day ?? 0)}</span> kWh
              a day, and the site covers its costs. Whether it will get there is the full
              report&rsquo;s question, answered as a range, never a single number.
            </p>
          </>
        ) : (
          <>
            <h1 className="max-w-[720px] text-[clamp(28px,4.6vw,44px)] leading-[1.15] font-medium text-cw-negative">
              No utilisation breaks even here.
            </h1>
            <p className="max-w-[720px] text-[clamp(17px,2.2vw,19px)] leading-[1.55] text-cw-muted">
              At the assumed selling price against this state&rsquo;s tariff, every unit sold loses
              money. That is an answer, not an error — the notes below say why.
            </p>
          </>
        )}
      </div>

      <div
        className="grid gap-7 border-y border-cw-line py-8"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 200px), 1fr))" }}
      >
        <Figure
          label="Energy tariff"
          value={`${formatRupeesPrecise(t.energy_tariff_paise_per_kwh as Paise)}/kWh`}
          detail={t.tariff_source}
        />
        <Figure
          label="Assumed selling price"
          value={`${formatRupeesPrecise(t.selling_paise_per_kwh as Paise)}/kWh`}
          detail="archetype default"
        />
        <Figure
          label="Sanctioned load priced"
          value={`${Math.round(t.sanctioned_kva)} kVA`}
          detail={placeName(out.district, out.state)}
        />
      </div>

      {out.tier != null && (
        <p className="max-w-[720px] font-cw-mono text-[14px] text-cw-muted">
          Data tier {out.tier} — {out.tier_why}
          {out.boundary_ambiguous && " · near a district border: two tariff regimes."}
        </p>
      )}

      <div className="flex flex-col">
        <h2 className="pb-4 text-[20px] font-medium">What you told us, and what it did</h2>
        {t.taps.map((tap) => (
          <div key={tap.label} className="flex flex-col gap-1 border-t border-cw-line py-4">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <span className="text-[17px]">{tap.label}</span>
              {!tap.provided && (
                <span className="font-cw-mono text-[13px] tracking-[0.08em] text-cw-accent">
                  SKIPPED — DEFAULT APPLIED
                </span>
              )}
            </div>
            <p className="max-w-[640px] text-[15px] text-cw-muted">{tap.effect}</p>
          </div>
        ))}
      </div>

      {t.notes.length > 0 && (
        <div className="flex max-w-[720px] flex-col gap-2">
          {t.notes.map((n) => (
            <p key={n} className="text-[15px] text-cw-muted">
              {n}
            </p>
          ))}
        </div>
      )}

      <Footer onRestart={onRestart} />
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="flex max-w-[900px] flex-col gap-[clamp(32px,5vw,44px)]">{children}</div>;
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-cw-mono text-[13px] tracking-[0.16em] text-cw-muted uppercase">
      {children}
    </div>
  );
}

function Figure({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-cw-muted">{label}</span>
      <span className="font-cw-mono text-[clamp(24px,3.4vw,32px)] font-medium tracking-[-0.02em] tabular-nums">
        {value}
      </span>
      {detail && <span className="font-cw-mono text-[13px] text-cw-muted">{detail}</span>}
    </div>
  );
}

function Footer({ onRestart }: { onRestart: () => void }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-6">
      <p className="max-w-[460px] text-cw-muted">
        The full report shows every factor we checked, including the ones that argued in this
        site&rsquo;s favour.
      </p>
      <div className="flex flex-wrap items-center gap-6">
        <button
          type="button"
          onClick={onRestart}
          className="inline-flex min-h-[56px] items-center text-[17px] text-cw-muted transition-colors duration-200 hover:text-cw-text"
        >
          Assess another site
        </button>
        <Link
          to={`/report/${DEMO_REPORT_ID}`}
          className="inline-flex min-h-[58px] items-center justify-center bg-cw-accent px-7 text-[17px] font-semibold text-cw-ground transition-[filter] duration-200 hover:brightness-107"
        >
          Read a full assessment
        </Link>
      </div>
    </div>
  );
}
