import { useEffect, useRef, useState } from "react";
import catalogue from "virtual:analytics-public-data";
import { decodeTopology, type Atlas, type Topology } from "./model";

// The validated TopoJSON is a separate public artifact, never route JavaScript.
// Load it only when the map/locator is visible. Keep observation data unchanged.
export function useViewportAtlas<T extends Atlas>(base: T) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [atlas, setAtlas] = useState(base);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    if (!("IntersectionObserver" in window)) {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setVisible(true);
        observer.disconnect();
      }
    });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const source = catalogue.datasets.find((d) => d.id === "district_boundaries");
    if (!visible || !source || base.shapes.length) return;
    const controller = new AbortController();
    setError(false);
    void fetch(source.data_url, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Boundary artifact unavailable");
        const geometry = (await response.json()) as Topology;
        const shapes = decodeTopology(geometry);
        if (!controller.signal.aborted) setAtlas({ ...base, shapes });
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      });
    return () => controller.abort();
  }, [visible, base, attempt]);
  return { ref, atlas, visible, error, retry: () => setAttempt((n) => n + 1) };
}
