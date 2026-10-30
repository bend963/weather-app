"use client";

import type { Units } from "@weather/api-types";
import { useEffect, useState } from "react";
import { applyStyle, readStyle, STYLES, type StyleId } from "@/lib/styles";
import { applyTheme, readTheme, THEMES, type Theme } from "@/lib/theme";

/** The gear sheet on the cities page: page style, light/dark, and units. */
export function SettingsSheet({
  onClose,
  temperature,
  onChangeUnits,
}: {
  onClose: () => void;
  temperature?: Units["temperature"];
  onChangeUnits: (unit: Units["temperature"]) => Promise<void>;
}) {
  const [style, setStyle] = useState<StyleId>(readStyle);
  const [theme, setTheme] = useState<Theme>(readTheme);
  const [savingUnits, setSavingUnits] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/30 sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        onClick={(e) => e.stopPropagation()}
        className="sheet max-h-[85dvh] w-full max-w-md overflow-y-auto rounded-t-3xl border border-line bg-surface p-5 shadow-xl sm:rounded-3xl"
      >
        <div className="flex items-baseline justify-between">
          <h2 id="settings-title" className="text-lg font-semibold">
            Settings
          </h2>
          <button onClick={onClose} className="text-sm text-muted hover:text-ink">
            Done
          </button>
        </div>

        <fieldset className="mt-5">
          <legend className="label">Style</legend>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {STYLES.map((s) => (
              <button
                key={s.id}
                aria-pressed={style === s.id}
                onClick={() => {
                  setStyle(s.id);
                  applyStyle(s.id);
                }}
                className={`rounded-xl border px-3 py-2.5 text-left text-sm ${
                  style === s.id ? "border-ink bg-ink text-bg" : "border-line hover:bg-surface-2"
                }`}
              >
                {s.name}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="mt-5">
          <legend className="label">Appearance</legend>
          <Segmented
            options={THEMES}
            value={theme}
            onChange={(t) => {
              setTheme(t);
              applyTheme(t);
            }}
          />
        </fieldset>

        <fieldset className="mt-5">
          <legend className="label">Units</legend>
          <Segmented
            options={[
              { id: "F", name: "°F, inches, mph" },
              { id: "C", name: "°C, mm, km/h" },
            ]}
            value={temperature}
            disabled={savingUnits || !temperature}
            onChange={async (u) => {
              setSavingUnits(true);
              try {
                await onChangeUnits(u);
              } finally {
                setSavingUnits(false);
              }
            }}
          />
        </fieldset>
      </div>
    </div>
  );
}

function Segmented<T extends string>({
  options,
  value,
  onChange,
  disabled,
}: {
  options: { id: T; name: string }[];
  value: T | undefined;
  onChange: (value: T) => void;
  disabled?: boolean;
}) {
  return (
    <div className="mt-2 flex rounded-xl bg-surface-2 p-1">
      {options.map((o) => (
        <button
          key={o.id}
          aria-pressed={value === o.id}
          disabled={disabled}
          onClick={() => value !== o.id && onChange(o.id)}
          className={`flex-1 rounded-lg px-2 py-1.5 text-sm ${
            value === o.id ? "bg-surface font-medium text-ink shadow-sm" : "text-muted"
          }`}
        >
          {o.name}
        </button>
      ))}
    </div>
  );
}
