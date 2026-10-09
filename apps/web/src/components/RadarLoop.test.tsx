import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RadarLoop } from "./RadarLoop";

describe("RadarLoop", () => {
  it("shows the nearest site's loop and how far away it is", () => {
    render(<RadarLoop latitude={40.71} longitude={-74.01} miles />);
    expect(screen.getByRole("heading", { name: "Radar now" })).toBeInTheDocument();
    const img = screen.getByRole("img", { name: /NWS radar KDIX/ });
    expect(img.getAttribute("src")).toMatch(/^https:\/\/radar\.weather\.gov\/ridge\/standard\/KDIX_loop\.gif\?t=\d+$/);
    expect(screen.getByText(/KDIX, \d+ mi away/)).toBeInTheDocument();
  });

  it("uses kilometres for metric units", () => {
    render(<RadarLoop latitude={40.71} longitude={-74.01} miles={false} />);
    expect(screen.getByText(/KDIX, \d+ km away/)).toBeInTheDocument();
  });

  it("links to radar.weather.gov when the loop fails to load", () => {
    render(<RadarLoop latitude={28.54} longitude={-81.38} miles />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByTestId("radar-fallback")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open KMLB on radar\.weather\.gov/ })).toHaveAttribute(
      "href",
      "https://radar.weather.gov/station/kmlb/standard",
    );
  });

  it("renders nothing outside NWS radar coverage", () => {
    const { container } = render(<RadarLoop latitude={51.51} longitude={-0.13} miles={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
