import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { forecastFixture } from "@/test/fixtures";
import { HourlyStrip } from "./HourlyStrip";

describe("HourlyStrip", () => {
  it("labels hours in the location's timezone", () => {
    render(<HourlyStrip hours={forecastFixture.hourly.slice(0, 24)} timeZone="America/New_York" onSelect={() => {}} />);
    expect(screen.getByText("Now")).toBeInTheDocument();
    // The fixture starts at 11 AM Eastern; the second column is noon.
    expect(screen.getByRole("button", { name: /^12\sPM: / })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(24);
  });
});
