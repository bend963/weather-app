"use client";

import type { Location } from "@weather/api-types";
import { useState } from "react";

export function LocationManager({
  locations,
  onMakeDefault,
  onDelete,
}: {
  locations: Location[];
  onMakeDefault: (id: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  async function run(id: string, action: (id: string) => Promise<void>) {
    setBusy(id);
    try {
      await action(id);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="mt-10">
      <button onClick={() => setOpen((o) => !o)} className="label hover:text-ink" aria-expanded={open}>
        Manage locations {open ? "▴" : "▾"}
      </button>
      {open && (
        <ul className="card mt-2 divide-y divide-line rounded-2xl border border-line bg-surface">
          {locations.map((loc) => (
            <li key={loc.id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
              <span className="min-w-0 truncate">
                {loc.name}
                {loc.is_default && <span className="ml-2 text-xs text-muted">Default</span>}
              </span>
              <span className="flex shrink-0 gap-3">
                {!loc.is_default && (
                  <button
                    disabled={busy === loc.id}
                    onClick={() => run(loc.id, onMakeDefault)}
                    className="text-rain hover:underline"
                  >
                    Make default
                  </button>
                )}
                <button
                  disabled={busy === loc.id}
                  onClick={() => {
                    if (window.confirm(`Remove ${loc.name}?`)) void run(loc.id, onDelete);
                  }}
                  className="text-alert hover:underline"
                >
                  Remove
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
