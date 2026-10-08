"use client";

import type { DailyForecast, HourlyForecast, ModelRun, Units } from "@weather/api-types";
import { useEffect } from "react";
import {
  confidenceLabel,
  formatCycle,
  formatDate,
  formatDayTime,
  formatPercent,
  formatPrecip,
  formatTemp,
  formatWind,
} from "@/lib/format";

export type DrawerItem = { kind: "day"; day: DailyForecast } | { kind: "hour"; hour: HourlyForecast };

const THRESHOLD_LABELS: Record<string, { in: string; mm: string }> = {
  trace: { in: "Any measurable", mm: "Any measurable" },
  "0.01in": { in: "≥ 0.01″", mm: "≥ 0.25 mm" },
  "0.10in": { in: "≥ 0.10″", mm: "≥ 2.5 mm" },
  "0.25in": { in: "≥ 0.25″", mm: "≥ 6.4 mm" },
  "0.50in": { in: "≥ 0.50″", mm: "≥ 12.7 mm" },
  "1.00in": { in: "≥ 1.00″", mm: "≥ 25.4 mm" },
};

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-line py-1.5 text-sm last:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  );
}

function Percentiles({
  title,
  p10,
  p50,
  p90,
}: {
  title: string;
  p10?: number | null;
  p50?: number | null;
  p90?: number | null;
}) {
  return (
    <div>
      <h4 className="label">{title}</h4>
      <dl className="mt-1">
        <Row label="Median" value={formatTemp(p50)} />
        <Row label="10th percentile (P10)" value={formatTemp(p10)} />
        <Row label="90th percentile (P90)" value={formatTemp(p90)} />
      </dl>
    </div>
  );
}

function Exceedance({ probs, units }: { probs?: Record<string, number> | null; units: Units }) {
  if (!probs) return null;
  return (
    <div>
      <h4 className="label">Precipitation probabilities</h4>
      <dl className="mt-1">
        {Object.entries(THRESHOLD_LABELS).map(([key, label]) => (
          <Row key={key} label={label[units.precipitation]} value={formatPercent(probs[key])} />
        ))}
      </dl>
    </div>
  );
}

