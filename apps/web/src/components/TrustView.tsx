import type { DailyForecast } from "@weather/api-types";
import { formatShortDate, formatWeekday } from "@/lib/format";
import { highSpread, roughFrom, trustSummary, trustZone, type TrustZone } from "@/lib/trust";

const W = 1000;
const H = 330;
const LEFT = 44;
const RIGHT = 12;
const TOP = 34;
const BASE = 250;

const ZONE_COLOR: Record<TrustZone, string> = {
  agree: "var(--ok)",
  spreading: "var(--mid)",
  scattered: "var(--alert)",
};

type Key = "high" | "low";

/** Members' values for one field, but only if every day has the same number of them. */
function memberLines(days: DailyForecast[], field: "member_highs" | "member_lows"): number[][] | null {
  const first = days[0]?.[field];
  if (!first?.length || days.some((d) => d[field]?.length !== first.length)) return null;
  return first.map((_, m) => days.map((d) => d[field]![m]!));
}

/**
 * "How far out can you trust it?": every run's daily high and low across the
 * whole forecast, so you can see where the runs agree and where they fan out.
 */
export function TrustView({ days, today, members }: { days: DailyForecast[]; today: string; members?: number | null }) {
  if (days.length < 2) return null;

  const highs = memberLines(days, "member_highs");
  const lows = memberLines(days, "member_lows");
  const values = [
    ...days.flatMap((d) => [d.high.p10, d.high.p90, d.low.p10, d.low.p90]),
    ...(highs ?? []).flat(),
    ...(lows ?? []).flat(),
  ].filter((v): v is number => v != null);
  const lo = Math.floor((Math.min(...values) - 2) / 5) * 5;
  const hi = Math.ceil((Math.max(...values) + 2) / 5) * 5;
  const n = days.length;
  const x = (i: number) => LEFT + 28 + ((W - LEFT - RIGHT - 56) * i) / (n - 1);
  const y = (v: number) => BASE - ((BASE - TOP) * (v - lo)) / Math.max(hi - lo, 1);
  const line = (vals: (number | null | undefined)[]) =>
    vals.flatMap((v, i) => (v == null ? [] : [`${x(i)},${y(v)}`])).join(" ");
  const band = (k: Key) =>
    [
      ...days.map((d, i) => `${x(i)},${y(d[k].p90 ?? d[k].p50 ?? 0)}`),
      ...days.map((d, i) => `${x(i)},${y(d[k].p10 ?? d[k].p50 ?? 0)}`).reverse(),
    ].join(" ");

  const rough = roughFrom(days);
  const roughX = rough == null ? null : rough === 0 ? LEFT : (x(rough - 1) + x(rough)) / 2;
  const grid: number[] = [];
  for (let v = lo; v <= hi; v += 10) grid.push(v);
  const runs = members ?? highs?.length;

  return (
    <section aria-labelledby="trust" className="dash-section trust mt-8">
      <div className="flex items-baseline justify-between">
        <h2 id="trust" className="label">
          How far out can you trust it?
        </h2>
        <span className="note hidden text-xs text-faint sm:inline">
          {runs ? `All ${runs} runs, ` : ""}
          {n} days
        </span>
      </div>
      <p className="mt-2 max-w-[62ch] text-[15px] leading-normal">{trustSummary(days)}</p>
      <div className="chart-paper scroll-x -mx-4 mt-2 px-4">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`Daily highs and lows from ${runs ? `all ${runs}` : "the"} forecast runs over ${n} days`}
          className="block h-auto w-full min-w-[640px] overflow-visible"
          style={{ fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums" }}
        >
          {roughX != null && (
            <g data-testid="rough-guide">
              <rect
                x={roughX}
                y={TOP - 22}
                width={W - RIGHT - roughX}
                height={BASE - TOP + 22}
                fill="var(--ink)"
                fillOpacity={0.045}
              />
              <line
                x1={roughX}
                x2={roughX}
                y1={TOP - 22}
                y2={BASE}
                stroke="var(--ink)"
                strokeOpacity={0.45}
                strokeDasharray="4 4"
              />
              <text x={roughX + 8} y={TOP - 8} fontSize={13} fill="var(--ink)">
                Rough guide only from here
              </text>
            </g>
          )}
          {grid.map((v) => (
            <g key={v}>
              <line x1={LEFT} x2={W - RIGHT} y1={y(v)} y2={y(v)} stroke="var(--line)" />
              <text x={LEFT - 6} y={y(v) + 4} textAnchor="end" fontSize={12} fill="var(--muted)">
                {v}°
              </text>
            </g>
          ))}
          <polygon points={band("high")} fill="var(--warm)" fillOpacity={0.16} />
          <polygon points={band("low")} fill="var(--rain)" fillOpacity={0.16} />
          {[
            [highs, "var(--warm)"],
            [lows, "var(--rain)"],
          ].map(([lines, color], k) =>
            (lines as number[][] | null)?.map((vals, m) => (
              <polyline
                key={`${k}-${m}`}
                data-testid="member-line"
                points={line(vals)}
                fill="none"
                stroke={color as string}
                strokeOpacity={0.22}
                strokeWidth={1}
              />
            )),
          )}
          {(["high", "low"] as const).map((k) => {
            const color = k === "high" ? "var(--warm)" : "var(--rain)";
            return (
              <g key={k}>
                <polyline
                  points={line(days.map((d) => d[k].p50))}
                  fill="none"
                  stroke={color}
                  strokeWidth={2.4}
                  strokeLinejoin="round"
                />
                {days.map((d, i) =>
                  d[k].p50 == null ? null : <circle key={i} cx={x(i)} cy={y(d[k].p50)} r={3} fill={color} />,
                )}
              </g>
            );
          })}
          {days.map((d, i) => {
            const zone = trustZone(d);
            const spread = highSpread(d);
            return (
              <g key={d.date} textAnchor="middle" data-zone={zone}>
                <text x={x(i)} y={BASE + 20} fontSize={12.5} fill="var(--ink)">
                  {d.date === today ? "Today" : formatWeekday(d.date)}
                </text>
                <text x={x(i)} y={BASE + 36} fontSize={11} fill="var(--muted)">
                  {formatShortDate(d.date)}
                </text>
                <text x={x(i)} y={BASE + 58} fontSize={13} fontWeight={600} fill={ZONE_COLOR[zone]}>
                  {spread == null ? "–" : `${Math.round(spread)}°`}
                </text>
                <text x={x(i)} y={BASE + 74} fontSize={11} fill={ZONE_COLOR[zone]}>
                  {zone}
                </text>
              </g>
            );
          })}
          <text x={4} y={BASE + 58} fontSize={11} fill="var(--muted)">
            spread
          </text>
        </svg>
      </div>
      <div className="note mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-faint">
        <span>
          <i className="mr-1.5 inline-block h-2 w-3.5 bg-warm" />
          Highs
        </span>
        <span>
          <i className="mr-1.5 inline-block h-2 w-3.5 bg-rain" />
          Lows
        </span>
        <span>
          {highs ? `Thin lines: each of the ${highs.length} runs. ` : ""}Shading: where 8 in 10 runs fall. Spread: how
          far apart those runs put the high.
        </span>
      </div>
    </section>
  );
}
