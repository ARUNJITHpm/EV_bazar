import expansion from "virtual:analytics-expansion";
import catalogue from "virtual:analytics-public-data";
import { expansionLinks } from "./expansion/home-links";
import { Link } from "react-router-dom";

export function HomeDataSection() {
  return (
    <section
      aria-labelledby="home-data-title"
      className="border-t border-cw-line px-[clamp(24px,5vw,80px)] py-[clamp(40px,6vw,72px)]"
    >
      <div className="grid gap-8 md:grid-cols-2 md:items-center">
        <div>
          <h2 id="home-data-title" className="font-cw-serif text-[32px] leading-[1.2]">
            Chargeworthy Data
          </h2>
          <p className="mt-4 max-w-[48ch] text-cw-muted">
            Free, public data on EV charging in India, with clear sources and explanations.
          </p>
          <Link
            to="/data"
            className="mt-4 inline-flex min-h-[44px] items-center gap-3 text-cw-text underline underline-offset-4"
          >
            Explore the data <span aria-hidden="true">→</span>
          </Link>
          {expansionLinks(expansion, catalogue).map((link) => (
            <p key={link.to} className="mt-2">
              <Link
                to={link.to}
                className="inline-flex min-h-[44px] items-center underline underline-offset-4"
              >
                {link.label}
              </Link>
            </p>
          ))}
        </div>
        <div className="border-l border-cw-line pl-6">
          <p className="font-cw-mono text-[14px] text-cw-muted uppercase">The weekly chart</p>
          <p className="mt-3 max-w-[46ch]">
            The first chart is being prepared. It will appear here once its public dataset is
            verified and the post is published.
          </p>
        </div>
      </div>
    </section>
  );
}
