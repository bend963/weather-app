import Link from "next/link";

export type StateKind =
  | "forecast-unavailable"
  | "forecast-processing"
  | "provider-unavailable"
  | "location-not-found"
  | "api-unavailable"
  | "alerts-unavailable";

const COPY: Record<StateKind, { title: string; body: string }> = {
  "forecast-processing": {
    title: "Preparing your forecast",
    body: "This location is new to us. Its forecast is being processed and will appear in a moment.",
  },
  "forecast-unavailable": {
    title: "Forecast unavailable",
    body: "There's no forecast for this location yet. Please try again shortly.",
  },
  "provider-unavailable": {
    title: "Forecast source unavailable",
    body: "The forecast model data can't be reached right now. Your saved locations are safe.",
  },
  "location-not-found": {
    title: "Location not found",
    body: "This location isn't saved in this browser. It may have been removed.",
  },
  "api-unavailable": {
    title: "Can't reach the weather service",
    body: "Check your connection, or try again in a minute.",
  },
  "alerts-unavailable": {
    title: "Official alerts unavailable",
    body: "We couldn't check the National Weather Service for alerts. Check weather.gov for warnings.",
  },
};

export function StateMessage({
  kind,
  onRetry,
  message,
}: {
  kind: StateKind;
  onRetry?: () => void;
  message?: string | null;
}) {
  const copy = COPY[kind];
  return (
    <div role="status" className="mx-auto max-w-md py-16 text-center">
      {kind === "forecast-processing" && (
        <div className="mx-auto mb-5 h-1 w-24 overflow-hidden rounded bg-line">
          <div className="h-full w-1/3 animate-pulse rounded bg-rain" />
        </div>
      )}
      <h2 className="text-lg font-semibold">{copy.title}</h2>
      <p className="mt-2 text-sm text-muted">{message ?? copy.body}</p>
      <div className="mt-5 flex justify-center gap-3 text-sm">
        {onRetry && (
          <button onClick={onRetry} className="rounded-full border border-line px-4 py-1.5 hover:bg-surface-2">
            Try again
          </button>
        )}
        {kind === "location-not-found" && (
          <Link href="/" className="rounded-full border border-line px-4 py-1.5 hover:bg-surface-2">
            Go to my locations
          </Link>
        )}
      </div>
    </div>
  );
}
