import { describe, expect, it } from "vitest";
import { nearestRadar, radarLoopUrl, radarPageUrl } from "./radar";

describe("nearest radar", () => {
  it.each([
    ["Orlando", 28.54, -81.38, "KMLB"],
    ["Kimball, SD", 43.75, -98.96, "KFSD"],
    ["New York City", 40.71, -74.01, "KDIX"],
    ["Honolulu", 21.31, -157.86, "PHMO"],
  ])("picks the closest site for %s", (_, lat, lon, id) => {
    expect(nearestRadar(lat, lon)?.id).toBe(id);
  });

  it("measures the distance to the site", () => {
    // KMLB (Melbourne, FL) is about 85 km from downtown Orlando.
    const km = nearestRadar(28.54, -81.38)!.km;
    expect(km).toBeGreaterThan(75);
    expect(km).toBeLessThan(95);
  });

  it("returns nothing where no NWS radar reaches", () => {
    expect(nearestRadar(51.51, -0.13)).toBeNull();
  });
});

describe("radar urls", () => {
  it("points at the NWS loop and station page", () => {
    expect(radarLoopUrl("KMLB")).toBe("https://radar.weather.gov/ridge/standard/KMLB_loop.gif");
    expect(radarLoopUrl("KMLB", 42)).toBe("https://radar.weather.gov/ridge/standard/KMLB_loop.gif?t=42");
    expect(radarPageUrl("KMLB")).toBe("https://radar.weather.gov/station/kmlb/standard");
  });
});
