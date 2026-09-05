import { useEffect, useRef, useState } from "react";

/**
 * A stepping clock for the two sequenced animations.
 *
 * design/IMPLEMENT.md:65-68 asks for IntersectionObserver plus CSS
 * transitions and no animation library, and animation A honours that with no
 * JS at all. B and C cannot: they walk 34 named factors through five
 * categories and into a report, and expressing that as one CSS timeline
 * means dozens of hand-tuned percentage keyframes that break the moment a
 * factor is added.
 *
 * The compromise keeps the spirit. This hook advances a STEP INDEX on a
 * setTimeout chain - roughly seven state changes per loop, not sixty per
 * second - and every continuous movement inside a step is still CSS. There
 * is no requestAnimationFrame loop and no per-frame React render.
 *
 * It stops when it is not being watched: off screen, hidden tab, or reduced
 * motion. Under reduced motion it parks on the final step, which is the
 * contract reveal.ts already sets - the finished state, immediately, with
 * nothing looping.
 *
 * `durations` must be a stable module constant, not an inline array.
 */
export function useLoopClock<T extends HTMLElement>(
  durations: readonly number[],
): [React.RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const last = durations.length - 1;

  const [motionOff, setMotionOff] = useState(
    () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false,
  );
  const [step, setStep] = useState(() => (motionOff ? last : 0));
  const [paused, setPaused] = useState(false);

  /** What is left of the current step when something interrupts it. */
  const remaining = useRef<number | null>(null);
  const startedAt = useRef(0);

  const key = durations.join(",");

  useEffect(() => {
    const query = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!query) return undefined;
    const onChange = () => {
      setMotionOff(query.matches);
      if (query.matches) setStep(last);
    };
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [last]);

  /* Pause the moment it leaves the viewport or the tab is backgrounded. A
     hero that keeps ticking in a hidden tab is just a battery cost. */
  useEffect(() => {
    if (motionOff) return undefined;
    const el = ref.current;
    let visible = document.visibilityState === "visible";
    let onScreen = true;

    const sync = () => setPaused(!visible || !onScreen);

    const onVisibility = () => {
      visible = document.visibilityState === "visible";
      sync();
    };
    document.addEventListener("visibilitychange", onVisibility);

    let observer: IntersectionObserver | undefined;
    if (el && "IntersectionObserver" in window) {
      observer = new IntersectionObserver(
        (entries) => {
          onScreen = entries[0]?.isIntersecting ?? true;
          sync();
        },
        { threshold: 0.05 },
      );
      observer.observe(el);
    }

    sync();
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      observer?.disconnect();
    };
  }, [motionOff]);

  useEffect(() => {
    if (motionOff || paused) return undefined;

    const wait = remaining.current ?? durations[step] ?? 1000;
    startedAt.current = performance.now();
    const timer = window.setTimeout(() => {
      remaining.current = null;
      setStep((s) => (s + 1) % durations.length);
    }, wait);

    return () => {
      window.clearTimeout(timer);
      /* Cleared mid-step (paused, or unmounted): carry the balance so
         resuming continues the beat rather than restarting it. On a normal
         advance the balance is zero and this stays null. */
      const left = wait - (performance.now() - startedAt.current);
      remaining.current = left > 16 ? left : null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, paused, motionOff, key]);

  return [ref, motionOff ? last : step];
}
