import type { Units } from "@weather/api-types";

/**
 * Display helpers. All forecast times are shown in the saved location's
 * timezone, never the browser's, because "3 PM" must mean 3 PM *there*.
 */

export function formatTemp(value: number | null | undefined, withUnit = false, unit?: Units["temperature"]) {
  if (value == null) return "–";
  return `${Math.round(value)}°${withUnit && unit ? unit : ""}`;
}

export function formatPercent(probability: number | null | undefined) {
  if (probability == null) return "–";
  return `${Math.round(probability * 100)}%`;
}

/** Rain probability rounded to the nearest 10%, the way forecasts usually say it. */
export function formatPop(probability: number | null | undefined) {
  if (probability == null) return "–";
  const pct = Math.round(probability * 10) * 10;
  return `${pct}%`;
}

export function formatPrecip(value: number | null | undefined, unit: Units["precipitation"]) {
  if (value == null) return "–";
  if (unit === "in") {
    if (value > 0 && value < 0.01) return "<0.01″";
    return `${value.toFixed(2)}″`;
  }
  if (value > 0 && value < 0.1) return "<0.1 mm";
  return `${value.toFixed(1)} mm`;
}

const WIND_LABEL: Record<Units["wind"], string> = { mph: "mph", kmh: "km/h", mps: "m/s", kt: "kt" };

export function formatWind(speed: number | null | undefined, unit: Units["wind"], direction?: string | null) {
  if (speed == null) return "–";
  return `${direction ? `${direction} ` : ""}${Math.round(speed)} ${WIND_LABEL[unit]}`;
}

function formatter(timeZone: string, options: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat("en-US", { timeZone, ...options });
}

export function formatHour(iso: string, timeZone: string) {
  return formatter(timeZone, { hour: "numeric" }).format(new Date(iso)).replace(" ", " ");
}

export function formatClock(iso: string, timeZone: string) {
  return formatter(timeZone, { hour: "numeric", minute: "2-digit" }).format(new Date(iso));
}

export function formatDayTime(iso: string, timeZone: string) {
  return formatter(timeZone, { weekday: "short", hour: "numeric", minute: "2-digit" }).format(new Date(iso));
}

/** Calendar dates ("2026-10-10") carry no time, so format them as UTC to avoid shifting. */
export function formatWeekday(date: string, style: "short" | "long" = "short") {
  return new Intl.DateTimeFormat("en-US", { weekday: style, timeZone: "UTC" }).format(new Date(`${date}T00:00:00Z`));
}

export function formatDate(date: string) {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00Z`));
}

export function formatShortDate(date: string) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(
    new Date(`${date}T00:00:00Z`),
  );
}

/** "Today" / "Tomorrow" / weekday, relative to today's date at the location. */
export function relativeDay(date: string, today: string) {
  const diff = Math.round((Date.parse(`${date}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  return formatWeekday(date);
}

export function localDate(iso: string, timeZone: string) {
  // en-CA formats as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(
    new Date(iso),
  );
}

/** Model cycle label, e.g. "00Z Oct 8". Model runs are conventionally named in UTC. */
export function formatCycle(iso: string) {
  const d = new Date(iso);
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const md = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(d);
  return `${hh}Z ${md}`;
}

export function confidenceLabel(level: string | null | undefined) {
  if (!level) return "Unknown";
  return `${level[0]!.toUpperCase()}${level.slice(1)}`;
}
