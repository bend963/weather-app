"use client";

import type { Forecast, Location, Units } from "@weather/api-types";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiFailure } from "@/lib/api";
import { formatTemp } from "@/lib/format";
import { lastCity } from "@/lib/lastCity";
import { AddLocationDialog } from "./AddLocationDialog";
import { CloseIcon, GearIcon, PlusIcon } from "./Icons";
import { SettingsSheet } from "./SettingsSheet";
import { StateMessage } from "./StateMessage";
import { WeatherIcon } from "./WeatherIcon";

type Summary = Forecast | "loading" | "error";

/** "/cities": every saved city as a tile. Hold and drag a tile to reorder. */
export function CitiesView() {
  const router = useRouter();
  const [locations, setLocations] = useState<Location[] | null>(null);
  const [summaries, setSummaries] = useState<Record<string, Summary>>({});
  const [units, setUnits] = useState<Units["temperature"]>();
  const [failed, setFailed] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [settings, setSettings] = useState(false);
  const [adding, setAdding] = useState(false);
  const [reload, setReload] = useState(0);
  const [closeTo, setCloseTo] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const me = await api.me(reload > 0);
        const locs = await api.listLocations();
        if (cancelled) return;
        setUnits(me.preferences.temperature_unit);
        setLocations(locs);
        setFailed(false);
        const remembered = lastCity();
        setCloseTo(locs.find((l) => l.id === remembered)?.id ?? locs[0]?.id ?? null);
        setSummaries(Object.fromEntries(locs.map((l) => [l.id, "loading"])));
        for (const loc of locs) {
          api
            .forecast(loc.id, 24)
            .then((fc) => !cancelled && setSummaries((s) => ({ ...s, [loc.id]: fc })))
            .catch(() => !cancelled && setSummaries((s) => ({ ...s, [loc.id]: "error" })));
        }
      } catch {
        if (!cancelled) setFailed(true);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reload]);

  const saveOrder = useCallback(async (ids: string[], previous: Location[]) => {
    try {
      setLocations(await api.reorderLocations(ids));
      setNotice(null);
    } catch (e) {
      setLocations(previous);
      setNotice(e instanceof ApiFailure ? e.message : "Couldn't save the new order.");
    }
  }, []);

  async function changeUnits(unit: Units["temperature"]) {
    await api.updatePreferences(
      unit === "C"
        ? { temperature_unit: "C", precipitation_unit: "mm", wind_unit: "kmh" }
        : { temperature_unit: "F", precipitation_unit: "in", wind_unit: "mph" },
    );
    setReload((r) => r + 1);
  }

  if (failed) return <StateMessage kind="api-unavailable" onRetry={() => setReload((r) => r + 1)} />;

  return (
    <div className="page mx-auto max-w-3xl px-4 pb-32">
      <header className="flex items-center justify-between pt-3">
        <h1 className="text-3xl font-bold tracking-tight">Cities</h1>
        <button
          onClick={() => setSettings(true)}
          className="-mr-2 rounded-full p-2 text-muted hover:bg-surface-2 hover:text-ink"
          aria-label="Settings: style, appearance and units"
        >
          <GearIcon size={24} />
        </button>
      </header>

      {locations && locations.length > 1 && (
        <p className="mt-1 text-sm text-muted">
          Hold and drag a city to move it. The first city opens when you start the app.
        </p>
      )}
      {notice && (
        <p role="alert" className="mt-3 text-sm text-alert">
          {notice}
        </p>
      )}

      {!locations ? (
        <p className="py-24 text-center text-sm text-muted">Loading cities…</p>
      ) : (
        <CityGrid
          locations={locations}
          summaries={summaries}
          currentId={closeTo}
          onReorder={(ids) => {
            const previous = locations;
            const byId = new Map(locations.map((l) => [l.id, l]));
            setLocations(ids.map((id) => byId.get(id)!));
            void saveOrder(ids, previous);
          }}
          onAdd={() => setAdding(true)}
        />
      )}

      {closeTo && (
        <nav aria-label="Cities" className="dock">
          <Link href={`/weather/${closeTo}`} className="dock-round glass" aria-label="Close cities">
            <CloseIcon />
          </Link>
        </nav>
      )}

      {settings && <SettingsSheet onClose={() => setSettings(false)} temperature={units} onChangeUnits={changeUnits} />}
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

type Drag = {
  id: string;
  pointerId: number;
  mouse: boolean;
  startX: number;
  startY: number;
  /** Slot rectangles in list order, measured when the press began. */
  slots: DOMRect[];
  startIndex: number;
  active: boolean;
  timer?: ReturnType<typeof setTimeout>;
};

const HOLD_MS = 300;
const MOVE_SLOP = 8;

function CityGrid({
  locations,
  summaries,
  currentId,
  onReorder,
  onAdd,
}: {
  locations: Location[];
  summaries: Record<string, Summary>;
  currentId: string | null;
  onReorder: (ids: string[]) => void;
  onAdd: () => void;
}) {
  const [order, setOrderState] = useState(() => locations.map((l) => l.id));
  const [dragging, setDragging] = useState<string | null>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [announce, setAnnounce] = useState("");
  const drag = useRef<Drag | null>(null);
  const suppressClick = useRef(false);
  const tiles = useRef(new Map<string, HTMLElement>());
  // Capture on the list, which never moves, rather than on a tile React re-inserts.
  const list = useRef<HTMLUListElement>(null);
  // Pointer handlers read the latest order from here, between renders.
  const orderRef = useRef(order);
  const setOrder = useCallback((ids: string[]) => {
    orderRef.current = ids;
    setOrderState(ids);
  }, []);

  // Follow the saved list (after a save, a reload, or a revert) when not dragging.
  const key = locations.map((l) => l.id).join();
  useEffect(() => {
    if (!drag.current?.active) setOrder(key ? key.split(",") : []);
  }, [key, setOrder]);

  // Once a drag starts, stop the page from scrolling under the finger.
  useEffect(() => {
    const block = (e: TouchEvent) => {
      if (drag.current?.active) e.preventDefault();
    };
    document.addEventListener("touchmove", block, { passive: false });
    return () => document.removeEventListener("touchmove", block);
  }, []);

  const byId = new Map(locations.map((l) => [l.id, l]));

  function activate(d: Drag) {
    d.active = true;
    setDragging(d.id);
    try {
      list.current?.setPointerCapture(d.pointerId);
    } catch {
      /* the pointer already ended */
    }
    navigator.vibrate?.(10);
  }

  function end(commit: boolean) {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    clearTimeout(d.timer);
    if (!d.active) return;
    suppressClick.current = true;
    setTimeout(() => (suppressClick.current = false), 0);
    setDragging(null);
    setOffset({ x: 0, y: 0 });
    const ids = orderRef.current;
    if (commit && ids.join() !== key) onReorder(ids);
    else setOrder(key.split(","));
  }

  function onPointerDown(e: React.PointerEvent, id: string) {
    if (e.button !== 0 || drag.current) return;
    const slots = orderRef.current.map((i) => tiles.current.get(i)!.getBoundingClientRect());
    const d: Drag = {
      id,
      pointerId: e.pointerId,
      mouse: e.pointerType === "mouse",
      startX: e.clientX,
      startY: e.clientY,
      slots,
      startIndex: orderRef.current.indexOf(id),
      active: false,
    };
    if (!d.mouse) d.timer = setTimeout(() => drag.current === d && activate(d), HOLD_MS);
    drag.current = d;
  }

  function onPointerMove(e: React.PointerEvent) {
    const d = drag.current;
    if (!d || e.pointerId !== d.pointerId) return;
    const dx = e.clientX - d.startX;
    const dy = e.clientY - d.startY;
    if (!d.active) {
      if (Math.hypot(dx, dy) < MOVE_SLOP) return;
      if (d.mouse) activate(d);
      else return end(false); // a touch that moves before the hold is a scroll
    }
    const target = nearestSlot(d.slots, e.clientX, e.clientY);
    let ids = orderRef.current;
    const from = ids.indexOf(d.id);
    if (target !== from) {
      ids = move(ids, from, target);
      setOrder(ids);
    }
    const slot = d.slots[ids.indexOf(d.id)]!;
    const home = d.slots[d.startIndex]!;
    setOffset({ x: dx - (slot.left - home.left), y: dy - (slot.top - home.top) });
  }

  function onKeyDown(e: React.KeyboardEvent, id: string) {
    if (!e.altKey) return;
    const step = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const from = order.indexOf(id);
    const to = Math.max(0, Math.min(order.length - 1, from + step));
    if (to === from) return;
    const ids = move(order, from, to);
    setOrder(ids);
    setAnnounce(`${byId.get(id)?.name} moved to position ${to + 1} of ${ids.length}`);
    onReorder(ids);
    requestAnimationFrame(() => tiles.current.get(id)?.focus());
  }

  return (
    <>
      <ul
        ref={list}
        className="city-grid mt-4"
        aria-label="Your cities"
        onPointerMove={onPointerMove}
        onPointerUp={() => end(true)}
        onPointerCancel={() => end(false)}
      >
        {order.map((id, i) => {
          const loc = byId.get(id);
          if (!loc) return null;
          const lifted = dragging === id;
          return (
            <li
              key={id}
              style={lifted ? { transform: `translate(${offset.x}px, ${offset.y}px)`, zIndex: 10 } : undefined}
            >
              <Link
                ref={(el) => {
                  if (el) tiles.current.set(id, el);
                  else tiles.current.delete(id);
                }}
                href={`/weather/${id}`}
                className={`city-tile${id === currentId ? " is-current" : ""}${lifted ? " is-lifted" : ""}`}
                aria-describedby="reorder-help"
                aria-label={`${loc.name}, ${i + 1} of ${order.length}`}
                draggable={false}
                onPointerDown={(e) => onPointerDown(e, id)}
                onContextMenu={(e) => dragging && e.preventDefault()}
                onKeyDown={(e) => onKeyDown(e, id)}
                onClick={(e) => suppressClick.current && e.preventDefault()}
              >
                <TileBody location={loc} summary={summaries[id]} />
              </Link>
            </li>
          );
        })}
        <li>
          <button onClick={onAdd} className="city-tile city-tile-add">
            <PlusIcon size={26} />
            Add city
          </button>
        </li>
      </ul>
      <p id="reorder-help" className="sr-only">
        Hold and drag to move. With a keyboard, press Alt and an arrow key.
      </p>
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
    </>
  );
}

function TileBody({ location, summary }: { location: Location; summary: Summary | undefined }) {
  const fc = summary && summary !== "loading" && summary !== "error" && summary.status === "ok" ? summary : null;
  const today = fc?.daily[0];
  const time = new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: location.timezone,
  }).format(new Date());
  const status =
    summary === "error"
      ? "Forecast unavailable"
      : summary && summary !== "loading" && summary.status === "processing"
        ? "Getting forecast…"
        : null;
  return (
    <>
      <span className="min-w-0">
        <span className="block truncate text-base font-semibold">{location.name}</span>
        <span className="block truncate text-xs text-muted">
          {time}
          {fc?.current && ` · ${fc.current.condition.label}`}
        </span>
      </span>
      {fc?.current ? (
        <span>
          <span className="flex items-end justify-between gap-2">
            <span className="hero-temp text-5xl font-light leading-none tracking-tighter">
              {formatTemp(fc.current.temperature)}
            </span>
            <WeatherIcon code={fc.current.condition.code} size={30} className="text-muted" />
          </span>
          {today && (
            <span className="mt-1.5 block text-xs text-muted">
              H {formatTemp(today.high.p50)} L {formatTemp(today.low.p50)}
            </span>
          )}
        </span>
      ) : (
        <span className="text-xs text-muted">{status ?? "Loading…"}</span>
      )}
    </>
  );
}

function nearestSlot(slots: DOMRect[], x: number, y: number) {
  let best = 0;
  let bestDist = Infinity;
  slots.forEach((r, i) => {
    const d = Math.hypot(r.left + r.width / 2 - x, r.top + r.height / 2 - y);
    if (d < bestDist) {
      best = i;
      bestDist = d;
    }
  });
  return best;
}

function move<T>(list: T[], from: number, to: number): T[] {
  const next = list.slice();
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item!);
  return next;
}
