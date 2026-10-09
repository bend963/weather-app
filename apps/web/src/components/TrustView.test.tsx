import type { DailyForecast } from "@weather/api-types";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { forecastFixture } from "@/test/fixtures";
import { roughFrom, trustSummary } from "@/lib/trust";
import { TrustView } from "./TrustView";

/** The fixture's days, each given three members spread around its median. */
function withMembers(days: DailyForecast[]): DailyForecast[] {
  return days.map((d) => ({
    ...d,
    member_highs: [d.high.p10!, d.high.p50!, d.high.p90!],
    member_lows: [d.low.p10!, d.low.p50!, d.low.p90!],
  }));
}

function withScores(scores: number[]): DailyForecast[] {
  return scores.map((score, i) => {
    const d = forecastFixture.daily[i]!;
    return { ...d, confidence: { ...d.confidence, temperature: { score, level: score >= 65 ? "high" : "low" } } };
  });
}

describe("trust helpers", () => {
  it("marks the rough guide from the start of the last run of weak agreement", () => {
    // A shaky day 2 that recovers doesn't count; days 4 on never recover.
    expect(roughFrom(withScores([90, 80, 40, 70, 45, 30, 20]))).toBe(4);
    expect(roughFrom(withScores([90, 80, 70]))).toBeNull();
    expect(roughFrom(withScores([40, 30]))).toBe(0);
  });

  it("says where the runs stop agreeing", () => {
    const days = forecastFixture.daily;
    // Agreement in the fixture drops below 50 for good on Monday, Oct 12.
    expect(trustSummary(days)).toMatch(/through Sunday, Oct 11\. From Monday, Oct 12 they're \d+ to \d+° apart/);
    expect(trustSummary(withScores([90, 80, 70]))).toMatch(/^The runs stay close on the daily high for all 3 days/);
  });
});

describe("TrustView", () => {
  it("draws every run's line and the rough-guide marker", () => {
    const days = withMembers(forecastFixture.daily);
    render(<TrustView days={days} today="2026-10-08" members={3} />);
    expect(screen.getByRole("heading", { name: "How far out can you trust it?" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /all 3 forecast runs over 15 days/ })).toBeInTheDocument();
    // Three high lines and three low lines.
    expect(screen.getAllByTestId("member-line")).toHaveLength(6);
    expect(screen.getByText("Rough guide only from here")).toBeInTheDocument();
    expect(screen.getByText("Today")).toBeInTheDocument();
  });

  it("falls back to bands only when the runs' own values are missing", () => {
    render(<TrustView days={forecastFixture.daily} today="2026-10-08" />);
    expect(screen.queryAllByTestId("member-line")).toHaveLength(0);
    expect(screen.getByRole("img", { name: /the forecast runs over 15 days/ })).toBeInTheDocument();
    expect(screen.queryByText(/Thin lines/)).not.toBeInTheDocument();
  });

  it("renders nothing for a single day", () => {
    const { container } = render(<TrustView days={forecastFixture.daily.slice(0, 1)} today="2026-10-08" />);
    expect(container).toBeEmptyDOMElement();
  });
});
