import type { DailyForecast } from "@weather/api-types";
import { formatPop, formatTemp, relativeDay } from "@/lib/format";
import { WeatherIcon } from "./WeatherIcon";

const BAR_H = 84;

export function DailyStrip({
  days,
  today,
  onSelect,
}: {
  days: DailyForecast[];
  today: string;
  onSelect: (day: DailyForecast) => void;
}) {
  const values = days
    .flatMap((d) => [d.low.p10 ?? d.low.p50, d.high.p90 ?? d.high.p50])
    .filter((v): v is number => v != null);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const y = (t: number | null | undefined) => (t == null ? 0 : ((max - t) / Math.max(max - min, 1)) * BAR_H);

  return (
    <section aria-labelledby="daily" className="mt-8">
      <div className="flex items-baseline justify-between">
        <h2 id="daily" className="label">
          {days.length}-day forecast
        </h2>
        <span className="hidden text-xs text-faint sm:inline">
          Bars: likely high/low · whiskers: 10th–90th percentile
        </span>
      </div>
      <ol className="scroll-x -mx-4 mt-2 flex gap-1 px-4 pb-1" aria-label="Daily forecast">
        {days.map((d) => (
          <li key={d.date} className="shrink-0">
            <button
              onClick={() => onSelect(d)}
              className="flex w-[68px] flex-col items-center gap-1.5 rounded-xl py-2 hover:bg-surface-2"
              aria-label={`${relativeDay(d.date, today)}: high ${formatTemp(d.high.p50)}, low ${formatTemp(d.low.p50)}, ${formatPop(d.precip_probability)} chance of rain`}
            >
              <span className="text-xs font-medium">{relativeDay(d.date, today)}</span>
              <WeatherIcon code={d.condition.code} size={24} />
              <span className="text-[15px] font-medium">{formatTemp(d.high.p50)}</span>
              <svg width="12" height={BAR_H} aria-hidden="true" className="overflow-visible">
                {/* Whiskers: the 10th percentile low to the 90th percentile high. */}
                <line x1="6" x2="6" y1={y(d.high.p90)} y2={y(d.low.p10)} stroke="var(--faint)" strokeWidth="1" />
                <rect
                  x="2"
                  width="8"
                  rx="4"
                  y={y(d.high.p50)}
                  height={Math.max(y(d.low.p50) - y(d.high.p50), 4)}
                  fill="var(--warm)"
                  fillOpacity="0.75"
                />
              </svg>
              <span className="text-[15px] text-muted">{formatTemp(d.low.p50)}</span>
              <span className={`text-xs ${(d.precip_probability ?? 0) >= 0.2 ? "text-rain" : "text-faint"}`}>
                {formatPop(d.precip_probability)}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
