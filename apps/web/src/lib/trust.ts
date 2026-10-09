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

/**
 * Index of the first day from which the runs never get back to solid agreement
 * (the start of the trailing run of days scoring under ROUGH_SCORE), or null if
 * the last day still agrees. A single shaky day followed by agreement doesn't count.
 */
export function roughFrom(days: DailyForecast[]): number | null {
  let start: number | null = null;
  for (let i = days.length - 1; i >= 0; i--) {
    const score = days[i]!.confidence.temperature.score;
    if (score == null || score >= ROUGH_SCORE) break;
    start = i;
  }
  return start;
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
  const late = degreeRange(days.slice(r));
  if (r === 0) {
    return `The runs disagree on the high from the start (${late} apart), so read the middle line as a rough guide throughout.`;
  }
  return (
    `The runs stay within ${degreeRange(days.slice(0, r))} of each other on the daily high through ${formatDate(days[r - 1]!.date)}. ` +
    `From ${formatDate(days[r]!.date)} they're ${late} apart, so read the middle line there as a rough guide, not a forecast.`
  );
}
