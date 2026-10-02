import { Link } from "react-router-dom";
import atlas from "virtual:analytics-atlas";
import catalogue from "virtual:analytics-public-data";
import expansion from "virtual:analytics-expansion";
import { districtContext } from "./district-context";
import { placeName, type AssessOut } from "./state";

export function YourDistrict({ out }: { out?: AssessOut }) {
  const context = districtContext(out?.lgd_district_code, catalogue, atlas, expansion);
  if (!context) return null;
  return (
    <section
      aria-labelledby="your-district-title"
      className="border-y border-cw-line py-7"
      data-versions={JSON.stringify(context.versions)}
    >
      <h2 id="your-district-title" className="text-[24px] font-medium">
        Your district · {placeName(context.district.district_name, context.district.state_name)}
      </h2>
      <dl className="mt-5 grid gap-x-10 gap-y-6 md:grid-cols-2">
        {context.facts.map((fact) => (
          <div key={fact.label}>
            <dt className="text-[15px] text-cw-muted">{fact.label}</dt>
            <dd className="mt-1">
              <p className="text-[18px]">{fact.value}</p>
              <p className="mt-1 max-w-[60ch] text-[14px] text-cw-muted">{fact.note}</p>
              {fact.source && (
                <a
                  href={fact.source.source_url}
                  className="mt-2 inline-flex min-h-[44px] items-center text-[14px] underline underline-offset-4"
                >
                  {fact.source.source_name} · retrieved {fact.source.retrieved_on}
                </a>
              )}
            </dd>
          </div>
        ))}
      </dl>
      <Link
        to={`/data/district/${context.district.slug}`}
        className="mt-5 inline-flex min-h-[44px] items-center underline underline-offset-4"
      >
        Explore this district's data
      </Link>
    </section>
  );
}
