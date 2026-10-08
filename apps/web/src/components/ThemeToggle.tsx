"use client";

import { useState } from "react";

type Theme = "system" | "light" | "dark";
const ORDER: Theme[] = ["system", "light", "dark"];

function readTheme(): Theme {
  try {
    const t = localStorage.getItem("theme");
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

export function ThemeToggle() {
  // The server renders "system"; the client may know better from storage, so
  // the label can differ on hydration (suppressHydrationWarning below).
  const [theme, setTheme] = useState<Theme>(() => (typeof window === "undefined" ? "system" : readTheme()));

  function cycle() {
    const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length]!;
    setTheme(next);
    try {
      if (next === "system") localStorage.removeItem("theme");
      else localStorage.setItem("theme", next);
    } catch {
      /* storage unavailable: still apply for this page view */
    }
    if (next === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = next;
  }

  return (
    <button
      onClick={cycle}
      className="rounded-full px-2.5 py-1 text-xs text-muted hover:bg-surface-2"
      aria-label={`Theme: ${theme}. Change theme`}
      title="Change theme"
      suppressHydrationWarning
    >
      {theme === "system" ? "Auto" : theme === "light" ? "Light" : "Dark"}
    </button>
  );
}
