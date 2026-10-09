"use client";

import type { DailyForecast, Units } from "@weather/api-types";
import { useState, type PointerEvent } from "react";
import { formatPop, formatPrecip, formatShortDate, formatWeekday } from "@/lib/format";
import { rainBand, rainSummary, rainZone, wetThreshold, type RainZone } from "@/lib/rain";

const W = 1000;
const H = 300;
const LEFT = 52;
const RIGHT = 12;
const TOP = 14;
const BASE = 220;

const ZONE_COLOR: Record<RainZone, string> = { agree: "var(--ok)", split: "var(--mid)", "toss-up": "var(--alert)" };

// Gridlines on a square-root scale: small amounts stay visible next to a downpour.
const TICKS: Record<Units["precipitation"], number[]> = {
  in: [0, 0.1, 0.25, 0.5, 1, 2, 4, 8],
  mm: [0, 2.5, 5, 10, 25, 50, 100, 200],
};

/**
 * How sure is the rain? Each run's rain total for every day, so you can see
 * where the runs agree it's dry or wet and where they split.
 */
export function RainSpread({
  days,
  today,
  unit,
}: {
  days: DailyForecast[];
  today: string;
  unit: Units["precipitation"];
}) {
  const [hover, setHover] = useState<number | null>(null);
  if (days.length < 2 || !days.every((d) => d.member_precip?.length)) return null;

  const n = days.length;
  const runs = days[0]!.member_precip!.length;
  const max = Math.max(...days.flatMap((d) => d.member_precip!));
  const ticks = TICKS[unit];
  const top = ticks.find((t) => t >= max && t >= ticks[2]!) ?? ticks[ticks.length - 1]!;
  const step = (W - LEFT - RIGHT - 56) / (n - 1);
  const x = (i: number) => LEFT + 28 + step * i;
  const y = (v: number) => BASE - (BASE - TOP) * Math.sqrt(Math.min(v, top) / top);
  const wet = wetThreshold(unit);
  const fmt = (v: number) => (v < wet ? "0" : formatPrecip(v, unit));

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const svgX = ((e.clientX - box.left) / box.width) * W;
    setHover(Math.max(0, Math.min(n - 1, Math.round((svgX - x(0)) / step))));
  };

  return (
    <section aria-labelledby="rain-spread" className="dash-section mt-8">
      <div className="flex items-baseline justify-between">
        <h2 id="rain-spread" className="label">
          How sure is the rain?
        </h2>
        <span className="note hidden text-xs text-faint sm:inline">Each run&apos;s rain total per day, {n} days</span>
      </div>
      <p className="mt-2 max-w-[62ch] text-[15px] leading-normal">{rainSummary(days, unit)}</p>
      <div className="chart-paper scroll-x -mx-4 mt-2 px-4">
        <div className="relative min-w-[640px]">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={`Daily rain totals from all ${runs} forecast runs over ${n} days`}
            className="block h-auto w-full overflow-visible"
            style={{ fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums" }}
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          >
            {ticks
              .filter((t) => t <= top)
              .map((t) => (
                <g key={t}>
                  <line x1={LEFT} x2={W - RIGHT} y1={y(t)} y2={y(t)} stroke="var(--line)" />
                  <text x={LEFT - 6} y={y(t) + 4} textAnchor="end" fontSize={12} fill="var(--muted)">
                    {t === 0 ? "0" : unit === "in" ? `${t}″` : `${t}`}
                  </text>
                </g>
              ))}
            {hover != null && (
              <rect
                x={x(hover) - step / 2}
                y={TOP}
                width={step}
                height={BASE - TOP}
                fill="var(--ink)"
                fillOpacity={0.05}
              />
            )}
            {days.map((d, i) => {
              const [p10, p50, p90] = rainBand(d)!;
              const zone = rainZone(d);
              return (
                <g key={d.date} data-day={d.date}>
                  <rect
                    x={x(i) - 7}
                    y={y(p90)}
                    width={14}
                    height={Math.max(y(p10) - y(p90), 2)}
                    rx={4}
                    fill="var(--rain)"
                    fillOpacity={0.16}
                  />
                  {d.member_precip!.map((v, m) => (
                    <circle
                      key={m}
                      data-testid="rain-run"
                      // A fixed sideways nudge per run so runs with the same total don't hide each other.
                      cx={x(i) + (((m * 7) % 11) - 5) * 2.4}
                      cy={y(v)}
                      r={2.6}
                      fill="var(--rain)"
                      fillOpacity={0.5}
                    />
                  ))}
                  <line x1={x(i) - 11} x2={x(i) + 11} y1={y(p50)} y2={y(p50)} stroke="var(--rain)" strokeWidth={2.4} />
                  <g textAnchor="middle">
                    <text x={x(i)} y={BASE + 20} fontSize={12.5} fill="var(--ink)">
                      {d.date === today ? "Today" : formatWeekday(d.date)}
                    </text>
                    <text x={x(i)} y={BASE + 36} fontSize={11} fill="var(--muted)">
                      {formatShortDate(d.date)}
                    </text>
                    <text x={x(i)} y={BASE + 58} fontSize={13} fontWeight={600} fill={ZONE_COLOR[zone]}>
                      {formatPop(d.precip_probability)}
                    </text>
                    <text x={x(i)} y={BASE + 74} fontSize={11} fill={ZONE_COLOR[zone]}>
                      {zone}
                    </text>
                  </g>
                </g>
              );
            })}
            <text x={4} y={BASE + 58} fontSize={11} fill="var(--muted)">
              chance
            </text>
          </svg>
          {hover != null &&
            (() => {
              const d = days[hover]!;
              const [p10, p50, p90] = rainBand(d)!;
              const wetRuns = d.member_precip!.filter((v) => v >= wet).length;
              return (
                <div
                  role="status"
                  className="card pointer-events-none absolute top-0 z-10 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs shadow-sm"
                  style={
                    x(hover) > W / 2
                      ? { right: `${(1 - (x(hover) - step / 2) / W) * 100}%` }
                      : { left: `${((x(hover) + step / 2) / W) * 100}%` }
                  }
                >
                  <div className="font-semibold">{formatShortDate(d.date)}</div>
                  <div className="whitespace-nowrap text-muted">
                    <span className="text-ink">
                      {wetRuns} of {runs} runs
                    </span>{" "}
                    bring rain
                  </div>
                  <div className="whitespace-nowrap text-muted">
                    <span className="text-ink">Middle run {fmt(p50)}</span> (most runs {fmt(p10)} to {fmt(p90)})
                  </div>
                  <div className="whitespace-nowrap text-muted">Wettest run {fmt(Math.max(...d.member_precip!))}</div>
                </div>
              );
            })()}
        </div>
      </div>
      <p className="note mt-2 text-xs text-faint">
        Dots: each run&apos;s rain for the day (midnight to midnight). Bar: where 8 in 10 runs fall; line: the middle
        run. Chance: share of runs with at least {unit === "in" ? "0.01″" : "0.25 mm"}.
      </p>
    </section>
  );
}
