"use client";

import type { DailyForecast } from "@weather/api-types";
import { useState, type PointerEvent } from "react";
import { formatShortDate, formatWeekday } from "@/lib/format";
import {
  DEFAULT_LINES,
  highSpread,
  percentile,
  readLines,
  roughFrom,
  saveLines,
  trustSummary,
  trustZone,
  type LineId,
  type LineToggles,
  type TrustZone,
} from "@/lib/trust";

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

type MemberField = "member_highs" | "member_lows" | "member_dewpoints" | "member_feels_highs" | "member_feels_lows";
type Band = [number | null, number | null, number | null];

/** One drawn quantity: a shaded 10th–90th band, a median line, and optionally every run's line. */
type Track = {
  key: string;
  line: LineId;
  label: string;
  color: string;
  dashed: boolean;
  members: number[][] | null;
  showMembers: boolean;
  bands: Band[];
};

/** Members' values for one field, by member then day, but only if every day has the same number of them. */
function memberLines(days: DailyForecast[], field: MemberField): number[][] | null {
  const first = days[0]?.[field];
  if (!first?.length || days.some((d) => d[field]?.length !== first.length)) return null;
  return first.map((_, m) => days.map((d) => d[field]![m]!));
}

function bandsFromMembers(members: number[][]): Band[] {
  return members[0]!.map((_, i) => {
    const day = members.map((m) => m[i]!);
    return [percentile(day, 10), percentile(day, 50), percentile(day, 90)];
  });
}

function buildTracks(days: DailyForecast[]): Track[] {
  const tracks: Track[] = [];
  const add = (
    key: string,
    line: LineId,
    label: string,
    color: string,
    field: MemberField,
    opts: { dashed?: boolean; showMembers?: boolean; apiBand?: (d: DailyForecast) => Band } = {},
  ) => {
    const members = memberLines(days, field);
    const bands = opts.apiBand ? days.map(opts.apiBand) : members ? bandsFromMembers(members) : null;
    if (!bands) return;
    tracks.push({
      key,
      line,
      label,
      color,
      members,
      bands,
      dashed: opts.dashed ?? false,
      showMembers: opts.showMembers ?? true,
    });
  };
  add("high", "highs", "High", "var(--warm)", "member_highs", { apiBand: (d) => [d.high.p10, d.high.p50, d.high.p90] });
  add("low", "lows", "Low", "var(--rain)", "member_lows", { apiBand: (d) => [d.low.p10, d.low.p50, d.low.p90] });
  add("dew", "dewpoint", "Dewpoint", "var(--dew)", "member_dewpoints");
  // Feels-like rides alongside the highs and lows it shadows, so it skips the
  // per-run lines and is told apart by its dashes.
  add("feels-high", "feels", "Feels-like high", "var(--warm)", "member_feels_highs", {
    dashed: true,
    showMembers: false,
  });
  add("feels-low", "feels", "Feels-like low", "var(--rain)", "member_feels_lows", { dashed: true, showMembers: false });
  return tracks;
}

const LINE_LABEL: Record<LineId, string> = { highs: "Highs", lows: "Lows", dewpoint: "Dewpoint", feels: "Feels like" };
const LINE_SWATCH: Record<LineId, { color: string; dashed: boolean }> = {
  highs: { color: "var(--warm)", dashed: false },
  lows: { color: "var(--rain)", dashed: false },
  dewpoint: { color: "var(--dew)", dashed: false },
  feels: { color: "var(--muted)", dashed: true },
};

/**
 * "How far out can you trust it?": every run's daily high and low across the
 * whole forecast, so you can see where the runs agree and where they fan out.
 * Dewpoint and feels-like can be switched on alongside.
 */
