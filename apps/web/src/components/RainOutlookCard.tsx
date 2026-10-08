import type { RainOutlook, Units } from "@weather/api-types";
import { formatPercent, formatPrecip } from "@/lib/format";

export function RainOutlookCard({ outlook, units }: { outlook: RainOutlook; units: Units }) {
  const rain = outlook.next_rain;
  return (
    <section aria-labelledby="rain-outlook" className="card rounded-2xl border border-line bg-surface p-4">
      <h2 id="rain-outlook" className="label">
        Rain outlook
      </h2>
      {rain ? (
        <>
          <p className="mt-2 text-[15px]">{outlook.summary}</p>
          <dl className="mt-3 grid grid-cols-3 gap-3">
            <div>
              <dt className="text-xs text-muted">Probability</dt>
              <dd className="text-2xl font-light">{formatPercent(rain.peak_probability)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Expected</dt>
              <dd className="text-2xl font-light">{formatPrecip(rain.expected_amount, units.precipitation)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted" title="The wettest 10% of ensemble members">
                High-end scenario
              </dt>
              <dd className="text-2xl font-light">{formatPrecip(rain.high_end_amount, units.precipitation)}</dd>
            </div>
          </dl>
        </>
      ) : (
        <p className="mt-2 text-[15px]">{outlook.summary}</p>
      )}
    </section>
  );
}
