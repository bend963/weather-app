import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: replace }) }));

function mockFetch(handler: (url: string, init?: RequestInit) => unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const body = handler(url, init);
      return new Response(JSON.stringify(body), { status: init?.method === "POST" ? 201 : 200 });
    }),
  );
}

const me = (defaultId: string | null) => ({
  visitor: { kind: "anonymous", created_at: "2026-10-08T00:00:00Z" },
  preferences: { temperature_unit: "F", precipitation_unit: "in", wind_unit: "mph", show_advanced_forecast: true },
  location_count: defaultId ? 1 : 0,
  default_location_id: defaultId,
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
  replace.mockReset();
});

describe("Onboarding", () => {
  it("shows onboarding to a new visitor and saves the first location as Home", async () => {
    mockFetch((url) => {
      if (url.includes("/geocode/search")) {
        return [{ name: "Orlando", label: "Orlando, Florida, United States", latitude: 28.54, longitude: -81.38 }];
      }
      if (url.endsWith("/api/v1/locations")) {
        return {
          id: "loc-1",
          name: "Home",
          latitude: 28.54,
          longitude: -81.38,
          timezone: "America/New_York",
          is_default: true,
          created_at: "",
        };
      }
      return me(null);
    });
    const { Onboarding } = await import("./Onboarding");
    render(<Onboarding />);

    expect(await screen.findByText("Your weather.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add your first location" }));
    await userEvent.type(screen.getByPlaceholderText("Search a city or place"), "Orl");
    await userEvent.click(await screen.findByRole("button", { name: /Orlando/ }));
    expect(screen.getByDisplayValue("Home")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save location" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/weather/loc-1"));
    const post = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ name: "Home", latitude: 28.54, longitude: -81.38 });
  });

  it("sends a returning visitor straight to their default location", async () => {
    mockFetch(() => me("loc-9"));
    const { Onboarding } = await import("./Onboarding");
    render(<Onboarding />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/weather/loc-9"));
  });
});
