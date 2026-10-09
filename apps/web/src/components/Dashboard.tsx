"use client";

import type { Forecast, Location } from "@weather/api-types";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiFailure } from "@/lib/api";
import { formatCycle, localDate } from "@/lib/format";
import { AddLocationDialog } from "./AddLocationDialog";
import { ConfidencePanel } from "./ConfidencePanel";
import { CurrentHeader } from "./CurrentHeader";
import { DailyStrip } from "./DailyStrip";
import { DetailDrawer, type DrawerItem } from "./DetailDrawer";
import { HourlyStrip } from "./HourlyStrip";
import { LocationBar } from "./LocationBar";
import { LocationManager } from "./LocationManager";
import { RainOutlookCard } from "./RainOutlookCard";
import { RainSpread } from "./RainSpread";
import { StateMessage, type StateKind } from "./StateMessage";
import { TrustView } from "./TrustView";

const POLL_MS = 2000;
const MAX_POLLS = 30;

export function Dashboard({ locationId }: { locationId: string }) {
  const router = useRouter();
  const [locations, setLocations] = useState<Location[]>([]);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [state, setState] = useState<StateKind | null>(null);
  const [adding, setAdding] = useState(false);
  const [drawer, setDrawer] = useState<DrawerItem | null>(null);
  const [reload, setReload] = useState(0);

  const refreshLocations = useCallback(async () => {
    setLocations(await api.listLocations());
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let polls = 0;

    async function load() {
      try {
        await api.me();
        const [locs, fc] = await Promise.all([api.listLocations(), api.forecast(locationId)]);
        if (cancelled) return;
        setLocations(locs);
        setForecast(fc);
        if (fc.status === "ok") {
          setState(null);
        } else if (fc.status === "processing" && polls < MAX_POLLS) {
          setState("forecast-processing");
          polls += 1;
          timer = setTimeout(load, POLL_MS);
        } else {
          setState(fc.status === "unavailable" ? "provider-unavailable" : "forecast-unavailable");
        }
      } catch (e) {
        if (cancelled) return;
        setForecast(null);
        setState(e instanceof ApiFailure && e.kind === "not_found" ? "location-not-found" : "api-unavailable");
      }
    }
    void load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [locationId, reload]);

  async function toggleUnits() {
    if (!forecast) return;
    const metric = forecast.units.temperature === "F";
    await api.updatePreferences(
      metric
        ? { temperature_unit: "C", precipitation_unit: "mm", wind_unit: "kmh" }
        : { temperature_unit: "F", precipitation_unit: "in", wind_unit: "mph" },
    );
    setReload((r) => r + 1);
  }

  async function makeDefault(id: string) {
    await api.updateLocation(id, { is_default: true });
    await refreshLocations();
  }

  async function remove(id: string) {
    await api.deleteLocation(id);
    const remaining = await api.listLocations();
    setLocations(remaining);
    if (id === locationId) {
      const next = remaining.find((l) => l.is_default) ?? remaining[0];
      router.replace(next ? `/weather/${next.id}` : "/");
    }
  }

  const ready = forecast?.status === "ok" ? forecast : null;
  const tz = ready?.location.timezone ?? "UTC";
  const today = ready?.current ? localDate(ready.current.time, tz) : (ready?.daily[0]?.date ?? "");

  return (
    <div className="page mx-auto max-w-3xl px-4 pb-16">
      <LocationBar
        locations={locations}
        currentId={locationId}
        onAdd={() => setAdding(true)}
        units={ready?.units}
        onToggleUnits={toggleUnits}
      />

      {state && (
        <StateMessage
          kind={state}
          message={state === "provider-unavailable" ? forecast?.message : undefined}
          onRetry={state === "location-not-found" ? undefined : () => setReload((r) => r + 1)}
        />
      )}

      {!state && !ready && <div className="py-24 text-center text-sm text-muted">Loading forecast…</div>}

      {ready && (
        <main>
          <CurrentHeader forecast={ready} />
          <HourlyStrip
            hours={ready.hourly.slice(0, 24)}
            timeZone={tz}
            onSelect={(hour) => setDrawer({ kind: "hour", hour })}
          />
          {ready.rain_outlook && (
            <div className="mt-8">
              <RainOutlookCard outlook={ready.rain_outlook} units={ready.units} />
            </div>
          )}
          <DailyStrip days={ready.daily} today={today} onSelect={(day) => setDrawer({ kind: "day", day })} />
          <TrustView days={ready.daily} today={today} members={ready.summary?.members} />
          <RainSpread days={ready.daily} today={today} unit={ready.units.precipitation} />
          <ConfidencePanel
            days={ready.daily.slice(1, 4)}
            today={today}
            onSelect={(day) => setDrawer({ kind: "day", day })}
          />
          <footer className="mt-10 flex flex-wrap items-center justify-between gap-3 text-xs text-faint">
            <span>
              {ready.model_run?.model === "mock_weathernext"
                ? "Mock ensemble (development data)"
                : ready.model_run?.model}
              {ready.model_run && ` · run ${formatCycle(ready.model_run.initialization_time)}`}
              {ready.summary?.members ? ` · ${ready.summary.members} members` : ""}
            </span>
            <Link href={`/weather/${locationId}/history`} className="text-rain hover:underline">
              How has this forecast changed? →
            </Link>
          </footer>
          <LocationManager locations={locations} onMakeDefault={makeDefault} onDelete={remove} />
        </main>
      )}

      <DetailDrawer
        item={drawer}
        onClose={() => setDrawer(null)}
        units={ready?.units ?? { temperature: "F", precipitation: "in", wind: "mph" }}
        run={ready?.model_run}
        timeZone={tz}
      />
      {adding && (
        <AddLocationDialog
          onClose={() => setAdding(false)}
          onSaved={(loc) => {
            setAdding(false);
            router.push(`/weather/${loc.id}`);
          }}
        />
      )}
    </div>
  );
}
