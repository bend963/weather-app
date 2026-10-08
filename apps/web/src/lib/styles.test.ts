import { afterEach, describe, expect, it } from "vitest";
import { applyStyle, isStyleId, readStyle } from "./styles";

describe("dashboard styles", () => {
  afterEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.style;
  });

  it("recognizes only known style ids", () => {
    expect(isStyleId("poster")).toBe(true);
    expect(isStyleId("comic-sans")).toBe(false);
    expect(isStyleId(null)).toBe(false);
  });

  it("applies and remembers a style", () => {
    applyStyle("letter");
    expect(document.documentElement.dataset.style).toBe("letter");
    expect(readStyle()).toBe("letter");
  });

  it("clears the attribute and storage for the original style", () => {
    applyStyle("dusk");
    applyStyle("original");
    expect(document.documentElement.dataset.style).toBeUndefined();
    expect(readStyle()).toBe("original");
  });

  it("ignores an unknown stored value", () => {
    localStorage.setItem("style", "neon");
    expect(readStyle()).toBe("original");
  });
});
