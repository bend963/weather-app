"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AddLocationDialog } from "./AddLocationDialog";
import { StateMessage } from "./StateMessage";

/** "/": onboarding for new visitors, otherwise straight to the default location. */
export function Onboarding() {
  const router = useRouter();
  const [phase, setPhase] = useState<"loading" | "empty" | "error">("loading");
  const [adding, setAdding] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .me(attempt > 0)
      .then((me) => {
        if (cancelled) return;
        if (me.default_location_id) router.replace(`/weather/${me.default_location_id}`);
        else setPhase("empty");
      })
      .catch(() => !cancelled && setPhase("error"));
    return () => {
      cancelled = true;
    };
  }, [router, attempt]);

  if (phase === "error") {
    return <StateMessage kind="api-unavailable" onRetry={() => setAttempt((a) => a + 1)} />;
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col justify-center px-6">
      {phase === "loading" && <p className="text-center text-sm text-muted">Loading…</p>}
      {phase === "empty" && (
        <>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
            Your weather.
            <br />
            <span className="text-muted">With uncertainty included.</span>
          </h1>
          <p className="mt-4 max-w-md text-[15px] text-muted">
            See the most likely forecast, the range it could fall in, and how much the forecast models agree.
          </p>
          <div>
            <button
              onClick={() => setAdding(true)}
              className="mt-8 rounded-full bg-ink px-5 py-2.5 text-sm font-medium text-bg"
            >
              Add your first location
            </button>
          </div>
          <p className="mt-4 text-xs text-faint">No account needed. Locations are saved privately to this browser.</p>
        </>
      )}
      {adding && (
        <AddLocationDialog
          onClose={() => setAdding(false)}
          suggestedName="Home"
          onSaved={(loc) => router.replace(`/weather/${loc.id}`)}
        />
      )}
    </main>
  );
}
