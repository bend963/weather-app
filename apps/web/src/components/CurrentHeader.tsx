import type { Forecast } from "@weather/api-types";
import { formatClock, formatTemp, formatWind } from "@/lib/format";
import { WeatherIcon } from "./WeatherIcon";

export function CurrentHeader({ forecast }: { forecast: Forecast }) {
  const { location, current, units, model_run: run } = forecast;
  const tz = location.timezone;
  return (
    <section aria-label="Current conditions" className="pt-2">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="truncate text-xl font-semibold tracking-tight">{location.name}</h1>
        {run && (
          <p className="shrink-0 text-xs text-muted" title={`Model run initialized ${run.initialization_time}`}>
            Updated {formatClock(run.ingested_at, tz)}
          </p>
        )}
      </div>

      {current ? (
        <div className="mt-4 flex items-end justify-between gap-6">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-7xl font-light leading-none tracking-tighter sm:text-8xl">
                {formatTemp(current.temperature)}
              </span>
              <WeatherIcon code={current.condition.code} size={44} className="text-muted" />
            </div>
            <p className="mt-2 text-lg">{current.condition.label}</p>
          </div>
          <dl className="grid shrink-0 grid-cols-[auto_auto] gap-x-3 gap-y-1 text-sm">
            <dt className="text-muted">Feels like</dt>
            <dd className="text-right">{formatTemp(current.feels_like)}</dd>
            <dt className="text-muted">Dewpoint</dt>
            <dd className="text-right">{formatTemp(current.dewpoint)}</dd>
            <dt className="text-muted">Wind</dt>
            <dd className="text-right">{formatWind(current.wind_speed, units.wind, current.wind_direction)}</dd>
          </dl>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted">Current conditions aren&apos;t available for this model run.</p>
      )}
      {current?.source === "forecast" && (
        <p className="mt-3 text-xs text-faint">Current conditions estimated from the nearest forecast hour.</p>
      )}
    </section>
  );
}
