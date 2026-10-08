"use client";

import { useState } from "react";
import { applyStyle, isStyleId, readStyle, STYLES, type StyleId } from "@/lib/styles";

export function StylePicker() {
  // Like ThemeToggle, the server renders the default and the client may know
  // better from storage (suppressHydrationWarning below).
  const [style, setStyle] = useState<StyleId>(() => (typeof window === "undefined" ? "original" : readStyle()));

  return (
    <label className="flex shrink-0 items-center gap-1 text-xs text-muted">
      <span className="sr-only sm:not-sr-only">Style</span>
      <select
        value={style}
        onChange={(e) => {
          if (!isStyleId(e.target.value)) return;
          setStyle(e.target.value);
          applyStyle(e.target.value);
        }}
        className="rounded-full bg-transparent px-1.5 py-1 text-xs text-muted hover:bg-surface-2"
        suppressHydrationWarning
      >
        {STYLES.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
    </label>
  );
}
