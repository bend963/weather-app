import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { forecastFixture } from "@/test/fixtures";
import { RainOutlookCard } from "./RainOutlookCard";

describe("RainOutlookCard", () => {
  it("shows the next likely rain with expected and high-end amounts", () => {
    render(<RainOutlookCard outlook={forecastFixture.rain_outlook!} units={forecastFixture.units} />);
    expect(screen.getByText("Rain likely Monday, 12 AM–2 PM")).toBeInTheDocument();
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.getByText("0.24″")).toBeInTheDocument();
    expect(screen.getByText("0.58″")).toBeInTheDocument();
  });

  it("says so when no rain is likely", () => {
    render(
      <RainOutlookCard
        outlook={{ next_rain: null, summary: "No rain likely in the next 7 days", horizon_hours: 168 }}
        units={forecastFixture.units}
      />,
    );
    expect(screen.getByText("No rain likely in the next 7 days")).toBeInTheDocument();
  });
});
