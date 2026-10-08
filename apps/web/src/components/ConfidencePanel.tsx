import type { DailyForecast } from "@weather/api-types";
import { confidenceLabel, formatDate, relativeDay } from "@/lib/format";

const TONE: Record<string, string> = { high: "text-ok", medium: "text-mid", low: "text-alert" };

function Level({ level }: { level: string | null | undefined }) {
  return (
    <span className={`text-xs font-semibold uppercase tracking-wider ${TONE[level ?? ""] ?? "text-muted"}`}>
      {confidenceLabel(level)} confidence
    </span>
  );
}

export function ConfidencePanel({
  days,
  today,
  onSelect,
}: {
  days: DailyForecast[];
  today: string;
  onSelect: (day: DailyForecast) => void;
}) {
  return (
    <section aria-labelledby="confidence" className="mt-8">
      <h2 id="confidence" className="label">
        Forecast confidence
      </h2>
      <div className="mt-2 grid gap-3 sm:grid-cols-3">
        {days.map((d) => (
          <button
            key={d.date}
            onClick={() => onSelect(d)}
            className="rounded-2xl border border-line bg-surface p-4 text-left hover:bg-surface-2"
          >
            <div className="text-sm font-semibold" title={formatDate(d.date)}>
              {relativeDay(d.date, today)}
            </div>
            <div className="mt-3">
              <div className="text-xs text-muted">Temperature</div>
              <Level level={d.confidence.temperature.level} />
              <p className="mt-0.5 text-sm">{d.confidence.temperature_summary}</p>
            </div>
            <div className="mt-3">
              <div className="text-xs text-muted">Rain</div>
              <Level level={d.confidence.precipitation.level} />
              <p className="mt-0.5 text-sm">{d.confidence.precipitation_summary}</p>
            </div>
          </button>
        ))}
      </div>
      <p className="mt-2 text-xs text-faint">
        Confidence reflects how closely the forecast&apos;s ensemble members agree. It isn&apos;t a guarantee.
      </p>
    </section>
  );
}
