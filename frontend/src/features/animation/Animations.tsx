import { Link } from "react-router-dom";

import { RouteToCharge } from "./RouteToCharge";
import { SiteAssessed } from "./SiteAssessed";
import { SourcesToReport } from "./SourcesToReport";
import { TOTAL_CHECKS } from "./data";

/**
 * /animation - a staging surface for the three hero animations.
 *
 * Deliberately NOT wired into Landing.tsx. These are candidates: they are
 * meant to be watched side by side, at real size, on the real ground, before
 * one of them displaces <HeroMap /> or lands in a section. Moving one across
 * is an import and a JSX line, and the note under each says where it goes.
 *
 * Not linked from anywhere either. This is a review surface, not a page, and
 * a public route nobody navigates to costs nothing; a nav item that leads to
 * a workbench costs credibility.
 *
 * Every figure on this page is illustrative and bracketed - see data.ts. The
 * banner is not decoration; a screenshot of this route will outlive the
 * conversation that produced it, and it must not read as a real assessment.
 */

const PAD_X = "px-[clamp(24px,7vw,112px)]";

export function Animations() {
  return (
    <div className="cw-surface-root min-h-dvh bg-cw-ground font-cw-sans text-[17px] leading-[1.6] text-cw-text antialiased">
      <header
        className={`flex flex-wrap items-center justify-between gap-6 border-b border-cw-line ${PAD_X} py-[26px]`}
      >
        <span className="font-cw-mono text-[clamp(18px,1.6vw,22px)] font-medium tracking-[0.08em] uppercase">
          Chargeworthy · Motion
        </span>
        <Link
          to="/"
          className="inline-flex min-h-[44px] items-center text-cw-muted transition-colors duration-200 hover:text-cw-text"
        >
          Back to the landing page
        </Link>
      </header>

      <div
        className={`border-b border-cw-accent/40 bg-cw-accent/5 ${PAD_X} py-3.5 font-cw-mono text-[12px] tracking-[0.08em] text-cw-accent`}
      >
        Review surface. Every figure below is illustrative and bracketed — no value here is a
        measurement.
      </div>

      <main>
        <Panel
          n="A"
          title="Route to charge"
          where="The landing hero, in place of or beside <HeroMap />. Carries no Mapbox payload, so it needs no lazy boundary and costs nothing on first paint."
          note="Candidates are compared, one is chosen, and only then does a vehicle reach it and charge. The catchment is the consequence of the choice, not the opening claim. Pure CSS — no script."
        >
          <RouteToCharge />
        </Panel>

        <Panel
          n="B"
          title="The site, assessed"
          where="The 'What a full assessment checks' section, or the report showcase."
          note={`All ${TOTAL_CHECKS} factors, grouped 9 / 7 / 8 / 6 / 4, walked one category at a time. Rows arrive already correct — never flickering through alternatives first. The verdict lands last.`}
        >
          <SiteAssessed />
        </Panel>

        <Panel
          n="C"
          title="Sources in, report out"
          where="A full-width band above the closing call to action."
          note="Public sources connect, the checks resolve against them, a report comes out on the report's own paper. Copper falls on one line only: the factor nobody could source."
        >
          <SourcesToReport />
        </Panel>
      </main>

      <footer
        className={`flex flex-wrap items-start justify-between gap-8 border-t border-cw-line ${PAD_X} pt-10 pb-14 text-cw-muted`}
      >
        <p className="max-w-[54ch]">
          All three honour <span className="font-cw-mono text-[15px]">prefers-reduced-motion</span>:
          the finished state renders immediately and nothing loops. B and C also stop when they
          scroll out of view or the tab is backgrounded.
        </p>
        <Link
          to="/report/KL-TVM-DEMO-001"
          className="inline-flex min-h-[44px] items-center transition-colors duration-200 hover:text-cw-text"
        >
          The document these describe
        </Link>
      </footer>
    </div>
  );
}

function Panel({
  n,
  title,
  where,
  note,
  children,
}: {
  n: string;
  title: string;
  where: string;
  note: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`border-b border-cw-line ${PAD_X} py-[clamp(48px,7vw,88px)]`}>
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="font-cw-mono text-[13px] tracking-[0.16em] text-cw-slate uppercase">
          {n}
        </span>
        <h2 className="text-[clamp(26px,3.4vw,36px)] leading-[1.12] font-medium">{title}</h2>
      </div>
      <div className="mt-4 grid gap-x-10 gap-y-2 md:grid-cols-2">
        <p className="max-w-[58ch] text-cw-muted">{note}</p>
        <p className="max-w-[58ch] font-cw-mono text-[13px] leading-[1.65] text-cw-muted">
          {where}
        </p>
      </div>
      <div className="mt-[clamp(32px,4vw,56px)]">{children}</div>
    </section>
  );
}

export default Animations;