export function TrustView({ days, today, members }: { days: DailyForecast[]; today: string; members?: number | null }) {
  // The dashboard renders on the client after its fetch, so storage is readable here.
  const [lines, setLines] = useState<LineToggles>(() => (typeof window === "undefined" ? DEFAULT_LINES : readLines()));
  const [hover, setHover] = useState<number | null>(null);
  if (days.length < 2) return null;

  const tracks = buildTracks(days);
  const available = new Set(tracks.map((t) => t.line));
  const visible = tracks.filter((t) => lines[t.line]);
  // With everything switched off, keep the axes the highs and lows would use.
  const scaled = visible.length ? visible : tracks.filter((t) => t.line === "highs" || t.line === "lows");
  const values = scaled
    .flatMap((t) => [...t.bands.flat(), ...(t.showMembers && t.members ? t.members.flat() : [])])
    .filter((v): v is number => v != null);
  const lo = Math.floor((Math.min(...values) - 2) / 5) * 5;
  const hi = Math.ceil((Math.max(...values) + 2) / 5) * 5;
  const n = days.length;
  const step = (W - LEFT - RIGHT - 56) / (n - 1);
  const x = (i: number) => LEFT + 28 + step * i;
  const y = (v: number) => BASE - ((BASE - TOP) * (v - lo)) / Math.max(hi - lo, 1);
  const line = (vals: (number | null | undefined)[]) =>
    vals.flatMap((v, i) => (v == null ? [] : [`${x(i)},${y(v)}`])).join(" ");
  const band = (bands: Band[]) =>
    [
      ...bands.map((b, i) => `${x(i)},${y(b[2] ?? b[1] ?? 0)}`),
      ...bands.map((b, i) => `${x(i)},${y(b[0] ?? b[1] ?? 0)}`).reverse(),
    ].join(" ");

  const rough = roughFrom(days);
  const roughX = rough == null ? null : rough === 0 ? LEFT : (x(rough - 1) + x(rough)) / 2;
  const grid: number[] = [];
  for (let v = lo; v <= hi; v += 10) grid.push(v);
  const runs = members ?? tracks[0]?.members?.length;
  const memberCount = visible.find((t) => t.showMembers && t.members)?.members?.length;

  const toggle = (id: LineId) => {
    const next = { ...lines, [id]: !lines[id] };
    setLines(next);
    saveLines(next);
  };

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const svgX = ((e.clientX - box.left) / box.width) * W;
    setHover(Math.max(0, Math.min(n - 1, Math.round((svgX - x(0)) / step))));
  };
  const fmt = (v: number | null) => (v == null ? "–" : `${Math.round(v)}°`);

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
      <div role="group" aria-label="Lines shown" className="mt-3 flex flex-wrap gap-1.5">
        {(Object.keys(LINE_LABEL) as LineId[])
          .filter((id) => available.has(id))
          .map((id) => (
            <button
              key={id}
              type="button"
              aria-pressed={lines[id]}
              onClick={() => toggle(id)}
              className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${
                lines[id]
                  ? "border-line bg-surface-2 text-ink"
                  : "border-dashed border-line text-faint hover:text-muted"
              }`}
            >
              <svg width="16" height="8" aria-hidden="true">
                <line
                  x1="1"
                  x2="15"
                  y1="4"
                  y2="4"
                  stroke={lines[id] ? LINE_SWATCH[id].color : "var(--faint)"}
                  strokeWidth="2.5"
                  strokeDasharray={LINE_SWATCH[id].dashed ? "3 2" : undefined}
                />
              </svg>
              {LINE_LABEL[id]}
            </button>
          ))}
      </div>
      <div className="chart-paper scroll-x -mx-4 mt-2 px-4">
        <div className="relative min-w-[640px]">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={`Daily ${visible.map((t) => t.label.toLowerCase()).join(", ") || "temperatures"} from ${
              runs ? `all ${runs}` : "the"
            } forecast runs over ${n} days`}
            className="block h-auto w-full overflow-visible"
            style={{ fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums" }}
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
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
            {hover != null && (
              <line x1={x(hover)} x2={x(hover)} y1={TOP - 22} y2={BASE} stroke="var(--muted)" strokeOpacity={0.5} />
            )}
            {visible.map((t) => (
              <polygon
                key={t.key}
                data-line={t.line}
                points={band(t.bands)}
                fill={t.color}
                fillOpacity={t.dashed ? 0.08 : 0.16}
              />
            ))}
            {visible.map((t) =>
              t.showMembers
                ? t.members?.map((vals, m) => (
                    <polyline
                      key={`${t.key}-${m}`}
                      data-line={t.line}
                      data-testid="member-line"
                      points={line(vals)}
                      fill="none"
                      stroke={t.color}
                      strokeOpacity={0.22}
                      strokeWidth={1}
                    />
                  ))
                : null,
            )}
            {visible.map((t) => (
              <g key={t.key} data-track={t.key} data-line={t.line}>
                <polyline
                  points={line(t.bands.map((b) => b[1]))}
                  fill="none"
                  stroke={t.color}
                  strokeWidth={t.dashed ? 2 : 2.4}
                  strokeDasharray={t.dashed ? "6 4" : undefined}
                  strokeLinejoin="round"
                />
                {!t.dashed &&
                  t.bands.map((b, i) =>
                    b[1] == null ? null : <circle key={i} cx={x(i)} cy={y(b[1])} r={3} fill={t.color} />,
                  )}
              </g>
            ))}
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
          {hover != null && visible.length > 0 && (
            <div
              role="status"
              className="card pointer-events-none absolute top-0 z-10 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs shadow-sm"
              style={
                x(hover) > W / 2
                  ? { right: `${(1 - (x(hover) - 10) / W) * 100}%` }
                  : { left: `${((x(hover) + 10) / W) * 100}%` }
              }
            >
              <div className="font-semibold">{formatShortDate(days[hover]!.date)}</div>
              {visible.map((t) => {
                const [p10, p50, p90] = t.bands[hover]!;
                return (
                  <div key={t.key} className="whitespace-nowrap text-muted">
                    <span className="text-ink">
                      {t.label} {fmt(p50)}
                    </span>{" "}
                    (most runs {fmt(p10)} to {fmt(p90)})
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
      <p className="note mt-2 text-xs text-faint">
        {memberCount ? `Thin lines: each of the ${memberCount} runs. ` : ""}Shading: where 8 in 10 runs fall.
        {lines.feels && available.has("feels") ? " Dashed: feels like (heat index or wind chill)." : ""} Spread: how far
        apart the runs put the high.
      </p>
    </section>
  );
}
