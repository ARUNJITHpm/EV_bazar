import { lazy, Suspense, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { DEMO_REPORT_ID } from "../report/payload";
import { ReportPaper } from "./ReportPaper";
import { useReveal, useScrollProgress } from "./reveal";

/**
 * The Chargeworthy landing - design/ implemented per design/DECISIONS.md.
 *
 * Copy comes from design/brand/copy-pass.md, the corrected pass, verbatim -
 * including the definition of "operator" in the hero and "Detailed enough
 * for your bank to lend against" (the claim describes the document, not the
 * bank's behaviour).
 *
 * Numbers the repo does not have render BRACKETED - [340] sites, [38%]
 * advised against, [XX%] accuracy - per IMPLEMENT.md's working rule: leave
 * it visibly bracketed rather than inventing one. Partner and hardware
 * names are not shipped at all until written permission exists; bracketed
 * slots hold their place. Un-bracketing any of these is a human step with
 * evidence, never an edit.
 */

const HeroMap = lazy(() => import("./HeroMap"));

const FACTORS = [
  "Road class",
  "Distance from main road",
  "Carriageway direction served",
  "Sub-road access",
  "Median or divider",
  "Sight line",
  "Turning radius",
  "Entry and exit width",
  "Frontage width",
  "AADT traffic count",
  "Dominant flow direction",
  "Peak hour timing",
  "EV registrations",
  "Registration mix",
  "Fleet operators within 10 km",
  "Distance to nearest city",
  "Tariff order",
  "Demand charges",
  "Sanctioned load",
  "Transformer distance",
  "Transformer spare capacity",
  "Grid outage hours",
  "New connection cost",
  "State subsidy applicability",
  "Plot area",
  "Parking bays",
  "Canopy feasibility",
  "Amenities within walking distance",
  "Mobile network coverage",
  "Night lighting",
  "Land or lease cost",
  "Competitor distance",
  "Competitor density at 3 / 5 / 10 km",
  "Announced stations",
];

function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <div className="font-cw-mono text-[13px] tracking-[0.16em] text-cw-muted uppercase">
      {children}
    </div>
  );
}

/** The pin-shaped input + copper CTA. The typed text rides to the flow's
 *  search box; the pin the customer finally places is what gets assessed. */
function LocationCta({ id }: { id: string }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    navigate("/assess", { state: { q } });
  }

  return (
    <form onSubmit={submit} className="flex max-w-[720px] flex-wrap gap-3">
      <label htmlFor={id} className="sr-only">
        Site location
      </label>
      <div className="flex min-h-[58px] min-w-[260px] flex-grow items-center gap-3 border border-cw-line bg-cw-surface px-5 text-cw-muted">
        <PinIcon />
        <input
          id={id}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Drop a pin, or type the location"
          autoComplete="off"
          className="min-w-0 flex-grow bg-transparent text-[17px] text-cw-text outline-none placeholder:text-cw-muted"
        />
      </div>
      <button
        type="submit"
        className="inline-flex min-h-[58px] items-center justify-center bg-cw-accent px-7 text-[17px] font-semibold text-cw-ground transition-[filter] duration-200 hover:brightness-107"
      >
        See the verdict
      </button>
    </form>
  );
}

function PinIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M10 18s6-5.2 6-9.4A6 6 0 0 0 4 8.6C4 12.8 10 18 10 18z" />
      <circle cx="10" cy="8.6" r="2.1" />
    </svg>
  );
}

const PAD_X = "px-[clamp(24px,7vw,112px)]";
const SECTION = `${PAD_X} py-[clamp(72px,10vw,128px)]`;

function Header() {
  return (
    <header
      className={`flex items-center justify-between gap-8 border-b border-cw-line ${PAD_X} py-[26px]`}
    >
      <span className="font-cw-mono text-[17px] font-medium tracking-[0.09em] uppercase">
        Chargeworthy
      </span>
      <Link
        to={`/report/${DEMO_REPORT_ID}`}
        className="inline-flex min-h-[44px] items-center text-cw-muted transition-colors duration-200 hover:text-cw-text"
      >
        Sample report
      </Link>
    </header>
  );
}

