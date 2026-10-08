"use client";

import type { HourlyForecast } from "@weather/api-types";
import { Area, Bar, ComposedChart, Line, YAxis } from "recharts";
import { formatHour, formatPop, formatTemp } from "@/lib/format";
import { WeatherIcon } from "./WeatherIcon";

const COL = 56; // px per hour; the chart and the columns share this grid

export function HourlyStrip({
  hours,
  timeZone,
  onSelect,
}: {
  hours: HourlyForecast[];
  timeZone: string;
  onSelect: (hour: HourlyForecast) => void;
}) {
  const data = hours.map((h) => ({
    band: [h.temperature.p10 ?? h.temperature.p50, h.temperature.p90 ?? h.temperature.p50],
    temp: h.temperature.p50,
    pop: Math.round((h.precip_probability ?? 0) * 100),
  }));
  const temps = hours.flatMap((h) => [h.temperature.p10, h.temperature.p90]).filter((t): t is number => t != null);
  const lo = Math.floor(Math.min(...temps)) - 1;
  const hi = Math.ceil(Math.max(...temps)) + 1;
  const width = hours.length * COL;

  return (
    <section aria-labelledby="next-24" className="mt-8">
      <div className="flex items-baseline justify-between">
        <h2 id="next-24" className="label">
          Next 24 hours
        </h2>
        <span className="hidden text-xs text-faint sm:inline">Shaded band: likely range (10th–90th percentile)</span>
      </div>
      <div className="scroll-x -mx-4 mt-2 px-4">
        <div style={{ width }}>
          <ComposedChart
            width={width}
            height={96}
            data={data}
            margin={{ top: 6, right: COL / 2, bottom: 0, left: COL / 2 }}
          >
            <YAxis yAxisId="t" domain={[lo, hi]} hide />
            <YAxis yAxisId="p" domain={[0, 300]} hide />
            <Bar
              yAxisId="p"
              dataKey="pop"
              fill="var(--rain)"
              fillOpacity={0.35}
              barSize={COL - 22}
              isAnimationActive={false}
            />
            <Area yAxisId="t" dataKey="band" stroke="none" fill="var(--band)" isAnimationActive={false} />
            <Line
              yAxisId="t"
              dataKey="temp"
              stroke="var(--warm)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
          <ol className="flex" aria-label="Hourly forecast">
            {hours.map((h, i) => (
              <li key={h.time} style={{ width: COL }} className="shrink-0">
                <button
                  onClick={() => onSelect(h)}
                  className="flex w-full flex-col items-center gap-1 rounded-lg py-2 hover:bg-surface-2"
                  aria-label={`${formatHour(h.time, timeZone)}: ${formatTemp(h.temperature.p50)}, ${h.condition.label}, ${formatPop(h.precip_probability)} chance of rain`}
                >
                  <span className="text-xs text-muted">{i === 0 ? "Now" : formatHour(h.time, timeZone)}</span>
                  <WeatherIcon code={h.condition.code} size={22} />
                  <span className="text-[15px] font-medium">{formatTemp(h.temperature.p50)}</span>
                  <span className={`text-xs ${(h.precip_probability ?? 0) >= 0.2 ? "text-rain" : "text-faint"}`}>
                    {formatPop(h.precip_probability)}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
