export type Theme = "system" | "light" | "dark";

export const THEMES: { id: Theme; name: string }[] = [
  { id: "system", name: "Auto" },
  { id: "light", name: "Light" },
  { id: "dark", name: "Dark" },
];

export function readTheme(): Theme {
  try {
    const t = localStorage.getItem("theme");
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(theme: Theme) {
  try {
    if (theme === "system") localStorage.removeItem("theme");
    else localStorage.setItem("theme", theme);
  } catch {
    /* storage unavailable: still apply for this page view */
  }
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}