function Hero() {
  const ref = useReveal<HTMLElement>(60);
  return (
    <section ref={ref}>
      <div
        className={`grid items-center gap-[clamp(40px,6vw,80px)] ${PAD_X} py-[clamp(72px,10vw,128px)]`}
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))" }}
      >
        <div className="flex max-w-[560px] flex-col gap-[26px]">
          <div data-reveal="0">
            <Eyebrow>Right site. Right operator.</Eyebrow>
          </div>
          <h1
            data-reveal="1"
            className="text-[clamp(34px,5.2vw,60px)] leading-[1.15] font-semibold tracking-[-0.025em] text-pretty"
          >
            Will your land pay for a charger?
          </h1>
          <p data-reveal="2" className="text-[18px] text-cw-muted">
            We assess the location, set the return against what a fixed deposit would pay on the
            same money, and tell you plainly — including when the answer is no.
          </p>
          <p data-reveal="3" className="text-cw-muted">
            Charging stations are built and run by operators. We are not one of them, and we hold no
            stake in any of them.
          </p>
          <div data-reveal="4">
            <LocationCta id="hero-location" />
          </div>
        </div>

        <div data-reveal="5">
          <Suspense
            fallback={
              <div className="h-[clamp(260px,42vw,452px)] w-full border border-cw-line bg-cw-surface" />
            }
          >
            <HeroMap />
          </Suspense>
        </div>
      </div>

      <div
        className={`flex flex-wrap gap-[clamp(16px,4vw,40px)] border-t border-cw-line ${PAD_X} pt-[26px] pb-[30px]`}
      >
        {/* Bracketed until the real ledger can publish them - see the module
            docstring. Never animated: a count-up on a placeholder would
            dress a gap as a fact. */}
        <span className="font-cw-mono text-[15px] tracking-[0.03em] text-cw-muted">
          [1,000+] station owners we work with
        </span>
        <span className="font-cw-mono text-[15px] tracking-[0.03em] text-cw-muted">
          [340] sites assessed in 2025
        </span>
        <span className="font-cw-mono text-[15px] tracking-[0.03em] text-cw-muted">
          [38%] advised against
        </span>
      </div>
    </section>
  );
}

const STEPS: [string, string, ReactNode][] = [
  [
    "01",
    "Assess the site",
    <>
      We survey the location against <span className="font-cw-mono">34</span> fixed criteria and
      model what it would earn. If it does not clear the bar, that is where it ends.
    </>,
  ],
  [
    "02",
    "Match the operator",
    "A highway site and an apartment basement need different operators. We rank our partners on charger type, revenue share and how fast they reach you for a fault, then name one.",
  ],
  [
    "03",
    "Install and run",
    "The operator supplies the charger, the installation and the management software. We stay with you through commissioning.",
  ],
];

