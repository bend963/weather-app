"use client";

import type { Location, Place } from "@weather/api-types";
import { useEffect, useId, useState } from "react";
import { api, ApiFailure } from "@/lib/api";

type Selected = { name: string; label: string; latitude: number; longitude: number };

// Forecasts are computed on a ~25 km grid, so there's no forecast benefit to
// storing a device's exact position. Rounding to 3 decimals (~100 m) keeps a
// saved "Home" from pinpointing a house.
const roundCoord = (x: number) => Math.round(x * 1000) / 1000;

/** Render only while open; each opening starts with fresh state. */
export function AddLocationDialog({
  onClose,
  onSaved,
  suggestedName,
}: {
  onClose: () => void;
  onSaved: (location: Location) => void;
  suggestedName?: string;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Place[]>([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState<Selected | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const titleId = useId();
  const searchable = !selected && query.trim().length >= 2;

  useEffect(() => {
    if (!searchable) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const places = await api.searchPlaces(query.trim());
        if (!cancelled) {
          setResults(places);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiFailure ? e.message : "Search failed.");
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, searchable]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const visibleResults = searchable ? results : [];

  function choose(place: Selected) {
    setSelected(place);
    setName(suggestedName ?? place.name);
  }

  function useMyLocation() {
    if (!("geolocation" in navigator)) {
      setError("Your browser can't share its location.");
      return;
    }
    setError(null);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const latitude = roundCoord(pos.coords.latitude);
        const longitude = roundCoord(pos.coords.longitude);
        let place: Place | null = null;
        try {
          place = await api.reverseGeocode(latitude, longitude);
        } catch {
          place = null;
        }
        choose({
          name: place?.name ?? "Current location",
          label: place?.label ?? "Your current location",
          latitude,
          longitude,
        });
      },
      () => setError("Location permission was denied. Search for a place instead."),
      { maximumAge: 600_000, timeout: 10_000 },
    );
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || !name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const location = await api.createLocation({
        name: name.trim(),
        latitude: selected.latitude,
        longitude: selected.longitude,
      });
      onSaved(location);
    } catch (err) {
      setError(err instanceof ApiFailure ? err.message : "Couldn't save this location.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-start sm:pt-[12vh]"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="w-full max-w-md rounded-t-2xl border border-line bg-surface p-5 shadow-xl sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-baseline justify-between">
          <h2 id={titleId} className="text-base font-semibold">
            Add a location
          </h2>
          <button onClick={onClose} className="text-sm text-muted hover:text-ink" aria-label="Close">
            Close
          </button>
        </div>

        {!selected ? (
          <>
            <label className="mt-4 block">
              <span className="sr-only">Search for a place</span>
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search a city or place"
                className="w-full rounded-lg border border-line bg-bg px-3 py-2.5 text-[15px] outline-none focus:border-rain"
                autoComplete="off"
              />
            </label>
            <ul className="mt-2 max-h-72 overflow-y-auto" aria-label="Search results">
              {visibleResults.map((place) => (
                <li key={`${place.latitude},${place.longitude},${place.label}`}>
                  <button
                    onClick={() => choose(place)}
                    className="w-full rounded-lg px-3 py-2 text-left hover:bg-surface-2"
                  >
                    <div className="text-[15px]">{place.name}</div>
                    <div className="truncate text-xs text-muted">{place.label}</div>
                  </button>
                </li>
              ))}
              {searching && visibleResults.length === 0 && <li className="px-3 py-2 text-sm text-muted">Searching…</li>}
              {!searching && searchable && visibleResults.length === 0 && !error && (
                <li className="px-3 py-2 text-sm text-muted">No matches yet.</li>
              )}
            </ul>
            <button onClick={useMyLocation} className="mt-2 text-sm text-rain hover:underline">
              Use my current location
            </button>
          </>
        ) : (
          <form onSubmit={save} className="mt-4">
            <div className="rounded-lg bg-surface-2 px-3 py-2">
              <div className="text-[15px]">{selected.label}</div>
              <button type="button" onClick={() => setSelected(null)} className="text-xs text-muted hover:text-ink">
                Choose a different place
              </button>
            </div>
            <label className="mt-4 block text-sm">
              <span className="label">Name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={80}
                placeholder="Home, Lake House…"
                className="mt-1 w-full rounded-lg border border-line bg-bg px-3 py-2.5 text-[15px] outline-none focus:border-rain"
              />
            </label>
            <p className="mt-2 text-xs text-muted">Saved privately to this browser. No account needed.</p>
            <button
              type="submit"
              disabled={saving || !name.trim()}
              className="mt-4 w-full rounded-full bg-ink px-4 py-2.5 text-sm font-medium text-bg disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save location"}
            </button>
          </form>
        )}
        {error && (
          <p role="alert" className="mt-3 text-sm text-alert">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
