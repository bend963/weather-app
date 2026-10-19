import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WeatherNextNotice } from "./Dashboard";

describe("WeatherNextNotice", () => {
  it("carries the disclaimer and copyright Google's terms require", () => {
    render(<WeatherNextNotice />);
    expect(screen.getByText(/intended for experimental modelling only/)).toBeInTheDocument();
    expect(screen.getByText(/copyright 2024-6 Google LLC/)).toBeInTheDocument();
  });
});
