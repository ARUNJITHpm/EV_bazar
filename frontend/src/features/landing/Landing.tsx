import { Link } from "react-router-dom";

/**
 * Public landing. Deliberately quiet: the product's claim is that its
 * numbers are auditable, so the page reads like a technical document, not a
 * SaaS hero (STACK.md §7).
 */
export function Landing() {
  return (
    <div className="mx-auto max-w-[52rem] px-6 py-12">
      <header className="flex items-baseline justify-between border-b-2 border-rule-strong pb-3">
        <p className="font-ui text-[13px] font-bold tracking-[0.08em] uppercase">
          EV Site Intelligence
        </p>
        <p className="font-data text-[11px] text-ink-faint">India · national schema</p>
      </header>

      <h1 className="mt-8 max-w-[34rem] text-[1.125rem] leading-tight">
        Drop a pin. Find out what utilisation this EV charging site needs to break even — and
        whether it will get there.
      </h1>

      <h2 className="mt-8 mb-3 border-b border-rule pb-2 font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
        Build status
      </h2>
      <dl className="border-t border-rule">
        <Row label="Part 1 · Pin → district resolution" value="live, verified" />
        <Row label="Part 2 · Site context (OSM roads · POIs)" value="scraping live" />
        <Row label="Part 3 · Tariffs + ROI engine" value="built" />
        <Row label="Part 4.1 · VAHAN registrations" value="scheduled scrape" />
        <Row label="Part 5 · Report served from stored payload" value="demo live" />
        <Row label="Part G.2 · Pin-drop breakeven teaser" value="live" />
        <Row label="Part 0.1 · Status poller" value="not yet running" warn />
      </dl>

      <p className="mt-6 max-w-[34rem] text-sm text-ink-muted">
        The poller is the one asset that cannot be acquired retroactively. Every day it is not
        running is a day permanently lost.
      </p>

      <p className="mt-8">
        <Link to="/assess" className="font-ui text-[13px] underline underline-offset-4">
          Drop a pin — free breakeven check →
        </Link>
      </p>
      <p className="mt-2">
        <Link
          to="/report/KL-TVM-DEMO-001"
          className="font-ui text-[13px] underline underline-offset-4"
        >
          Demonstration report — Kazhakkoottam, NH-66 →
        </Link>
      </p>
      <p className="mt-2">
        <Link to="/console" className="font-ui text-[13px] underline underline-offset-4">
          Operations console →
        </Link>
      </p>
    </div>
  );
}

function Row({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="flex justify-between gap-4 border-b border-rule py-1.5">
      <dt className="font-ui text-[13px] text-ink-muted">{label}</dt>
      <dd
        className={
          warn
            ? "bg-warn-ground px-1 font-data text-[13px] text-warn"
            : "font-data text-[13px] tabular-nums"
        }
      >
        {value}
      </dd>
    </div>
  );
}
