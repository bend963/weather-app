import type { Forecast } from "@weather/api-types";
import { formatClock, formatTemp, formatWind } from "@/lib/format";
import { WeatherIcon } from "./WeatherIcon";

function formatDistance(km: number, miles: boolean) {
  const value = miles ? km / 1.609 : km;
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${miles ? "mi" : "km"}`;
}

export function CurrentHeader({ forecast }: { forecast: Forecast }) {
  const { location, current, units, model_run: run } = forecast;
  const tz = location.timezone;
  return (
    <section aria-label="Current conditions" className="current pt-2">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="place-name truncate text-xl font-semibold tracking-tight">{location.name}</h1>
        {run && (
          <p className="shrink-0 text-xs text-muted" title={`Model run initialized ${run.initialization_time}`}>
            Forecast updated {formatClock(run.ingested_at, tz)}
          </p>
        )}
      </div>

      {current ? (
        <div className="mt-4 flex items-end justify-between gap-6">
          <div>
            <div className="flex items-center gap-3">
              <span className="hero-temp text-7xl font-light leading-none tracking-tighter sm:text-8xl">
                {formatTemp(current.temperature)}
              </span>
              <WeatherIcon code={current.condition.code} size={44} className="text-muted" />
            </div>
            <p className="hero-cond mt-2 text-lg">{current.condition.label}</p>
          </div>
          <dl className="grid shrink-0 grid-cols-[auto_auto] gap-x-3 gap-y-1 text-sm">
            <dt className="text-muted">Feels like</dt>
            <dd className="text-right">{formatTemp(current.feels_like)}</dd>
            <dt className="text-muted">Dewpoint</dt>
            <dd className="text-right">{formatTemp(current.dewpoint)}</dd>
            {current.humidity != null && (
              <>
                <dt className="text-muted">Humidity</dt>
                <dd className="text-right">{Math.round(current.humidity)}%</dd>
              </>
            )}
            <dt className="text-muted">Wind</dt>
            <dd className="text-right">{formatWind(current.wind_speed, units.wind, current.wind_direction)}</dd>
            {current.wind_gust != null && (
              <>
                <dt className="text-muted">Gusts</dt>
                <dd className="text-right">{formatWind(current.wind_gust, units.wind)}</dd>
              </>
            )}
          </dl>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted">Current conditions aren&apos;t available for this model run.</p>
      )}
      {current?.source === "observation" && current.station && (
        <p className="note mt-3 text-xs text-faint">
          Observed {formatClock(current.time, tz)} at {current.station.name}
          {" · "}
          {formatDistance(current.station.distance_km, units.temperature === "F")} away
        </p>
      )}
      {current?.source === "forecast" && (
        <p className="note mt-3 text-xs text-faint">Current conditions estimated from the nearest forecast hour.</p>
      )}
    </section>
  );
}
