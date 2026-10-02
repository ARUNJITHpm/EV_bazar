import { lazy, Suspense, type ComponentProps } from "react";
import { Chart as ServerChart } from "./Chart";

const BrowserChart = lazy(() => import("./Chart").then((m) => ({ default: m.Chart })));
const Chart = import.meta.env.SSR ? ServerChart : BrowserChart;

// Only a rendered chart requests chart JavaScript. The server renders the full
// figure and table; its Suspense boundary preserves that HTML during hydration.
export function ProgressiveChart(props: ComponentProps<typeof ServerChart>) {
  return (
    <Suspense fallback={<p role="status">Loading chart: {props.data.title}</p>}>
      <Chart {...props} />
    </Suspense>
  );
}