function HowItWorks() {
  const ref = useReveal<HTMLElement>(60);
  return (
    <section ref={ref} className={SECTION}>
      <div className="flex flex-col gap-[clamp(40px,6vw,64px)]">
        <div className="flex max-w-[620px] flex-col gap-[18px]">
          <div data-reveal="0">
            <Eyebrow>How it works</Eyebrow>
          </div>
          <h2 data-reveal="1" className="text-[clamp(26px,3.4vw,34px)] leading-[1.15] font-medium">
            Three steps, and we stop at any of them.
          </h2>
        </div>
        <div
          className="grid"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))" }}
        >
          {STEPS.map(([n, title, body], i) => (
            <div
              key={n}
              data-reveal={i + 2}
              className={`flex flex-col gap-4 pr-[clamp(24px,4vw,56px)] ${
                i === 0 ? "" : "border-l border-cw-line pl-[clamp(24px,4vw,56px)]"
              }`}
            >
              <span className="font-cw-mono text-[15px] tracking-[0.08em] text-cw-slate">{n}</span>
              <h3 className="text-[22px] font-medium">{title}</h3>
              <p className="text-cw-muted">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function WhatWeCheck() {
  const ref = useReveal<HTMLElement>(30);
  return (
    <section ref={ref} className={SECTION}>
      <div className="flex flex-col gap-[clamp(36px,5vw,52px)]">
        <div className="flex max-w-[660px] flex-col gap-[18px]">
          <div data-reveal="0">
            <Eyebrow>What a full assessment checks</Eyebrow>
          </div>
          <h2 data-reveal="1" className="text-[clamp(26px,3.4vw,34px)] leading-[1.15] font-medium">
            Nothing here is a guess.
          </h2>
          <p data-reveal="2" className="max-w-[580px] text-cw-muted">
            Each one is measured or sourced, and the unverified ones are marked, not buried —
            including the factors that argue in the site&rsquo;s favour.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          {FACTORS.map((f, i) => (
            <span
              key={f}
              data-reveal={i + 3}
              className="border border-cw-line bg-cw-surface px-[17px] py-[11px] text-[16px]"
            >
              {f}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function Card({
  children,
  span,
  reveal,
}: {
  children: ReactNode;
  span: 4 | 8 | 12;
  reveal: number;
}) {
  const cols = {
    4: "min-[900px]:col-span-4",
    8: "min-[900px]:col-span-8",
    12: "min-[900px]:col-span-12",
  };
  return (
    <div
      data-reveal={reveal}
      className={`min-w-0 border border-cw-line bg-cw-surface ${cols[span]}`}
    >
      {children}
    </div>
  );
}

function Cards() {
  const ref = useReveal<HTMLElement>(50);
  return (
    <section ref={ref} className={SECTION}>
      <div className="flex flex-col gap-[clamp(32px,4vw,48px)]">
        <div className="flex max-w-[660px] flex-col gap-[18px]">
          <div data-reveal="0">
            <Eyebrow>Why trust the answer</Eyebrow>
          </div>
          <h2 data-reveal="1" className="text-[clamp(26px,3.4vw,34px)] leading-[1.15] font-medium">
            We have no stake in you building.
          </h2>
          <p data-reveal="2" className="max-w-[620px] text-[18px] text-cw-muted">
            Chargeworthy is not a charge point operator. We own no stations, take no margin on
            hardware, and charge the same assessment fee whether the answer is yes or no.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-5 min-[900px]:grid-cols-12">
          <Card span={8} reveal={3}>
            <div className="flex flex-col justify-center gap-6 p-[clamp(28px,4vw,48px)]">
              <h3 className="text-[26px] font-medium">We tell people not to build.</h3>
              <div className="font-cw-mono text-[clamp(56px,8vw,96px)] leading-none font-medium tracking-[-0.03em] text-cw-accent">
                [38%]
              </div>
              <p className="max-w-[540px] text-[18px] text-cw-muted">
                Of <span className="font-cw-mono">[340]</span> sites assessed in{" "}
                <span className="font-cw-mono">2025</span>, we advised{" "}
                <span className="font-cw-mono">[129]</span> owners to walk away. We were paid the
                same either way.
              </p>
            </div>
          </Card>

          <Card span={4} reveal={4}>
            <div className="flex h-full flex-col justify-center gap-[18px] p-[clamp(24px,3vw,40px)]">
              <Eyebrow>Prediction accuracy</Eyebrow>
              <div className="font-cw-mono text-[clamp(38px,5vw,56px)] leading-none font-medium">
                [XX%]
              </div>
              <p className="text-cw-muted">
                Of the sites we cleared that went on to be built, this share landed inside our
                projected utilisation band after twelve months.
              </p>
            </div>
          </Card>

          <Card span={4} reveal={5}>
            <div className="flex h-full flex-col gap-[22px] p-[clamp(24px,3vw,40px)]">
              <h3 className="text-[20px] leading-[1.35] font-medium">
                Matched to the right operator, not our own.
              </h3>
              <p className="text-cw-muted">
                Partner operators appear here named, with each one&rsquo;s written permission —
                never before.
              </p>
            </div>
          </Card>

          <Card span={4} reveal={6}>
            <div className="flex h-full flex-col gap-[22px] p-[clamp(24px,3vw,40px)]">
              <h3 className="text-[20px] leading-[1.35] font-medium">
                Independent across hardware.
              </h3>
              <p className="text-cw-muted">
                No stake in any charger brand, no margin on hardware. Makers appear named on the
                same terms as operators.
              </p>
            </div>
          </Card>

          <Card span={4} reveal={7}>
            <div className="flex h-full flex-col justify-center gap-[18px] p-[clamp(24px,3vw,40px)]">
              <div className="font-cw-mono text-[clamp(38px,5vw,56px)] leading-none font-medium">
                [1,000+]
              </div>
              <p className="text-cw-muted">
                Station owners in our network across India, and the reason our operator comparisons
                are grounded in what actually happens after commissioning.
              </p>
            </div>
          </Card>

          <Card span={12} reveal={8}>
            <div
              className="grid items-center gap-[clamp(28px,4vw,56px)] p-[clamp(28px,4vw,48px)]"
              style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))" }}
            >
              <div className="flex flex-col gap-[18px]">
                <Eyebrow>See a full assessment</Eyebrow>
                <h3 className="text-[24px] font-medium">
                  Every site gets the same document, whatever the verdict.
                </h3>
                <p className="text-cw-muted">
                  Read a real one end to end before you order your own.
                </p>
                <Link
                  to={`/report/${DEMO_REPORT_ID}`}
                  className="text-cw-muted underline underline-offset-4 transition-colors duration-200 hover:text-cw-text"
                >
                  The demonstration report →
                </Link>
              </div>
              <Link
                to={`/report/${DEMO_REPORT_ID}`}
                className="block max-h-[236px] overflow-hidden"
              >
                <ReportPaper compact />
              </Link>
            </div>
          </Card>
        </div>
      </div>
    </section>
  );
}

const CALLOUTS: [string, string, string][] = [
  ["01", "The verdict, first", "One word and one sentence, before any statistics."],
  [
    "02",
    "The band, not a promise",
    "Projected utilisation as a P10–P90 range against the breakeven line — never a single number.",
  ],
  [
    "03",
    "The assumptions ledger",
    "Every input we used. The unverified ones are shown, not buried.",
  ],
];

function ReportShowcase() {
  const [ref, progress] = useScrollProgress<HTMLElement>();
  return (
    <section id="report" ref={ref} className={SECTION}>
      <div
        className="grid items-start gap-[clamp(36px,5vw,72px)]"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 380px), 1fr))" }}
      >
        <div className="flex max-w-[452px] flex-col gap-5">
          <Eyebrow>The report</Eyebrow>
          <h2 className="text-[clamp(26px,3.4vw,34px)] leading-[1.15] font-medium">
            Detailed enough for your bank to lend against.
          </h2>
          <p className="text-cw-muted">
            And written to be read in plain language first — the statistics verify, they do not
            gatekeep.
          </p>
          <div className="flex flex-col pt-[18px]">
            {CALLOUTS.map(([n, title, body], i) => {
              // Scroll-linked: the one place it is justified, because the
              // movement mirrors reading down a document.
              const shown = progress > 0.22 + i * 0.16;
              return (
                <div
                  key={n}
                  className={`flex gap-[18px] border-t border-cw-line py-5 transition-[opacity,transform] duration-500 ease-(--cw-ease) ${
                    i === CALLOUTS.length - 1 ? "border-b" : ""
                  } ${shown ? "opacity-100" : "translate-y-2.5 opacity-25"}`}
                >
                  <span className="shrink-0 pt-0.5 font-cw-mono text-[14px] text-cw-slate">
                    {n}
                  </span>
                  <div className="flex flex-col gap-1.5">
                    <h3 className="text-[17px] font-medium">{title}</h3>
                    <p className="text-cw-muted">{body}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <Link to={`/report/${DEMO_REPORT_ID}`} className="block">
          <ReportPaper />
        </Link>
      </div>
    </section>
  );
}

function Close() {
  const ref = useReveal<HTMLElement>(60);
  return (
    <section ref={ref}>
      <div className={`flex flex-col items-start gap-7 ${SECTION}`}>
        <h2
          data-reveal="0"
          className="max-w-[660px] text-[clamp(28px,4vw,42px)] leading-[1.15] font-medium"
        >
          Start with the location. We will tell you the rest.
        </h2>
        <div data-reveal="1" className="w-full">
          <LocationCta id="close-location" />
        </div>
      </div>

      <footer
        className={`flex flex-wrap items-start justify-between gap-10 border-t border-cw-line ${PAD_X} pt-10 pb-12`}
      >
        <div className="flex max-w-[620px] flex-col gap-4">
          <span className="font-cw-mono text-[15px] font-medium tracking-[0.09em] uppercase">
            Chargeworthy
          </span>
          <p className="text-[16px] text-cw-muted">
            Chargeworthy is not a charge point operator and holds no stake in any station or charger
            brand. We earn a fee when a site proceeds to installation with a partner operator.
            Assessment fees are not contingent on a positive verdict.
          </p>
        </div>
        <nav className="flex gap-8">
          <Link
            to={`/report/${DEMO_REPORT_ID}`}
            className="inline-flex min-h-[44px] items-center text-[16px] text-cw-muted transition-colors duration-200 hover:text-cw-text"
          >
            Sample report
          </Link>
          <Link
            to="/console"
            className="inline-flex min-h-[44px] items-center text-[16px] text-cw-muted transition-colors duration-200 hover:text-cw-text"
          >
            Console
          </Link>
        </nav>
      </footer>
    </section>
  );
}

export function Landing() {
  return (
    <div className="cw-surface-root min-h-dvh bg-cw-ground font-cw-sans text-[17px] leading-[1.6] text-cw-text antialiased">
      <Header />
      <main>
        <Hero />
        <HowItWorks />
        <WhatWeCheck />
        <Cards />
        <ReportShowcase />
        <Close />
      </main>
    </div>
  );
}
