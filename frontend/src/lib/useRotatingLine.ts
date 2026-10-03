import { useEffect, useMemo, useState } from "react";

import { LOADING_LINES, type DayPart, type LoadingLine } from "../content/loadingLines";

/** Long enough to read a line twice; the working screen runs ~14 s. */
export const ROTATE_MS = 3_500;

/** The part of the day in IST, whatever the viewer's own clock says. */
export function dayPartIst(now: Date): DayPart {
  const hour = Number(
    new Intl.DateTimeFormat("en-IN", {
      hour: "numeric",
      hourCycle: "h23",
      timeZone: "Asia/Kolkata",
    }).format(now),
  );
  if (hour < 5) return "night";
  if (hour < 12) return "morning";
  if (hour < 17) return "afternoon";
  if (hour < 22) return "evening";
  return "night";
}

/**
 * The lines for this viewer, in show order: their state's line first (the
 * one that lands), then the time-of-day line, then the general ones shuffled.
 * Lines tagged for another state or another part of the day are dropped.
 */
export function pickLines(
  lines: readonly LoadingLine[],
  stateName: string | null | undefined,
  part: DayPart,
  random: () => number = Math.random,
): string[] {
  const state = stateName?.trim().toUpperCase() ?? null;
  const regional = lines.filter((l) => l.states && state && l.states.includes(state));
  const timely = lines.filter((l) => !l.states && l.when === part);
  const general = lines.filter((l) => !l.states && !l.when);
  const shuffled = [...general];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j]!, shuffled[i]!];
  }
  return [...regional, ...timely, ...shuffled].map((l) => l.text);
}

/**
 * One line at a time, rotating every ROTATE_MS while `running`. With
 * reduced motion it never rotates - the first line stays put.
 */
export function useRotatingLine({
  stateName,
  running,
  reducedMotion,
}: {
  stateName: string | null | undefined;
  running: boolean;
  reducedMotion: boolean;
}): string | undefined {
  const lines = useMemo(
    () => pickLines(LOADING_LINES, stateName, dayPartIst(new Date())),
    [stateName],
  );
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!running || reducedMotion || lines.length < 2) return undefined;
    const id = setInterval(() => setIndex((i) => (i + 1) % lines.length), ROTATE_MS);
    return () => clearInterval(id);
  }, [running, reducedMotion, lines.length]);

  return lines[index % Math.max(lines.length, 1)];
}
