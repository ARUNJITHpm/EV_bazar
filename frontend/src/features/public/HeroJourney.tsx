import { useEffect, useRef, useState } from "react";
import { RouteToCharge } from "../animation/RouteToCharge";

/** Decorative route sequence: no sample financials, and no work while out of view. */
export function HeroJourney() {
  const ref = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    let onScreen = true;
    const sync = () => setVisible(onScreen && document.visibilityState === "visible");
    const observer = new IntersectionObserver(([entry]) => {
      onScreen = entry?.isIntersecting ?? false;
      sync();
    });
    if (ref.current) observer.observe(ref.current);
    document.addEventListener("visibilitychange", sync);
    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", sync);
    };
  }, []);
  return (
    <div ref={ref} className="home-journey" data-paused={paused || !visible}>
      <div className="home-journey-scene" aria-hidden="true">
        <RouteToCharge background />
      </div>
      <div className="home-journey-caption">
        <span>Illustration of route access and a recommended site</span>
        <button type="button" onClick={() => setPaused(!paused)}>
          {paused ? "Play animation" : "Pause animation"}
        </button>
      </div>
    </div>
  );
}
