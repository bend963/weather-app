import type { DailyForecast } from "@weather/api-types";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { forecastFixture } from "@/test/fixtures";
import { rainSummary } from "@/lib/rain";
import { RainSpread } from "./RainSpread";

type Level = "high" | "medium" | "low";

/** Days with the given runs' rain totals (inches) and rain agreement level. */
function rainDays(specs: [number[], Level][]): DailyForecast[] {
  return specs.map(([runs, level], i) => {
    const d = forecastFixture.daily[i]!;
    const pop = runs.filter((v) => v >= 0.01).length / runs.length;
    return {
      ...d,
      precip_probability: pop,
      member_precip: runs,
      confidence: { ...d.confidence, precipitation: { score: 50, level } },
    };
  });
}

const DRY: [number[], Level] = [[0, 0, 0, 0], "high"];

describe("rain summary", () => {
  it("says when every run stays dry", () => {
    expect(rainSummary(rainDays([DRY, DRY, DRY]), "in")).toBe("Nearly every run keeps all 3 days dry.");
  });

  it("says where the runs split and names the best chance", () => {
    const days = rainDays([DRY, DRY, [[0, 0, 0.2, 0.6], "low"], [[0, 0, 0, 0.05], "medium"]]);
    expect(rainSummary(days, "in")).toBe(
      "The runs agree on rain or no rain through Friday, Oct 9. From Saturday, Oct 10 they start to split on whether it rains at all. " +
        "The best chance is Saturday, Oct 10: 2 of 4 runs bring rain, up to 0.60″.",
    );
  });
});

describe("rain summary when every run is wet", () => {
  it("says so instead of calling it a chance", () => {
    const days = rainDays([DRY, [[0.1, 0.2, 0.3, 0.5], "high"]]);
    expect(rainSummary(days, "in")).toMatch(/Friday, Oct 9 is wet in all 4 runs, up to 0\.50″\.$/);
  });
});

describe("RainSpread", () => {
  it("draws a dot for every run on every day", () => {
    const days = rainDays([DRY, DRY, [[0, 0, 0.2, 0.6], "low"]]);
    render(<RainSpread days={days} today="2026-10-08" unit="in" />);
    expect(screen.getByRole("heading", { name: "How sure is the rain?" })).toBeInTheDocument();
    expect(screen.getAllByTestId("rain-run")).toHaveLength(12);
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("stays hidden without the runs' own totals", () => {
    const { container } = render(<RainSpread days={forecastFixture.daily} today="2026-10-08" unit="in" />);
    expect(container).toBeEmptyDOMElement();
  });
});
