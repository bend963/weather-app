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
});
