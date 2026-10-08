import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { StateMessage } from "./StateMessage";

describe("StateMessage", () => {
  it.each([
    ["forecast-processing", "Preparing your forecast"],
    ["forecast-unavailable", "Forecast unavailable"],
    ["provider-unavailable", "Forecast source unavailable"],
    ["location-not-found", "Location not found"],
    ["api-unavailable", "Can't reach the weather service"],
    ["alerts-unavailable", "Official alerts unavailable"],
  ] as const)("renders a friendly %s state", (kind, title) => {
    render(<StateMessage kind={kind} />);
    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
  });

  it("offers a retry", async () => {
    const onRetry = vi.fn();
    render(<StateMessage kind="api-unavailable" onRetry={onRetry} />);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });
});
