import type { DailyForecast } from "@weather/api-types";
import { formatDate } from "./format";

/** How the runs relate on a day's high, from the API's temperature confidence level. */
export type TrustZone = "agree" | "spreading" | "scattered";

export function trustZone(day: DailyForecast): TrustZone {
  const level = day.confidence.temperature.level;
  return level === "high" ? "agree" : level === "medium" ? "spreading" : "scattered";
}

/** How far apart most runs put the high: the 10th–90th percentile range, in display units. */
export function highSpread(day: DailyForecast): number | null {
  const { p10, p90 } = day.high;
  return p10 == null || p90 == null ? null : p90 - p10;
}

/** Below this temperature agreement score the runs no longer pin the high down. */
export const ROUGH_SCORE = 50;

const weak = (day: DailyForecast) => {
  const score = day.confidence.temperature.score;
  return score != null && score < ROUGH_SCORE;
};

/**
 * Index of the first weak day from which the runs stay apart, or null if they
 * never do. One later day where the runs happen to line up again doesn't reset
 * it (far out, that's luck); a second one does.
 */
export function roughFrom(days: DailyForecast[]): number | null {
  for (let i = 0; i < days.length; i++) {
    if (!weak(days[i]!)) continue;
    const recoveries = days.slice(i).filter((d) => !weak(d)).length;
    if (recoveries <= 1) return i;
  }
  return null;
}

function degreeRange(days: DailyForecast[]): string {
  const spreads = days.map(highSpread).filter((s): s is number => s != null);
  if (!spreads.length) return "";
  const lo = Math.max(1, Math.round(Math.min(...spreads)));
  const hi = Math.max(1, Math.round(Math.max(...spreads)));
  return lo === hi ? `about ${lo}°` : `${lo} to ${hi}°`;
}

/** One or two plain sentences on how far out the forecast holds together. */
export function trustSummary(days: DailyForecast[]): string {
  if (!days.length) return "";
  const r = roughFrom(days);
  if (r == null) {
    return `The runs stay close on the daily high for all ${days.length} days (${degreeRange(days)} apart).`;
  }
  // The odd far-out day where the runs line up by luck would understate the spread.
  const late = degreeRange(days.slice(r).filter(weak));
  if (r === 0) {
    return `The runs disagree on the high from the start (${late} apart), so read the middle line as a rough guide throughout.`;
  }
  return (
    `The runs stay within ${degreeRange(days.slice(0, r))} of each other on the daily high through ${formatDate(days[r - 1]!.date)}. ` +
    `From ${formatDate(days[r]!.date)} they're ${late} apart, so read the middle line there as a rough guide, not a forecast.`
  );
}

/** Linear-interpolated percentile, the same method numpy uses on the API side. */
export function percentile(values: number[], p: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  const pos = ((sorted.length - 1) * p) / 100;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo]! + (sorted[hi]! - sorted[lo]!) * (pos - lo);
}

/** The lines the trust chart can show, each switched on or off by the viewer. */
export const LINE_IDS = ["highs", "lows", "dewpoint", "feels"] as const;
export type LineId = (typeof LINE_IDS)[number];
export type LineToggles = Record<LineId, boolean>;

export const DEFAULT_LINES: LineToggles = { highs: true, lows: true, dewpoint: false, feels: false };
const LINES_KEY = "trust-lines";

export function readLines(): LineToggles {
  try {
    const saved = JSON.parse(localStorage.getItem(LINES_KEY) ?? "null") as Partial<LineToggles> | null;
    if (!saved || typeof saved !== "object") return DEFAULT_LINES;
    return Object.fromEntries(
      LINE_IDS.map((id) => [id, typeof saved[id] === "boolean" ? saved[id] : DEFAULT_LINES[id]]),
    ) as LineToggles;
  } catch {
    return DEFAULT_LINES;
  }
}

export function saveLines(lines: LineToggles) {
  try {
    localStorage.setItem(LINES_KEY, JSON.stringify(lines));
  } catch {
    // Private mode or storage blocked: the choice just won't persist.
  }
}
