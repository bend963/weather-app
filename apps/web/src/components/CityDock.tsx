"use client";

import type { Location } from "@weather/api-types";
import Link from "next/link";
import { ChevronLeft, ChevronRight, GridIcon } from "./Icons";

/**
 * Floating controls at the bottom of a city page: a button for the cities
 * grid, and a pill with the current city and arrows to step through the list.
 */
export function CityDock({ locations, currentId }: { locations: Location[]; currentId: string }) {
  const index = locations.findIndex((l) => l.id === currentId);
  const current = locations[index];
  const prev = index > 0 ? locations[index - 1] : undefined;
  const next = index >= 0 ? locations[index + 1] : undefined;

  return (
    <nav aria-label="Cities" className="dock">
      <Link href="/cities" className="dock-round glass" aria-label="All cities">
        <GridIcon />
      </Link>
      {current && (
        <div className="dock-pill glass">
          <StepLink to={prev} label="Previous city">
            <ChevronLeft />
          </StepLink>
          <div className="dock-name" aria-live="polite">
            <span className="block truncate">{current.name}</span>
            <small>
              {index + 1} of {locations.length}
            </small>
          </div>
          <StepLink to={next} label="Next city">
            <ChevronRight />
          </StepLink>
        </div>
      )}
    </nav>
  );
}

function StepLink({ to, label, children }: { to?: Location; label: string; children: React.ReactNode }) {
  if (!to) {
    return (
      <span className="dock-arrow" aria-hidden="true" data-disabled="">
        {children}
      </span>
    );
  }
  return (
    <Link href={`/weather/${to.id}`} className="dock-arrow" aria-label={`${label}: ${to.name}`}>
      {children}
    </Link>
  );
}
