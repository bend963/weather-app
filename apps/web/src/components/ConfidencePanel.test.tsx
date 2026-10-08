import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { forecastFixture } from "@/test/fixtures";
import { ConfidencePanel } from "./ConfidencePanel";

describe("ConfidencePanel", () => {
  it("explains temperature and rain confidence separately in plain language", () => {
    render(<ConfidencePanel days={forecastFixture.daily.slice(1, 4)} today="2026-10-08" onSelect={() => {}} />);
    expect(screen.getByText("Tomorrow")).toBeInTheDocument();
    expect(screen.getByText("86–90°F likely")).toBeInTheDocument();
    expect(screen.getAllByText("High confidence").length).toBeGreaterThan(0);
    expect(screen.getByText("Ensemble members disagree")).toBeInTheDocument();
    expect(screen.getByText(/isn.t a guarantee/)).toBeInTheDocument();
  });
});
