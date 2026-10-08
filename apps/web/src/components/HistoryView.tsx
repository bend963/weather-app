"use client";

import type { ForecastHistory, Location } from "@weather/api-types";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Area, Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiFailure } from "@/lib/api";
import { formatCycle, formatDate, formatPercent, formatShortDate, formatTemp, formatWeekday } from "@/lib/format";
import { LocationBar } from "./LocationBar";
import { StateMessage, type StateKind } from "./StateMessage";

type Pair = { temperature: ForecastHistory; precipitation: ForecastHistory };

/**
 * Forecast evolution: how successive model runs predicted one target day.
 * Converging values across runs mean growing confidence in the outcome.
 */
export function HistoryView({ locationId }: { locationId: string }) {
  const router = useRouter();
  const [locations, setLocations] = useState<Location[]>([]);
  const [targetDate, setTargetDate] = useState<string | undefined>(undefined);
  const [data, setData] = useState<Pair | null>(null);
  const [state, setState] = useState<StateKind | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await api.me();
        const [locs, temperature] = await Promise.all([
          api.listLocations(),
          api.history(locationId, { target_date: targetDate, metric: "temperature" }),
        ]);
        const precipitation = await api.history(locationId, {
          target_date: temperature.target_date ?? undefined,
          metric: "precipitation",
        });
        if (cancelled) return;
        setLocations(locs);
        setData({ temperature, precipitation });
        setState(temperature.entries.length ? null : "forecast-unavailable");
      } catch (e) {
        if (!cancelled)
          setState(e instanceof ApiFailure && e.kind === "not_found" ? "location-not-found" : "api-unavailable");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [locationId, targetDate]);

  const temp = data?.temperature;
  const selected = temp?.target_date ?? targetDate;
  const rows =
    temp?.entries.map((e, i) => {
      const rain = data?.precipitation.entries[i]?.values.precipitation;
      const high = e.values.high;
      const low = e.values.low;
      return {
        run: formatCycle(e.model_run.initialization_time),
        day: formatWeekday(e.model_run.initialization_time.slice(0, 10)),
        lead: e.lead_time_hours,
        high: high?.p50 ?? null,
        band: [high?.p10 ?? high?.p50 ?? null, high?.p90 ?? high?.p50 ?? null],
        low: low?.p50 ?? null,
        rain: rain?.probability != null ? Math.round(rain.probability * 100) : null,
      };
    }) ?? [];
  const unit = temp?.units.temperature ?? "F";

  return (
    <div className="mx-auto max-w-3xl px-4 pb-16">
      <LocationBar locations={locations} currentId={locationId} onAdd={() => router.push("/")} />
      <Link href={`/weather/${locationId}`} className="text-sm text-muted hover:text-ink">
        ← Back to forecast
      </Link>
      <h1 className="mt-3 text-xl font-semibold tracking-tight">How the forecast changed</h1>
      <p className="mt-1 text-sm text-muted">
        Each model run makes a new prediction. When runs agree with each other, confidence grows.
      </p>

      {temp && temp.available_dates.length > 0 && (
        <div className="scroll-x mt-5 flex gap-1" role="tablist" aria-label="Target date">
          {temp.available_dates.map((d) => (
            <button
              key={d}
              role="tab"
              aria-selected={d === selected}
              onClick={() => setTargetDate(d)}
              className={`shrink-0 rounded-full px-3 py-1 text-sm ${
                d === selected ? "bg-ink text-bg" : "text-muted hover:bg-surface-2"
              }`}
            >
              {formatWeekday(d)} {formatShortDate(d)}
            </button>
          ))}
        </div>
      )}

      {state && <StateMessage kind={state} />}

      {!state && temp && selected && (
        <section className="mt-6">
          <h2 className="text-lg font-medium">{formatDate(selected)}</h2>
          <div className="mt-4 h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="run" tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} axisLine={false} />
                <YAxis
                  yAxisId="t"
                  tick={{ fontSize: 11, fill: "var(--muted)" }}
                  tickLine={false}
                  axisLine={false}
                  allowDecimals={false}
                  tickFormatter={(v: number) => `${Math.round(v)}°`}
                  domain={[(min: number) => Math.floor(min - 3), (max: number) => Math.ceil(max + 3)]}
                />
                <YAxis yAxisId="p" orientation="right" domain={[0, 100]} hide />
                <Tooltip
                  contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", fontSize: 12 }}
                  formatter={(value, name) =>
                    name === "rain"
                      ? [`${value}%`, "Rain chance"]
                      : name === "high"
                        ? [`${value}°`, "High"]
                        : [String(value), String(name)]
                  }
                />
                <Bar
                  yAxisId="p"
                  dataKey="rain"
                  fill="var(--rain)"
                  fillOpacity={0.3}
                  barSize={18}
                  isAnimationActive={false}
                />
                <Area yAxisId="t" dataKey="band" stroke="none" fill="var(--band)" isAnimationActive={false} />
                <Line
                  yAxisId="t"
                  dataKey="high"
                  stroke="var(--warm)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div className="scroll-x mt-6">
            <table className="w-full min-w-max text-sm">
              <thead>
                <tr className="text-left text-xs text-muted">
                  <th className="py-1.5 pr-4 font-medium">Model run</th>
                  {rows.map((r) => (
                    <th key={r.run} className="px-2 py-1.5 text-right font-medium">
                      <div>{r.day}</div>
                      <div className="text-faint">{r.run.split(" ")[0]}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                <tr>
                  <th className="py-2 pr-4 text-left font-normal text-muted">High</th>
                  {rows.map((r) => (
                    <td key={r.run} className="px-2 py-2 text-right">
                      {formatTemp(r.high)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th className="py-2 pr-4 text-left font-normal text-muted">Low</th>
                  {rows.map((r) => (
                    <td key={r.run} className="px-2 py-2 text-right">
                      {formatTemp(r.low)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th className="py-2 pr-4 text-left font-normal text-muted">Rain</th>
                  {rows.map((r) => (
                    <td key={r.run} className="px-2 py-2 text-right text-rain">
                      {r.rain == null ? "–" : formatPercent(r.rain / 100)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th className="py-2 pr-4 text-left font-normal text-muted">Lead time</th>
                  {rows.map((r) => (
                    <td key={r.run} className="px-2 py-2 text-right text-faint">
                      {r.lead != null ? `${Math.round(r.lead / 24)}d` : "–"}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-faint">Temperatures in °{unit}. Model runs are labeled by their UTC cycle.</p>
        </section>
      )}
    </div>
  );
}
