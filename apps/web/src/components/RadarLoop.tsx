"use client";

import { useEffect, useState } from "react";
import { nearestRadar, radarLoopUrl, radarPageUrl } from "@/lib/radar";

/** NWS regenerates each loop every few minutes; fetch a fresh one this often. */
const REFRESH_MS = 5 * 60 * 1000;

const stampNow = () => Math.floor(Date.now() / REFRESH_MS);

/** The live NWS radar loop from the site nearest the location. */
export function RadarLoop({ latitude, longitude, miles }: { latitude: number; longitude: number; miles: boolean }) {
  const site = nearestRadar(latitude, longitude);
  const [stamp, setStamp] = useState(stampNow);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      setFailed(false);
      setStamp(stampNow());
    }, REFRESH_MS);
    return () => clearInterval(timer);
  }, []);

  if (!site) return null;
  const distance = miles ? `${Math.round(site.km / 1.609)} mi` : `${Math.round(site.km)} km`;
  const page = radarPageUrl(site.id);

  return (
    <section aria-labelledby="radar-loop" className="dash-section mt-8">
      <div className="flex items-baseline justify-between">
        <h2 id="radar-loop" className="label">
          Radar now
        </h2>
        <span className="note text-xs text-faint">
          {site.id}, {distance} away
        </span>
      </div>
      <div className="mt-3 overflow-hidden rounded-xl border border-line bg-surface">
        {failed ? (
          <p className="px-4 py-10 text-center text-sm text-muted" data-testid="radar-fallback">
            The radar loop didn&apos;t load.{" "}
            <a href={page} target="_blank" rel="noreferrer" className="text-rain hover:underline">
              Open {site.id} on radar.weather.gov →
            </a>
          </p>
        ) : (
          // A plain <img>: the animated GIF comes straight from the NWS, not through Next's image optimizer.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={radarLoopUrl(site.id, stamp)}
            alt={`Animated radar loop from NWS radar ${site.id}`}
            width={600}
            height={550}
            loading="lazy"
            className="block h-auto w-full"
            onError={() => setFailed(true)}
          />
        )}
      </div>
      <p className="note mt-2 text-xs text-faint">
        Reflectivity loop from the National Weather Service, refreshed every 5 minutes.{" "}
        <a href={page} target="_blank" rel="noreferrer" className="text-rain hover:underline">
          Full radar controls →
        </a>
      </p>
    </section>
  );
}
