import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { forecastFixture } from "@/test/fixtures";
import { CurrentHeader } from "./CurrentHeader";

describe("CurrentHeader", () => {
  it("shows the location, temperature and details in the location's units", () => {
    render(<CurrentHeader forecast={forecastFixture} />);
    expect(screen.getByRole("heading", { name: "Home" })).toBeInTheDocument();
    expect(screen.getAllByText("75°")[0]).toHaveClass("text-7xl");
    expect(screen.getByText("Mostly cloudy")).toBeInTheDocument();
    expect(screen.getByText("NNE 13 mph")).toBeInTheDocument();
    expect(screen.getByText(/estimated from the nearest forecast hour/)).toBeInTheDocument();
  });

  it("names the station and reading time for a live observation", () => {
    const observed = {
      ...forecastFixture,
      current: {
        ...forecastFixture.current!,
        source: "observation" as const,
        time: "2026-10-08T11:15:00-04:00",
        station: { id: "KMCO", name: "Orlando International Airport", distance_km: 9.2 },
        wind_gust: 22.4,
        condition: { code: "rain", label: "Light Rain" },
      },
    };
    render(<CurrentHeader forecast={observed} />);
    expect(screen.getByText("Light Rain")).toBeInTheDocument();
    expect(screen.getByText("Gusts")).toBeInTheDocument();
    expect(screen.getByText("22 mph")).toBeInTheDocument();
    expect(screen.getByText(/Observed 11:15 AM at Orlando International Airport · 5.7 mi away/)).toBeInTheDocument();
    expect(screen.queryByText(/estimated from the nearest forecast hour/)).not.toBeInTheDocument();
  });
});
