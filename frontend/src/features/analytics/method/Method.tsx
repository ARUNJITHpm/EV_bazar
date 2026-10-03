import { Link } from "react-router-dom";
import catalogue from "virtual:analytics-public-data";
import articles from "virtual:analytics-content";
import reviewed from "virtual:analytics-method";
import { articleHref } from "../content/model";
import { datasetLabels } from "../data/schemas";
import "./method.css";
const percent = (value: number) =>
  `${(100 * value).toLocaleString("en-IN", { maximumFractionDigits: 1 })}%`;
export function Methodology() {
  const validation = reviewed.validation;
  return (
    <div className="analytics-method">
      <p className="analytics-lead">Know what a number can tell you.</p>
      <nav aria-label="On this page">
        <a href="#data-used">Data we use</a>
        <a href="#usage-estimates">Usage estimates</a>
        <a href="#validation">Validation</a>
        <a href="#privacy">Privacy</a>
        <a href="#limitations">Limitations</a>
        <a href="#corrections">Corrections</a>
      </nav>
      <section id="data-used">
        <h2>What data we use and why</h2>
        <p>
          Our archived Local Government Directory (LGD) reference links district names to district
          codes. It is a historical snapshot, not a current list of every district. Renamed or split
          districts need review before datasets can be joined.
        </p>
        <p>
          Monthly vehicle registrations would help describe EV adoption; reviewed public charger
          lists would describe coverage; regulator tariff orders would describe electricity charges.
          Highway lines and district boundaries would help locate gaps in that coverage. These
          datasets are still being prepared. A source listed as pending is never treated as zero.
        </p>
        <p>
          Owner electricity bills could provide observed energy use. We would use only confirmed
          bills for a complete calendar month, tied to verified physical connectors and a separate
          meter, with analysis consent. A bill records energy supplied through the meter; it does
          not prove how many charging sessions occurred.
        </p>
        <p>
          <Link to="/data/sources">Check each available source and its reporting period</Link>.
        </p>
      </section>
      <section id="usage-estimates">
        <h2>How district usage would be estimated</h2>
        <p>
          No district usage estimates are published yet. The method below describes the working
          model; it is awaiting real inputs, validation and publication review.
        </p>
        <p>
          We would learn from eligible stations with confirmed monthly bills, comparing similar
          connector mixes, power levels, station ages and locations. Nearby districts can share
          information when their own sample is small. For listed stations without a bill, the model
          would estimate daily energy per physical connector. We would convert that into monthly
          energy using the actual number of connectors and calendar days, then combine observed and
          estimated energy across the district.
        </p>
        <p>
          Repeated simulated outcomes would give a range. P10 is the lower end, P50 the middle and
          P90 the upper end: an estimated interval spanning the middle{" "}
          <span className="analytics-number">80%</span> of simulated outcomes. It is not a
          guarantee. Monthly energy per listed physical station would be calculated after
          aggregation; a station, charger and connector are different counting units.
        </p>
        <details>
          <summary>Technical model and features</summary>
          <p>
            The draft fits a mixed effects model to log(1 + kWh per connector per day), with state
            effects and district effects nested within states. It uses the DC connector share, power
            class, station age, road class, distance to a national highway and district EV
            registrations. Features with no variation are removed and recorded. Missing opening
            dates would be sampled from the available state age distribution, with wider
            uncertainty; absent essential inputs refuse publication.
          </p>
          <p>
            The draft uses at least <span className="analytics-number">1,000</span> Gaussian
            fitted-parameter predictive simulations. Fixed effect, geographic effect and residual
            uncertainty are simulated; fitted variance components are held fixed. This is not a
            refit bootstrap and may understate uncertainty. Predictions are recorded with all six
            version stamps before use. The model predicts energy only; it does not predict revenue
            or returns.
          </p>
        </details>
      </section>
      <section id="validation">
        <h2>Validation against held-out stations</h2>
        <p>
          Leave-one-station-out (LOO) validation would remove every month from one station, fit on
          the remaining stations, and compare its predictions with that station’s confirmed bills.
          This prevents the same station from appearing on both sides of a check.
        </p>
        {validation ? (
          <>
            <p>
              Latest approved real run:{" "}
              <time dateTime={validation.completed_on}>{validation.completed_on}</time>. Publication
              validation {validation.publication_validation_passed ? "passed" : "did not pass"};
              each district must also pass its privacy gates.
            </p>
            <dl className="analytics-method-metrics">
              <div>
                <dt>Distinct held-out stations</dt>
                <dd>{validation.stations.toLocaleString("en-IN")}</dd>
              </div>
              <div>
                <dt>LOO median absolute percentage error</dt>
                <dd>{percent(validation.median_absolute_percentage_error)}</dd>
              </div>
              <div>
                <dt>P10–P90 interval coverage</dt>
                <dd>{percent(validation.interval_coverage)}</dd>
              </div>
            </dl>
            <p>
              Error is the median absolute difference from a positive observed value, divided by
              that observation. Zero observations are excluded from percentage error, but included
              in interval coverage. Coverage is the share of held-out readings inside the predicted
              P10–P90 interval; it is measured per reading, not per station.
            </p>
            <details>
              <summary>Latest run configuration</summary>
              <p>
                Selected features: {validation.selected_features.join(", ") || "Intercept only"}.
                Simulations: {validation.simulation_count.toLocaleString("en-IN")}.
              </p>
              <dl>
                {Object.entries(validation.versions).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            </details>
          </>
        ) : (
          <p className="analytics-preparation">
            No approved real validation summary is available. LOO error, interval coverage and
            station count will appear automatically when a reviewed summary from a real run is
            published. Test and demo results cannot fill this gap.
          </p>
        )}
      </section>
      <section id="privacy">
        <h2>Owner data stays private</h2>
        <ul>
          <li>Only stations whose owners gave analysis consent.</li>
          <li>Stations with shared or unknown meters excluded.</li>
          <li>
            A published group must contain at least <span className="analytics-number">10</span>{" "}
            distinct eligible stations.
          </li>
          <li>No single station may make up more than one third of a group’s total.</li>
          <li>Groups failing either rule show “Not enough data yet”, never a number.</li>
        </ul>
        <p>
          We count stations, not bills or connectors, and use the latest confirmed correction for
          each station and month. Checks apply to every group and period. Private station
          identifiers, bills and individual predictions are never part of public downloads.
          Validation and connector coverage checks add requirements; they cannot relax these minimum
          privacy rules.
        </p>
      </section>
      <section id="limitations">
        <h2>What this data cannot tell us</h2>
        <ul>
          <li>
            Volunteer bias: owners who upload bills may differ from those who do not. Busy or
            surviving stations may be overrepresented; failed and closed stations are especially
            easy to miss.
          </li>
          <li>
            Public charger lists may omit stations, retain closed sites or duplicate physical
            stations. Coverage ratios describe the reviewed list, not a complete national census.
          </li>
          <li>
            Registration office boundaries can cross district boundaries. District allocations
            require verified mappings and visible notes.
          </li>
          <li>
            Metered energy may include losses and auxiliary loads. Shared meters are excluded;
            electricity consumption is not session demand.
          </li>
          <li>
            Tariff orders describe charges and time bands, not the total payable on an individual
            bill. Retrieval dates are not effective dates.
          </li>
          <li>
            Small samples, seasonality, unknown ages and changing station inventories can widen
            uncertainty. Estimated ranges do not resolve unmeasured selection bias.
          </li>
        </ul>
      </section>
      <section id="grid-policy-corridors">
        <h2>Grid, policies and corridors</h2>
        <p>
          AT&C loss combines technical loss with billing and collection gaps; it is not an outage or
          voltage measure. National references must match the utility observations in edition, year
          and metric basis. Conflicting editions and changed definitions are withheld rather than
          averaged.
        </p>
        <p>
          Supply hours retain their published geography, reporting period, rural or urban coverage
          and definition. Statewide context is not district or feeder reliability; 24 minus an area
          average is not a station outage log. No serving utility is assigned without a verified
          geographic mapping.
        </p>
        <p>
          Policy status is evaluated at the page build date from human-reviewed notifications and
          validity dates. The register includes expired policies and does not infer ongoing validity
          from an absent end date. Policy dates on registrations are context, not evidence that a
          policy caused a change. Descriptive policy text never changes financial inputs.
        </p>
        <p>
          Corridor gaps require verified operating DC fast chargers on connected highway geometry, a
          reviewed snap tolerance and distance along that route calculated on geography in
          EPSG:4326. Straight-line proximity is insufficient. Planned or awarded amenities appear
          separately as hollow markers only when dated evidence explicitly lists EV charging; they
          never close a gap. Gap analysis remains unavailable until these inputs and checks exist.
        </p>
        <p>
          Monthly new registrations are not the total EV fleet. An EVs-per-public-charger comparison
          needs a compatible fleet count and a reviewed charger counting unit; it cannot be
          reconstructed from a single year of registrations.
        </p>
      </section>
      <section id="editorial-policy">
        <h2>How we publish</h2>
        <p>
          We do not publish figures by named operator or promote charger brands on these pages.
          Sources, limitations and corrections remain visible.
        </p>
        <p>
          Chargeworthy currently has no affiliation with any charge point operator (CPO). We do not
          own charging stations and do not plan to own them.
        </p>
        <p>Our business model is based on site-assessment and operator-matching fees.</p>
      </section>
      <section id="corrections">
        <h2>Corrections</h2>
        <p>
          We record the date, what changed and why, and link affected charts back to their
          correction.
        </p>
        {reviewed.corrections.length ? (
          <ol>
            {reviewed.corrections.map((c) => (
              <li id={`correction-${c.id}`} key={c.id}>
                <time dateTime={c.date}>{c.date}</time>
                <p>{c.changed}</p>
                <p>Why: {c.reason}</p>
                <ul>
                  {c.charts.map((id) => {
                    const article = articles.find((a) =>
                      a.blocks.some((b) => b.kind === "chart" && b.data.id === id),
                    );
                    return (
                      <li key={id}>
                        <Link to={`${article ? articleHref(article) : "/data"}#${id}`}>
                          Affected chart: {id}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ol>
        ) : (
          <p>No corrections have been published yet.</p>
        )}
      </section>
    </div>
  );
}
export function Sources() {
  return (
    <div className="analytics-method">
      <p>
        These entries are generated from the metadata of every validated public dataset. Retrieval
        dates describe our snapshot; reporting periods describe the observations.
      </p>
      {catalogue.datasets.map((dataset) => {
        const meta = dataset.metadata;
        const charts = articles.flatMap((a) =>
          a.blocks.flatMap((b) =>
            b.kind === "chart" && b.data.sources.some((s) => s.url === meta.source_url)
              ? [{ href: `${articleHref(a)}#${b.data.id}`, title: b.data.title, article: a.title }]
              : [],
          ),
        );
        return (
          <section key={dataset.id} id={`source-${dataset.id}`}>
            <h2>{meta.title}</h2>
            <p>{meta.description}</p>
            <p>
              Source: <a href={meta.source_url}>{meta.source_name}</a>.
            </p>
            <dl>
              <div>
                <dt>Retrieved</dt>
                <dd>
                  <time dateTime={meta.retrieved_on}>{meta.retrieved_on}</time>
                </dd>
              </div>
              <div>
                <dt>Reporting period</dt>
                <dd>{meta.time_coverage}</dd>
              </div>
              <div>
                <dt>Licence</dt>
                <dd>
                  {meta.licence_url ? <a href={meta.licence_url}>{meta.licence}</a> : meta.licence}
                </dd>
              </div>
              <div>
                <dt>Update frequency</dt>
                <dd>{meta.update_frequency}</dd>
              </div>
            </dl>
            {meta.attribution && <p>Attribution: {meta.attribution}</p>}
            <p>{meta.notes}</p>
            <h3>Charts using this source</h3>
            {charts.length ? (
              <ul>
                {charts.map((c) => (
                  <li key={c.href}>
                    <Link to={c.href}>{c.title}</Link>
                    {/* The same chart can appear in more than one article. */}
                    <span className="analytics-muted"> in “{c.article}”</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No published article charts use this source yet.</p>
            )}
            <p>
              <a href={dataset.data_url} download>
                Download source data
              </a>
              {" · "}
              <a href={dataset.data_url.replace(/[^/]+$/, "README.txt")}>
                Download notes and attribution
              </a>
            </p>
          </section>
        );
      })}
      {catalogue.pending.length > 0 && (
        <section>
          <h2>Still being prepared</h2>
          <ul>
            {catalogue.pending.map((id) => (
              <li key={id} id={`source-${id}`}>
                {datasetLabels[id]}: awaiting verified data and metadata.
              </li>
            ))}
          </ul>
        </section>
      )}
      <section id="licence">
        <h2>Using and crediting this work</h2>
        <p>
          Original Chargeworthy Data text, charts and eligible original CSV outputs are licensed
          under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Credit
          Chargeworthy Data, link to the page and licence, and identify your changes. Source
          datasets retain their own licences; our licence does not replace them. OpenStreetMap data
          retains ODbL and its attribution requirements.
        </p>
        <p>
          CSV downloads include a licence comment before the column header. Download notes retain
          source attribution and reporting limits. Chart downloads also carry source licences,
          citations and output versions on every data row.
        </p>
      </section>
    </div>
  );
}
