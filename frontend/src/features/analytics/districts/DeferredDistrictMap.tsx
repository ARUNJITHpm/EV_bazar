import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";
import type { ComponentProps } from "react";
import type { DistrictMap } from "./DistrictMap";
import { useViewportAtlas } from "./viewport-atlas";

const Map = lazy(() => import("./DistrictMap").then((m) => ({ default: m.DistrictMap })));

export function DeferredDistrictMap(props: ComponentProps<typeof DistrictMap>) {
  const { ref, visible, atlas, error, retry } = useViewportAtlas(props.atlas);
  const fallback = (
    <div className="analytics-section">
      <h2>Explore districts</h2>
      <p>The interactive map loads when this section is in view.</p>
      <p>
        <Link to="/data/district">Find a district</Link> for sources and available figures.
      </p>
      <noscript>JavaScript is needed for the map; district documents remain available.</noscript>
    </div>
  );
  return (
    <div ref={ref}>
      {error && (
        <p role="status">
          The map boundaries could not load. <button onClick={retry}>Retry map</button>
        </p>
      )}
      {visible ? (
        <Suspense fallback={fallback}>
          <Map {...props} atlas={atlas} />
        </Suspense>
      ) : (
        fallback
      )}
    </div>
  );
}
