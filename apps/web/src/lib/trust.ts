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
