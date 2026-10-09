import type { DailyForecast, Units } from "@weather/api-types";
import { formatDate, formatPrecip } from "./format";
import { percentile } from "./trust";

/** How the runs relate on whether a day is wet, from the API's precipitation confidence level. */
export type RainZone = "agree" | "split" | "toss-up";

export function rainZone(day: DailyForecast): RainZone {
  const level = day.confidence.precipitation.level;
  return level === "high" ? "agree" : level === "medium" ? "split" : "toss-up";
}

/** A run counts as wet at 0.01 in (0.25 mm), the NWS definition behind "chance of rain". */
export function wetThreshold(unit: Units["precipitation"]) {
  return unit === "in" ? 0.01 : 0.25;
}

/** 10th, 50th and 90th percentile of the runs' daily totals, or null without member data. */
export function rainBand(day: DailyForecast): [number, number, number] | null {
  const m = day.member_precip;
  if (!m?.length) return null;
  return [percentile(m, 10), percentile(m, 50), percentile(m, 90)];
}

/** One or two plain sentences on where the runs agree about rain. */
export function rainSummary(days: DailyForecast[], unit: Units["precipitation"]): string {
  if (!days.length) return "";
  const split = days.findIndex((d) => rainZone(d) !== "agree");
  const wet = wetThreshold(unit);

  // The day the most runs bring rain to, and how much the wettest of them bring.
  let wettest: DailyForecast | null = null;
  for (const d of days) {
    if ((d.precip_probability ?? 0) > (wettest?.precip_probability ?? 0)) wettest = d;
  }
  const wettestNote = (() => {
    if (!wettest || (wettest.precip_probability ?? 0) < 0.2) return "";
    const runs = wettest.member_precip;
    const max = runs?.length ? Math.max(...runs) : wettest.precip_amount.p90;
    const count = runs?.filter((v) => v >= wet).length;
    const share = runs?.length
      ? `${count} of ${runs.length} runs`
      : `${Math.round((wettest.precip_probability ?? 0) * 100)}% of runs`;
    if (runs?.length && count === runs.length) {
      return ` ${formatDate(wettest.date)} is wet in all ${runs.length} runs, up to ${formatPrecip(max, unit)}.`;
    }
    return ` The best chance is ${formatDate(wettest.date)}: ${share} bring rain, up to ${formatPrecip(max, unit)}.`;
  })();

  if (split === -1) {
    if (!wettestNote) return `Nearly every run keeps all ${days.length} days dry.`;
    return `The runs agree on which days are wet and which are dry for all ${days.length} days.${wettestNote}`;
  }
  const lead =
    split === 0
      ? "The runs disagree on whether it rains from the start."
      : `The runs agree on rain or no rain through ${formatDate(days[split - 1]!.date)}. From ${formatDate(days[split]!.date)} they start to split on whether it rains at all.`;
  return `${lead}${wettestNote}`;
}
