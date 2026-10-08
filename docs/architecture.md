# Architecture notes

## Request flow

1. The browser loads the Next.js app from Vercel and calls `/api/v1/...` on the
   same origin. `next.config.ts` rewrites those calls to the FastAPI service.
2. The first call (`GET /api/v1/me`) creates a `visitors` row and sets the
   `weather_visitor` cookie. The client awaits it before other calls so parallel
   first requests can't create two visitors.
3. Every saved-location route derives the owner from the cookie
   (`weather_api.visitors`). Request bodies that include `visitor_id` are
   rejected (`extra="forbid"`). Another visitor's location returns the same 404
   as a nonexistent id.

## Anonymous identity

* Cookie value: `<uuid>.<HMAC-SHA256(uuid, COOKIE_SECRET)>`. Opaque, no personal
  data. `HttpOnly`, `SameSite=Lax`, `Secure` in production, one-year `Max-Age`,
  refreshed at most every 12 h together with `visitors.last_seen_at`.
* The signature means a client can't forge or guess an id; an invalid cookie is
  simply ignored.
* Read endpoints never create visitors (bots don't fill the table).

## Ownership and future accounts

`saved_locations` has nullable `visitor_id` and `user_id` with a check
constraint that exactly one is set. Queries go through `Owner.owns()`, so adding
authenticated users means resolving a request to `Owner(user_id=…)`. Signup
transfers rows with `UPDATE saved_locations SET visitor_id = NULL, user_id = :new
WHERE visitor_id = :visitor`. Organizations would add `organizations` and
`organization_members` plus an `organization_id` owner column under the same
constraint; forecast tables are unaffected.

A partial unique index allows at most one default location per owner. The first
saved location becomes the default; deleting the default promotes the oldest
remaining one.

## Grid points

`weather_api.grid.normalize_to_grid` snaps a coordinate to the nearest node of
the 0.25° grid and produces a stable identifier (`"<lat_index>:<lon_index>"`,
longitude on 0–360 so the dateline is continuous). `(model_name,
model_grid_identifier)` is unique, and creation is an `INSERT … ON CONFLICT DO
UPDATE`, so concurrent saves in one cell share one row.

Each grid point stores a timezone, used to group hours into local days. If the
node sits offshore (where only fixed `Etc/GMT±N` zones exist), the saved
location's real zone is used so daily summaries follow daylight saving time.

A grid point is `active` while saved locations reference it. The worker's
`deactivate-unused` command turns off points unreferenced for
`GRID_POINT_INACTIVE_DAYS`; their history is kept.

## Ingestion

`weather_api.forecast.ingestion.run_ingestion` is used by both the Cloud Run Job
and the API (to backfill a newly saved location immediately, as a background
task). For each of the latest `INGESTION_BACKFILL_RUNS` initializations, newest
first:

1. Upsert the `forecast_runs` row for (model, initialization_time).
2. Find active grid points with no rows in that run.
3. Fetch members from the provider in batches of 100 points, compute
   statistics, insert hourly and daily rows with `ON CONFLICT DO NOTHING`.
   One point's rows for a run are committed together.
4. Mark the run `complete` (or `failed`, with an `error_category`; the next
   invocation retries the missing points).

Idempotency comes from unique constraints, so concurrent or repeated runs can't
duplicate or overwrite data. Existing runs are never modified.

## Reading forecasts

`read_model.latest_run_for_point` picks the newest non-failed run that contains
the point. Loaded forecasts are cached in-process keyed by `(grid point, run)`;
that data is immutable, and the key is shared by everyone in the cell. Swap
`weather_api.cache.TTLCache` for Redis when traffic warrants it.

The forecast response carries `Cache-Control: private, max-age≤300` and an ETag
covering location, run, units and the current hour; `If-None-Match` gets a 304.

`ForecastPresenter` converts SI to the visitor's units and writes the plain-
language confidence summaries. It is the only place units are converted.

## Current conditions

WeatherNext forecasts; it doesn't observe. `CurrentConditionsProvider` is the
seam: today `NearestForecastHour` returns the closest forecast hour with
`source="forecast"` (and the UI says so). An observations-backed provider (NWS,
METAR, personal stations) can replace it without API or UI changes.

## Logging and privacy

Logs are JSON lines (Cloud Logging format) with `request_id`, route template,
status, duration, `forecast_run_id`, `grid_point_id`, provider and
`error_category`. Query strings, request bodies, coordinates and cookies are
never logged; uvicorn's access log is disabled for that reason. Validation errors
name the bad fields without echoing values. Unhandled errors return a generic
message with the request id.

Coordinates entered with "Use my current location" are rounded to 3 decimals
(~100 m) in the browser before saving; forecasts are on a ~25 km grid, so
nothing is lost.

## Rate limits

Location creation (per visitor) and geocoding (per client IP) use an in-process
sliding window. That is per Cloud Run instance; a shared limit needs Redis or
Cloud Armor later. Each owner can save at most 50 locations.