function Histogram({ edges, counts, unit }: { edges: number[]; counts: number[]; unit: string }) {
  const max = Math.max(...counts, 1);
  return (
    <div>
      <h4 className="label">Ensemble members&apos; highs</h4>
      <div className="mt-2 flex h-20 items-end gap-1" aria-hidden="true">
        {counts.map((c, i) => (
          <div key={i} className="flex-1 rounded-t bg-warm/70" style={{ height: `${(c / max) * 100}%` }} />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-xs text-muted">
        <span>{formatTemp(edges[0])}</span>
        <span>{formatTemp(edges[edges.length - 1])}</span>
      </div>
      <p className="sr-only">
        Member highs range from {formatTemp(edges[0])} to {formatTemp(edges[edges.length - 1])} {unit}
      </p>
    </div>
  );
}

export function DetailDrawer({
  item,
  onClose,
  units,
  run,
  timeZone,
}: {
  item: DrawerItem | null;
  onClose: () => void;
  units: Units;
  run: ModelRun | null | undefined;
  timeZone: string;
}) {
  useEffect(() => {
    if (!item) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [item, onClose]);

  if (!item) return null;

  const title = item.kind === "day" ? formatDate(item.day.date) : formatDayTime(item.hour.time, timeZone);
  const lead =
    item.kind === "hour"
      ? `${item.hour.lead_time_hours} h`
      : run
        ? `${Math.max(0, Math.round((Date.parse(`${item.day.date}T12:00:00Z`) - Date.parse(run.initialization_time)) / 3_600_000))} h (to midday)`
        : "–";

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={`Forecast details for ${title}`}
        onClick={(e) => e.stopPropagation()}
        className="mt-auto max-h-[85dvh] w-full overflow-y-auto rounded-t-2xl border border-line bg-surface p-5 shadow-xl sm:mt-0 sm:h-full sm:max-h-none sm:max-w-sm sm:rounded-none"
      >
        <div className="flex items-baseline justify-between">
          <h3 className="text-base font-semibold">{title}</h3>
          <button onClick={onClose} className="text-sm text-muted hover:text-ink">
            Close
          </button>
        </div>

        <div className="mt-4 space-y-6">
          {item.kind === "day" ? (
            <>
              <p className="text-sm">
                {item.day.condition.label}. {item.day.confidence.temperature_summary}.{" "}
                {item.day.confidence.precipitation_summary}.
              </p>
              <Percentiles title="High" {...item.day.high} />
              <Percentiles title="Low" {...item.day.low} />
              {item.day.high_distribution && (
                <Histogram {...item.day.high_distribution} unit={`°${units.temperature}`} />
              )}
              <div>
                <h4 className="label">Rain</h4>
                <dl className="mt-1">
                  <Row label="Chance (≥ 0.01″)" value={formatPercent(item.day.precip_probability)} />
                  <Row label="Median total" value={formatPrecip(item.day.precip_amount.p50, units.precipitation)} />
                  <Row label="High-end (P90)" value={formatPrecip(item.day.precip_amount.p90, units.precipitation)} />
                </dl>
              </div>
              <Exceedance probs={item.day.precip_exceedance} units={units} />
              <div>
                <h4 className="label">Peak wind</h4>
                <dl className="mt-1">
                  <Row label="Median" value={formatWind(item.day.wind_max.p50, units.wind)} />
                  <Row label="P90" value={formatWind(item.day.wind_max.p90, units.wind)} />
                </dl>
              </div>
              <dl>
                <Row
                  label="Overall confidence"
                  value={`${confidenceLabel(item.day.confidence.overall.level)} (${item.day.confidence.overall.score ?? "–"}/100)`}
                />
              </dl>
            </>
          ) : (
            <>
              <p className="text-sm">{item.hour.condition.label}</p>
              <Percentiles title="Temperature" {...item.hour.temperature} />
              <div>
                <h4 className="label">Rain</h4>
                <dl className="mt-1">
                  <Row label="Chance (≥ 0.01″)" value={formatPercent(item.hour.precip_probability)} />
                  <Row label="Median" value={formatPrecip(item.hour.precip_amount.p50, units.precipitation)} />
                  <Row label="High-end (P90)" value={formatPrecip(item.hour.precip_amount.p90, units.precipitation)} />
                </dl>
              </div>
              <Exceedance probs={item.hour.precip_exceedance} units={units} />
              <div>
                <h4 className="label">Wind</h4>
                <dl className="mt-1">
                  <Row
                    label="Median"
                    value={formatWind(item.hour.wind_speed.p50, units.wind, item.hour.wind_direction)}
                  />
                  <Row label="P90" value={formatWind(item.hour.wind_speed.p90, units.wind)} />
                </dl>
              </div>
              <dl>
                <Row label="Feels like" value={formatTemp(item.hour.feels_like)} />
                <Row label="Dewpoint" value={formatTemp(item.hour.dewpoint)} />
                <Row label="Cloud cover" value={formatPercent(item.hour.cloud_cover)} />
                <Row
                  label="Confidence"
                  value={`${confidenceLabel(item.hour.confidence.level)} (${item.hour.confidence.score ?? "–"}/100)`}
                />
              </dl>
            </>
          )}
          <div>
            <h4 className="label">Model</h4>
            <dl className="mt-1">
              <Row label="Model" value={run?.model ?? "–"} />
              <Row label="Initialized" value={run ? formatCycle(run.initialization_time) : "–"} />
              <Row label="Lead time" value={lead} />
              {item.kind === "day" && <Row label="Ensemble members" value={item.day.members ?? "–"} />}
            </dl>
          </div>
        </div>
      </aside>
    </div>
  );
}
