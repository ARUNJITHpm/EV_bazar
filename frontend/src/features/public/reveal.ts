import { useEffect, useRef, useState } from "react";

/**
 * Scroll motion for the public surface - the reference build's hooks, ported.
 *
 * The contract that matters: content is visible in the DOM by default, and
 * the hidden state is applied only after JS confirms it can observe (the
 * `cw-reveal-armed` class). A failed script leaves a readable page, never a
 * blank one. Everything fires once and never replays, and
 * prefers-reduced-motion renders the final state immediately.
 */

const reduced = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/**
 * Arms `[data-reveal]` descendants of the returned ref: each fires once at
 * 20% viewport entry, staggered by its `data-reveal` index × `stagger` ms.
 */
export function useReveal<T extends HTMLElement>(stagger = 50) {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const root = ref.current;
    if (!root) return undefined;

    const items = Array.from(root.querySelectorAll<HTMLElement>("[data-reveal]"));
    if (!items.length) return undefined;

    if (reduced() || !("IntersectionObserver" in window)) {
      items.forEach((el) => el.classList.add("is-in"));
      return undefined;
    }

    root.classList.add("cw-reveal-armed");

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const el = entry.target as HTMLElement;
          const i = Number(el.dataset.reveal) || 0;
          el.style.setProperty("--reveal-delay", `${i * stagger}ms`);
          el.classList.add("is-in");
          observer.unobserve(el);
        });
      },
      { threshold: 0.2, rootMargin: "0px 0px -5% 0px" },
    );

    items.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [stagger]);

  return ref;
}

/**
 * Scroll-linked progress through an element, 0 to 1. Used only for the
 * report showcase, where the movement mirrors reading down a document -
 * deliberately not for pinning or hijacking any other section.
 */
export function useScrollProgress<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [progress, setProgress] = useState(() => (reduced() ? 1 : 0));

  useEffect(() => {
    const el = ref.current;
    if (!el || reduced()) {
      setProgress(1);
      return undefined;
    }

    let raf: number | null = null;
    const measure = () => {
      raf = null;
      const rect = el.getBoundingClientRect();
      const span = rect.height + window.innerHeight;
      const p = 1 - rect.bottom / span;
      setProgress(Math.min(Math.max(p, 0), 1));
    };
    const onScroll = () => {
      if (raf === null) raf = requestAnimationFrame(measure);
    };

    measure();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf !== null) cancelAnimationFrame(raf);
    };
  }, []);

  return [ref, progress];
}
