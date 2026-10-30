import { describe, expect, it } from "vitest";
import { frameLabel, inMosaic, LOOP_MINUTES, mosaicTileUrl, nearestRadar, radarLoopUrl, radarPageUrl } from "./radar";

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

describe("IEM radar mosaic", () => {
  it("builds tile URLs for now and for past frames", () => {
    expect(mosaicTileUrl(0, 7)).toBe(
      "https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913/{z}/{x}/{y}.png?t=7",
    );
    expect(mosaicTileUrl(5, 7)).toContain("/nexrad-n0q-900913-m05m/{z}/{x}/{y}.png");
    expect(mosaicTileUrl(50, 7)).toContain("/nexrad-n0q-900913-m50m/");
  });

  it("loops 50 minutes, oldest first, ending now", () => {
    expect(LOOP_MINUTES[0]).toBe(50);
    expect(LOOP_MINUTES.at(-1)).toBe(0);
    expect(LOOP_MINUTES).toHaveLength(11);
  });

  it("covers the lower 48 only", () => {
    expect(inMosaic(28.54, -81.38)).toBe(true); // Orlando
    expect(inMosaic(43.68, -98.86)).toBe(true); // Kimball, SD
    expect(inMosaic(61.22, -149.9)).toBe(false); // Anchorage
    expect(inMosaic(21.31, -157.86)).toBe(false); // Honolulu
  });

  it("labels frames", () => {
    expect(frameLabel(0)).toBe("Now");
    expect(frameLabel(35)).toBe("35 min ago");
  });
});
