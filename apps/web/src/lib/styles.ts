/**
 * Dashboard visual styles. Each one is a set of CSS overrides keyed on
 * data-style on <html> (see app/styles.css); "original" sets no attribute.
 */
export const STYLES = [
  { id: "original", name: "Original" },
  { id: "timetable", name: "Timetable" },
  { id: "letter", name: "Letter" },
  { id: "dusk", name: "Dusk" },
  { id: "recorder", name: "Chart recorder" },
  { id: "poster", name: "Poster" },
  { id: "annotated", name: "Annotated" },
] as const;

export type StyleId = (typeof STYLES)[number]["id"];

export const STYLE_KEY = "style";

export function isStyleId(value: unknown): value is StyleId {
  return STYLES.some((s) => s.id === value);
}

export function readStyle(): StyleId {
  try {
    const s = localStorage.getItem(STYLE_KEY);
    return isStyleId(s) ? s : "original";
  } catch {
    return "original";
  }
}

export function applyStyle(style: StyleId) {
  try {
    if (style === "original") localStorage.removeItem(STYLE_KEY);
    else localStorage.setItem(STYLE_KEY, style);
  } catch {
    /* storage unavailable: still apply for this page view */
  }
  if (style === "original") delete document.documentElement.dataset.style;
  else document.documentElement.dataset.style = style;
}
