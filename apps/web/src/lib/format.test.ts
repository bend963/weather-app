import { describe, expect, it } from "vitest";
import {
  formatCycle,
  formatHour,
  formatPop,
  formatPrecip,
  formatTemp,
  formatWind,
  localDate,
  relativeDay,
} from "./format";

describe("format", () => {
  it("rounds temperatures", () => {
    expect(formatTemp(78.4)).toBe("78°");
    expect(formatTemp(-0.4)).toBe("0°");
    expect(formatTemp(null)).toBe("–");
    expect(formatTemp(21.6, true, "C")).toBe("22°C");
  });

  it("formats precipitation in inches and millimetres", () => {
    expect(formatPrecip(0.18, "in")).toBe("0.18″");
    expect(formatPrecip(0.004, "in")).toBe("<0.01″");
    expect(formatPrecip(4.6, "mm")).toBe("4.6 mm");
  });

  it("rounds rain chance to tens", () => {
    expect(formatPop(0.74)).toBe("70%");
    expect(formatPop(0.05)).toBe("10%");
    expect(formatPop(0.04)).toBe("0%");
  });

  it("formats wind with direction", () => {
    expect(formatWind(8.2, "mph", "NE")).toBe("NE 8 mph");
    expect(formatWind(3, "kmh")).toBe("3 km/h");
  });

  it("shows times in the location's timezone, not the browser's", () => {
    const iso = "2026-10-08T22:00:00Z";
    expect(formatHour(iso, "America/New_York")).toBe("6 PM");
    expect(formatHour(iso, "America/Denver")).toBe("4 PM");
    expect(localDate("2026-10-09T02:00:00Z", "America/Denver")).toBe("2026-10-08");
  });

  it("labels days relative to the location's today", () => {
    expect(relativeDay("2026-10-08", "2026-10-08")).toBe("Today");
    expect(relativeDay("2026-10-09", "2026-10-08")).toBe("Tomorrow");
    expect(relativeDay("2026-10-10", "2026-10-08")).toBe("Sat");
  });

  it("names model cycles in UTC", () => {
    expect(formatCycle("2026-10-08T00:00:00+00:00")).toBe("00Z Oct 8");
    expect(formatCycle("2026-10-07T20:00:00-04:00")).toBe("00Z Oct 8");
  });
});
