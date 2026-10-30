import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RadarLoop } from "./RadarLoop";

// Leaflet needs a real browser; the map itself is covered by the end-to-end tests.
vi.mock("./RadarMap", () => ({
  RadarMap: ({ onFail }: { onFail: () => void }) => (
    <div role="region" aria-label="Radar map">
      <button onClick={onFail}>fail</button>
    </div>
  ),
}));

describe("RadarLoop", () => {
  it("shows the radar map in the lower 48 states", () => {
    render(<RadarLoop latitude={40.71} longitude={-74.01} miles />);
    expect(screen.getByRole("heading", { name: "Radar now" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Radar map" })).toBeInTheDocument();
    expect(screen.getByText("NEXRAD mosaic, last 50 min")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Full radar controls/ })).toHaveAttribute(
      "href",
      "https://radar.weather.gov/station/kdix/standard",
    );
  });

  it("falls back to the nearest site's loop when the map's tiles don't load", () => {
    render(<RadarLoop latitude={40.71} longitude={-74.01} miles />);
    fireEvent.click(screen.getByRole("button", { name: "fail" }));
    const img = screen.getByRole("img", { name: /NWS radar KDIX/ });
    expect(img.getAttribute("src")).toMatch(/^https:\/\/radar\.weather\.gov\/ridge\/standard\/KDIX_loop\.gif\?t=\d+$/);
    expect(screen.getByText(/KDIX, \d+ mi away/)).toBeInTheDocument();
  });

  it("uses the nearest site's loop outside the mosaic, in kilometres for metric units", () => {
    render(<RadarLoop latitude={21.31} longitude={-157.86} miles={false} />);
    expect(screen.getByRole("img", { name: /NWS radar PHMO|NWS radar PHKI|NWS radar PH/ })).toBeInTheDocument();
    expect(screen.getByText(/PH\w+, \d+ km away/)).toBeInTheDocument();
  });

  it("links to radar.weather.gov when the site loop fails to load", () => {
    render(<RadarLoop latitude={21.31} longitude={-157.86} miles />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByTestId("radar-fallback")).toBeInTheDocument();
  });

  it("renders nothing outside NWS radar coverage", () => {
    const { container } = render(<RadarLoop latitude={51.51} longitude={-0.13} miles={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
