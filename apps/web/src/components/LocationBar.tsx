"use client";

import type { Location, Units } from "@weather/api-types";
import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";

export function LocationBar({
  locations,
  currentId,
  onAdd,
  units,
  onToggleUnits,
}: {
  locations: Location[];
  currentId?: string;
  onAdd: () => void;
  units?: Units;
  onToggleUnits?: () => void;
}) {
  return (
    <header className="flex items-center gap-3 py-3">
      <nav aria-label="Saved locations" className="scroll-x -ml-1 flex min-w-0 flex-1 gap-1 pl-1">
        {locations.map((loc) => (
          <Link
            key={loc.id}
            href={`/weather/${loc.id}`}
            aria-current={loc.id === currentId ? "page" : undefined}
            className={`shrink-0 rounded-full px-3 py-1 text-sm ${
              loc.id === currentId ? "bg-ink text-bg" : "text-muted hover:bg-surface-2 hover:text-ink"
            }`}
          >
            {loc.name}
          </Link>
        ))}
        <button
          onClick={onAdd}
          className="shrink-0 rounded-full px-3 py-1 text-sm text-muted hover:bg-surface-2 hover:text-ink"
        >
          + Add
        </button>
      </nav>
      {units && onToggleUnits && (
        <button
          onClick={onToggleUnits}
          className="shrink-0 rounded-full px-2.5 py-1 text-xs text-muted hover:bg-surface-2"
          aria-label={`Units: degrees ${units.temperature}. Switch units`}
        >
          °{units.temperature === "F" ? "F" : "C"}
        </button>
      )}
      <ThemeToggle />
    </header>
  );
}
