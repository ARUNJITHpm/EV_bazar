import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { GROUPS, OPERATOR_GROUPS } from "../animation/data";
import { DEMO_REPORT_ID } from "../report/payload";
import { PublicNavigation } from "./PublicNavigation";
import { ReportPaper } from "./ReportPaper";

const PAGE = "mx-auto w-full max-w-[1200px] px-6 sm:px-10 lg:px-16";
const SECTION = `${PAGE} py-12 sm:py-16`;
const LINK =
  "inline-flex min-h-[44px] items-center underline underline-offset-4 transition-colors hover:text-cw-text";

/** A short customer introduction; detailed evidence stays in the report and optional checks. */
export function Landing() {
  const navigate = useNavigate();
  const [location, setLocation] = useState("");
  useEffect(() => {
    document.title = "Chargeworthy — is your land suitable for EV charging?";
  }, []);
  function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    navigate("/assess", { state: { q: location.trim() } });
  }
  return (
    <div className="cw-surface-root min-h-dvh bg-cw-ground font-cw-sans text-[17px] leading-[1.6] text-cw-text antialiased">
      <a href="#home-content" className="sr-only focus:not-sr-only focus:block focus:p-4">
        Skip to content
      </a>
      <header className="border-b border-cw-line">
        <div className={`${PAGE} flex flex-wrap items-center justify-between gap-x-8 gap-y-2 py-4`}>
          <Link
            to="/"
            className="inline-flex min-h-[44px] items-center font-cw-mono text-[21px] font-medium tracking-[0.08em] uppercase"
          >
            Chargeworthy
          </Link>
          <PublicNavigation />
        </div>
      </header>
      <main id="home-content">
        <section
          className={`${PAGE} pt-10 pb-12 sm:pt-16 sm:pb-16 lg:pt-20`}
          aria-labelledby="home-heading"
        >
          <h1
            id="home-heading"
            className="max-w-[20ch] text-[clamp(34px,5vw,60px)] leading-[1.1] font-semibold tracking-[-0.025em] text-balance"
          >
            Is your land suitable for EV charging?
          </h1>
          <p className="mt-5 max-w-[60ch] text-[18px] text-cw-muted">
            We assess your location, compare costs and possible returns, and help you compare
            charging operators.
          </p>
          <form onSubmit={start} className="mt-7 max-w-[760px]">
            <label htmlFor="home-location" className="mb-2 block font-medium">
              Site location
            </label>
            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                id="home-location"
                value={location}
                onChange={(event) => setLocation(event.target.value)}
                placeholder="Enter an address or area"
                aria-describedby="location-help"
                autoComplete="street-address"
                className="min-h-[58px] min-w-0 flex-1 border border-cw-line bg-cw-surface px-5 text-cw-text placeholder:text-cw-muted"
              />
              <button
                type="submit"
                className="inline-flex min-h-[58px] items-center justify-center bg-cw-accent px-7 font-semibold text-cw-ground transition-[filter] hover:brightness-107"
              >
                Check my location
              </button>
            </div>
            <p id="location-help" className="mt-3 text-[15px] text-cw-muted">
              Next, place a pin on the map. You can also start without typing.
            </p>
          </form>
          <p className="mt-3 text-[15px] text-cw-muted">
            Coverage varies by district. If verified data is missing, we will tell you.
          </p>
          <Link to={`/report/${DEMO_REPORT_ID}`} className={`${LINK} mt-4 text-cw-muted`}>
            View sample report
          </Link>
        </section>
        <section className="border-t border-cw-line" aria-labelledby="benefits-heading">
          <div className={SECTION}>
            <h2
              id="benefits-heading"
              className="text-[clamp(26px,3vw,36px)] leading-[1.2] font-medium"
            >
              Know what you are getting into.
            </h2>
            <div className="mt-7 grid gap-8 md:grid-cols-3">
              <div>
                <h3 className="text-[21px] font-medium">Understand your site</h3>
                <p className="mt-2 text-cw-muted">
                  See how access, nearby chargers, local demand and power availability affect the
                  location.
                </p>
              </div>
              <div>
                <h3 className="text-[21px] font-medium">See the money and the risk</h3>
                <p className="mt-2 text-cw-muted">
                  Compare setup costs and downside, central and upside scenarios. Estimates are not
                  promises.
                </p>
              </div>
              <div>
                <h3 className="text-[21px] font-medium">Compare charging operators</h3>
                <p className="mt-2 text-cw-muted">
                  Compare the companies that run charging stations. Missing commercial terms stay
                  marked as missing.
                </p>
              </div>
            </div>
          </div>
        </section>
        <section className="border-t border-cw-line" aria-labelledby="sample-heading">
          <div className={`${SECTION} grid items-start gap-8 md:grid-cols-2 md:gap-12`}>
            <div>
              <h2
                id="sample-heading"
                className="text-[clamp(26px,3vw,36px)] leading-[1.2] font-medium"
              >
                See what an assessment looks like.
              </h2>
              <p className="mt-4 max-w-[50ch] text-cw-muted">
                This demonstration uses a sample site and modelled demand. It is not an assessment
                of your land.
              </p>
              <p className="mt-4 max-w-[50ch] text-cw-muted">
                The report gives a clear decision, explains the risks and shows what could change
                the answer — including when the advice is not to build.
              </p>
              <Link to={`/report/${DEMO_REPORT_ID}`} className={`${LINK} mt-4 text-cw-text`}>
                Read the full sample report
              </Link>
            </div>
            <div>
              <p className="mb-3 text-[15px] font-medium text-cw-muted">
                Example only · sample site and figures
              </p>
              <ReportPaper compact />
            </div>
          </div>
        </section>
        <section className="border-t border-cw-line" aria-labelledby="steps-heading">
          <div className={SECTION}>
            <h2
              id="steps-heading"
              className="text-[clamp(26px,3vw,36px)] leading-[1.2] font-medium"
            >
              Start with your location.
            </h2>
            <ol className="mt-6 grid list-inside list-decimal gap-5 text-cw-muted md:grid-cols-3">
              <li>
                <span className="font-medium text-cw-text">Place a pin.</span>
                <p className="mt-1">Choose the exact spot on the map.</p>
              </li>
              <li>
                <span className="font-medium text-cw-text">Tell us about the site.</span>
                <p className="mt-1">
                  Answer a few questions about power, space and your plans. Skip what you do not
                  know.
                </p>
              </li>
              <li>
                <span className="font-medium text-cw-text">See the next step.</span>
                <p className="mt-1">
                  Get the available site check, or join the waitlist where verified data is not
                  ready.
                </p>
              </li>
            </ol>
          </div>
        </section>
        <section className="border-t border-cw-line" aria-labelledby="questions-heading">
          <div className={SECTION}>
            <h2
              id="questions-heading"
              className="text-[clamp(26px,3vw,36px)] leading-[1.2] font-medium"
            >
              Want to know more?
            </h2>
            <div className="mt-6 max-w-[850px]">
              <details className="border-t border-cw-line py-4">
                <summary className="min-h-[44px] cursor-pointer py-2 text-[18px] font-medium">
                  What do you check at a site?
                </summary>
                <p className="mt-3 text-cw-muted">
                  This is the full checklist. Some checks need a site survey or a verified source;
                  your report marks gaps and unverified inputs.
                </p>
                <div className="mt-5 grid gap-6 sm:grid-cols-2">
                  {GROUPS.map((group) => (
                    <div key={group.key}>
                      <h3 className="font-medium">{group.name}</h3>
                      <p className="mt-1 text-[15px] text-cw-muted">{group.source}</p>
                      <ul className="mt-3 list-disc space-y-1 pl-5 text-cw-muted">
                        {group.checks.map((check) => (
                          <li key={check.label}>{check.label}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </details>
              <details className="border-t border-cw-line py-4">
                <summary className="min-h-[44px] cursor-pointer py-2 text-[18px] font-medium">
                  How do you compare operators?
                </summary>
                <p className="mt-3 text-cw-muted">
                  We show network fit beside the financial scenarios. Unverified uptime, occupancy
                  and commercial terms are not guessed. Confirm the selected operator's terms in
                  writing before you proceed.
                </p>
                <div className="mt-5 grid gap-6 sm:grid-cols-2">
                  {OPERATOR_GROUPS.map((group) => (
                    <div key={group.key}>
                      <h3 className="font-medium">{group.source}</h3>
                      <ul className="mt-3 space-y-3 text-cw-muted">
                        {group.factors.map((factor) => (
                          <li key={factor.label}>
                            <span className="text-cw-text">{factor.label}</span>
                            <p className="text-[15px]">{factor.effect}</p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </details>
              <details className="border-t border-cw-line py-4">
                <summary className="min-h-[44px] cursor-pointer py-2 text-[18px] font-medium">
                  Already run a charging station?
                </summary>
                <p className="mt-3 text-cw-muted">
                  Sign in or create an owner account to submit your station's electricity bill.
                  Comparisons depend on enough consented, comparable submissions.
                </p>
                <Link to="/owner" className={`${LINK} mt-3`}>
                  Go to station owners
                </Link>
              </details>
              <details className="border-t border-cw-line py-4">
                <summary className="min-h-[44px] cursor-pointer py-2 text-[18px] font-medium">
                  Where does the data come from?
                </summary>
                <p className="mt-3 text-cw-muted">
                  Your report lists sources and assumptions. Explore our public data pages for
                  available references and their limits.
                </p>
                <Link to="/data" className={`${LINK} mt-3`}>
                  Explore Chargeworthy Data
                </Link>
              </details>
            </div>
          </div>
        </section>
      </main>
      <footer className="border-t border-cw-line">
        <div className={`${PAGE} py-8`}>
          <p className="max-w-[75ch] text-[15px] text-cw-muted">
            Chargeworthy earns assessment and operator-matching fees. We have no current CPO
            affiliation and do not own or operate charging stations. Operator-matching fees create a
            potential commercial conflict that must be disclosed.
          </p>
        </div>
      </footer>
    </div>
  );
}
