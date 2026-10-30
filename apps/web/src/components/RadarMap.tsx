"use client";

import type * as Leaflet from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import { frameLabel, LOOP_MINUTES, mosaicTileUrl } from "@/lib/radar";

/** IEM refreshes the mosaic every 5 minutes. */
const REFRESH_MS = 5 * 60 * 1000;
const FRAME_MS = 550;
const HOLD_LAST_MS = 1600;
const RADAR_OPACITY = 0.75;
const LAST = LOOP_MINUTES.length - 1;

const stampNow = () => Math.floor(Date.now() / REFRESH_MS);

function isDark() {
  const theme = document.documentElement.dataset.theme;
  if (theme === "dark" || theme === "light") return theme === "dark";
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

/**
 * A zoomable map centred on the location with a 50-minute radar loop on top.
 * Leaflet only runs in the browser, so it is loaded inside an effect.
 */
export function RadarMap({ latitude, longitude, onFail }: { latitude: number; longitude: number; onFail: () => void }) {
  const el = useRef<HTMLDivElement>(null);
  const layers = useRef<Leaflet.TileLayer[]>([]);
  const [frame, setFrame] = useState(LAST);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);

  // Build the map once per location.
  useEffect(() => {
    let map: Leaflet.Map | undefined;
    let refresh: ReturnType<typeof setInterval> | undefined;
    let cancelled = false;

    void import("leaflet").then((mod) => {
      const L = (mod as unknown as { default?: typeof Leaflet }).default ?? (mod as typeof Leaflet);
      if (cancelled || !el.current) return;
      const touch = window.matchMedia?.("(pointer: coarse)").matches ?? false;
      map = L.map(el.current, {
        center: [latitude, longitude],
        zoom: 7,
        minZoom: 4,
        maxZoom: 10,
        // Don't trap page scrolling: no wheel zoom, and on phones no one-finger
        // drag. Pinch and the +/- buttons still zoom.
        scrollWheelZoom: false,
        dragging: !touch,
        attributionControl: true,
      });
      map.attributionControl.setPrefix(false);

      // Esri's gray canvas: keyless public tiles, with light and dark versions
      // and a separate place-name layer we can draw above the radar.
      const tone = isDark() ? "dark" : "light";
      const canvas = (kind: "Base" | "Reference") =>
        `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_${tone === "dark" ? "Dark" : "Light"}_Gray_${kind}/MapServer/tile/{z}/{y}/{x}`;
      L.tileLayer(canvas("Base"), {
        attribution: "Base map &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors",
        maxNativeZoom: 16,
      }).addTo(map);

      // Radar sits between the base map and its place names.
      map.createPane("labels").style.zIndex = "450";
      map.getPane("labels")!.style.pointerEvents = "none";

      const stamp = stampNow();
      let loaded = 0;
      let failed = 0;
      layers.current = LOOP_MINUTES.map((minutes, i) => {
        const layer = L.tileLayer(mosaicTileUrl(minutes, stamp), {
          opacity: i === LAST ? RADAR_OPACITY : 0,
          attribution:
            i === LAST
              ? 'Radar: NWS via <a href="https://mesonet.agron.iastate.edu/">IEM</a>'
              : undefined,
        });
        if (i === LAST) {
          layer.on("tileload", () => (loaded += 1));
          layer.on("tileerror", () => {
            failed += 1;
            if (loaded === 0 && failed >= 4) onFail();
          });
        }
        return layer.addTo(map!);
      });

      L.tileLayer(canvas("Reference"), { pane: "labels", maxNativeZoom: 16 }).addTo(map);
      L.circleMarker([latitude, longitude], {
        radius: 5,
        weight: 2,
        color: tone === "dark" ? "#ececea" : "#16171a",
        fillColor: tone === "dark" ? "#16171a" : "#ffffff",
        fillOpacity: 1,
        pane: "labels",
        interactive: false,
      }).addTo(map);

      refresh = setInterval(() => {
        const next = stampNow();
        LOOP_MINUTES.forEach((minutes, i) => layers.current[i]?.setUrl(mosaicTileUrl(minutes, next)));
      }, REFRESH_MS);

      setReady(true);
      const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
      setPlaying(!still);
    });

    return () => {
      cancelled = true;
      if (refresh) clearInterval(refresh);
      map?.remove();
      layers.current = [];
    };
  }, [latitude, longitude, onFail]);

  // Show one frame at a time.
  useEffect(() => {
    layers.current.forEach((layer, i) => layer.setOpacity(i === frame ? RADAR_OPACITY : 0));
  }, [frame, ready]);

  // Step through the frames, pausing on the latest.
  useEffect(() => {
    if (!playing) return;
    const timer = setTimeout(
      () => setFrame((f) => (f + 1) % LOOP_MINUTES.length),
      frame === LAST ? HOLD_LAST_MS : FRAME_MS,
    );
    return () => clearTimeout(timer);
  }, [playing, frame]);

  const minutes = LOOP_MINUTES[frame]!;
  return (
    <div>
      <div ref={el} role="region" aria-label="Radar map" className="radar-map h-80 w-full bg-surface-2 sm:h-96" />
      <div className="flex items-center gap-3 border-t border-line px-3 py-2">
        <button
          onClick={() => setPlaying((p) => !p)}
          disabled={!ready}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-2 text-ink"
          aria-label={playing ? "Pause radar loop" : "Play radar loop"}
        >
          {playing ? (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true">
              <rect x="2.5" y="2" width="3" height="10" rx="1" />
              <rect x="8.5" y="2" width="3" height="10" rx="1" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true">
              <path d="M3.5 2.2v9.6a.6.6 0 0 0 .9.5l7.6-4.8a.6.6 0 0 0 0-1L4.4 1.7a.6.6 0 0 0-.9.5z" />
            </svg>
          )}
        </button>
        <input
          type="range"
          min={0}
          max={LAST}
          step={1}
          value={frame}
          disabled={!ready}
          onChange={(e) => {
            setPlaying(false);
            setFrame(Number(e.target.value));
          }}
          aria-label="Radar time"
          aria-valuetext={frameLabel(minutes)}
          className="min-w-0 flex-1 accent-[var(--rain)]"
        />
        <span className="w-20 shrink-0 text-right text-xs tabular-nums text-muted" aria-live="off">
          {frameLabel(minutes)}
        </span>
      </div>
    </div>
  );
}
