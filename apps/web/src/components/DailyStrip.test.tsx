import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { forecastFixture } from "@/test/fixtures";
import { DailyStrip } from "./DailyStrip";

describe("DailyStrip", () => {
  it("shows each day with high, low and rain chance", async () => {
    const onSelect = vi.fn();
    render(<DailyStrip days={forecastFixture.daily} today="2026-10-08" onSelect={onSelect} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(forecastFixture.daily.length);
    expect(screen.getByRole("button", { name: /^Today: high 83°, low/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Tomorrow:/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^Tomorrow:/ }));
    expect(onSelect).toHaveBeenCalledWith(forecastFixture.daily[1]);
  });
});
