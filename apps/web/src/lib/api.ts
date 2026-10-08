import type {
  ApiErrorBody,
  Forecast,
  ForecastHistory,
  Location,
  LocationCreate,
  LocationUpdate,
  Me,
  Place,
  Preferences,
  PreferencesUpdate,
} from "@weather/api-types";

/**
 * Browser API client. Requests go to this site's own origin and are proxied
 * to FastAPI (see next.config.ts), so the visitor cookie stays first-party.
 */
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export type ApiFailureKind = "network" | "not_found" | "rate_limited" | "invalid" | "server";

export class ApiFailure extends Error {
  constructor(
    public kind: ApiFailureKind,
    message: string,
    public status?: number,
    public code?: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      credentials: "include",
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch {
    throw new ApiFailure("network", "We can't reach the weather service right now.");
  }
  if (response.status === 204) return undefined as T;
  if (!response.ok) {
    let body: ApiErrorBody | undefined;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = undefined;
    }
    const message = body?.error?.message ?? "Something went wrong.";
    const kind: ApiFailureKind =
      response.status === 404
        ? "not_found"
        : response.status === 429
          ? "rate_limited"
          : response.status < 500
            ? "invalid"
            : "server";
    throw new ApiFailure(kind, message, response.status, body?.error?.code);
  }
  return (await response.json()) as T;
}

const json = (body: unknown) => JSON.stringify(body);

// The first call to /me issues the visitor cookie. Every page awaits it before
// making other calls, so parallel first requests can't create two visitors.
let mePromise: Promise<Me> | null = null;

export const api = {
  me(force = false): Promise<Me> {
    if (!mePromise || force) {
      mePromise = request<Me>("/api/v1/me").catch((error) => {
        mePromise = null;
        throw error;
      });
    }
    return mePromise;
  },
  updatePreferences: (body: PreferencesUpdate) =>
    request<Preferences>("/api/v1/me/preferences", { method: "PATCH", body: json(body) }),
  listLocations: () => request<Location[]>("/api/v1/locations"),
  createLocation: (body: LocationCreate) =>
    request<Location>("/api/v1/locations", { method: "POST", body: json(body) }),
  updateLocation: (id: string, body: LocationUpdate) =>
    request<Location>(`/api/v1/locations/${id}`, { method: "PATCH", body: json(body) }),
  deleteLocation: (id: string) => request<void>(`/api/v1/locations/${id}`, { method: "DELETE" }),
  forecast: (id: string, hours = 72) => request<Forecast>(`/api/v1/locations/${id}/forecast?hours=${hours}`),
  history: (id: string, params: { target_date?: string; target_time?: string; metric?: string }) => {
    const query = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => Boolean(e[1])));
    return request<ForecastHistory>(`/api/v1/locations/${id}/forecast-history?${query}`);
  },
  searchPlaces: (q: string) => request<Place[]>(`/api/v1/geocode/search?q=${encodeURIComponent(q)}`),
  reverseGeocode: (lat: number, lon: number) => request<Place | null>(`/api/v1/geocode/reverse?lat=${lat}&lon=${lon}`),
};
