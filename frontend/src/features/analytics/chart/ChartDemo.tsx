import { Chart } from "./Chart";
import { publicDataVersions } from "../data/schemas";
import type { ChartData, ChartType } from "./model";

// Authored SVG fixtures, not a model run. This module is unreachable in production.
export default function ChartDemo() {
  const types: ChartType[] = ["line", "bar", "horizontal-bar", "range", "small-multiples"];
  return (
    <>
      <h1>Chart development demo</h1>
      <aside className="analytics-preparation">
        <h2>Test data</h2>
        <p>Invented fixture values. No observations or predictions are published here.</p>
      </aside>
      {types.map((type) => {
        const data: ChartData = {
          id: `demo-${type}`,
          title: `Test data: ${type}`,
          subtitle: "Invented monthly energy, in kWh. For interface checks only.",
          summary: "Invented example with an explicit missing observation and estimate ranges.",
          type,
          unit: "kWh",
          updated: "2026-09-30",
          sources: [
            {
              name: "Authored development fixtures",
              url: "https://example.invalid/chart-fixture",
              licence: "Test fixture only; not for publication",
            },
          ],
          notes: ["All values are invented. Sample sizes are fixture labels, not evidence."],
          versions: {
            ...publicDataVersions,
            renderer_version: "analytics_svg_v1",
            model_version: "not_applicable:authored_fixture",
          },
          rows: ["Test District North", "Test District South"].flatMap((region, seriesIndex) =>
            ["2026-01", "2026-02", "2026-03"].map((period, index) => ({
              region: `Test State / ${region}`,
              series: region,
              period,
              label: period,
              indicator: "Energy",
              value:
                seriesIndex === 1 && index === 1 ? null : 10000 + seriesIndex * 5000 + index * 2000,
              p10:
                seriesIndex === 1 && index === 1 ? null : 8000 + seriesIndex * 5000 + index * 2000,
              p90:
                seriesIndex === 1 && index === 1 ? null : 14000 + seriesIndex * 5000 + index * 2000,
              status:
                seriesIndex === 1 && index === 1 ? ("suppressed" as const) : ("estimate" as const),
              sample_size: seriesIndex === 1 && index === 1 ? null : 12,
            })),
          ),
        };
        return <Chart key={type} data={data} />;
      })}
    </>
  );
}
