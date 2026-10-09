# WeatherNext Personal Weather

A personal weather web app built around probabilistic forecasts. Instead of a
single number, it shows the most likely value, the likely range, the chance and
amount of rain, and how much the forecast's ensemble members agree, in plain
language. Every model run is kept, so you can see how a forecast evolved.

Forecast data will come from Google DeepMind **WeatherNext**. Until access is
granted, a deterministic **mock ensemble provider** drives the entire app, so
everything works locally with no Google credentials.

**Status:** Milestones 1–3 of the v1 spec (skeleton, locations, mock weather)
plus a working dashboard, history page, tests, Docker, CI and deploy config.
WeatherNext (M5) and NWS alerts (M6) are next; see [docs/roadmap.md](docs/roadmap.md).

---

## Architecture

```
                         ┌──────────────────────────────┐
  Browser ──HTTPS──────▶ │  Vercel: Next.js (apps/web)  │
  weather_visitor cookie │  pages + /api/v1/* proxy     │  rewrites keep the cookie first-party
                         └──────────────┬───────────────┘
                                        │ /api/v1/*
                                        ▼
                         ┌──────────────────────────────┐        ┌───────────────────────┐
                         │ Cloud Run service: FastAPI   │──────▶ │ Geocoder (Nominatim / │
                         │ (apps/api)                   │        │ static; Places later) │
                         │ visitors, locations,         │        └───────────────────────┘
                         │ forecast + history read API  │
                         └──────┬───────────────▲───────┘
                     SQL        │               │ backfill a new grid point
                                ▼               │ (same ingestion code)
                         ┌──────────────────────┴───────┐
                         │ PostgreSQL (Supabase or      │
                         │ Cloud SQL)                   │
                         │ ownership tables │ forecast  │
                         │ (private)        │ tables    │
                         └──────────────────▲───────────┘
                                            │ idempotent upserts
  Cloud Scheduler ──hourly──▶ ┌─────────────┴────────────────┐      ┌──────────────────────┐
                              │ Cloud Run Job: ingestion     │────▶ │ ForecastProvider     │
                              │ (workers/forecast-ingestion) │      │  mock │ WeatherNext  │
                              └──────────────────────────────┘      │ (BigQuery)           │
                                                                    └──────────────────────┘
```

| Path | What it is |
| --- | --- |
| `apps/web` | Next.js 16 + React 19 + Tailwind 4 + Recharts. Dashboard, history, onboarding. |
| `apps/api` | FastAPI service **and** the shared forecast domain code (providers, ensemble statistics, ingestion), plus Alembic migrations. |
| `workers/forecast-ingestion` | Thin CLI used as the Cloud Run Job: `run`, `migrate`, `deactivate-unused`. |
| `packages/api-types` | TypeScript types generated from the API's OpenAPI schema. |
| `packages/config` | Shared TypeScript config. |
| `infra/` | Cloud Run deploy/bootstrap scripts, GitHub and database notes. |
| `docs/` | Architecture notes, forecast methodology, WeatherNext integration plan, roadmap. |

There are exactly three deployables: one web app, one API, one worker. No microservices.

## Local setup

Prerequisites: Docker (for the one-command path), or Python 3.12+ with
[uv](https://docs.astral.sh/uv/), Node 22, and a local Postgres 16.

**One command (Docker):**

```bash
git clone <repo-url> weather-app
cd weather-app
make dev            # same as: docker compose up --build
```

Open http://localhost:3000, add a location, and the forecast appears. API docs
are at http://localhost:8000/docs. Docker Compose runs Postgres, migrations, the
API with autoreload, an hourly mock ingestion loop, and the Next.js dev server.

**Without Docker:**

```bash
git clone <repo-url> weather-app
cd weather-app
make setup                                    # uv sync + npm ci
createdb weather                              # any Postgres 16; adjust DATABASE_URL if needed
make dev-local                                # migrate, ingest, run API (8000) + web (3000)
```

**Tests and checks:**

```bash
createdb weather_test && createdb weather_e2e  # once
make test        # pytest (API + worker) and Vitest
make e2e         # Playwright: real Postgres + API + production Next.js build
make lint typecheck build
```

## Environment variables

All are listed in [`.env.example`](.env.example). Nothing secret is committed.

| Variable | Used by | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | API, worker | SQLAlchemy URL, `postgresql+psycopg://…`. Secret in production. |
| `ENVIRONMENT` | API, worker | `development`, `test` or `production` (production enables secure cookies, hides `/docs`, requires `COOKIE_SECRET`). |
| `FORECAST_PROVIDER` | API, worker | `mock` (default), `gefs` (NOAA GEFS, real data) or `weathernext`. |
| `INGESTION_BACKFILL_RUNS` | API, worker | How many recent model runs are kept filled for every active grid point (default 8). |
| `GRID_POINT_INACTIVE_DAYS` | worker | Unreferenced grid points stop being ingested after this many days (default 14). |
| `GOOGLE_CLOUD_PROJECT` | API, worker | GCP project for BigQuery (WeatherNext). |
| `GOOGLE_APPLICATION_CREDENTIALS` | local only | Service account key path for local WeatherNext work. Cloud Run uses its service account instead. |
| `WEATHERNEXT_BIGQUERY_DATASET` | API, worker | Dataset holding WeatherNext forecasts once access is granted. |
| `GEOCODER_PROVIDER` | API | `nominatim` (development) or `static` (offline list for tests/E2E). |
| `NOMINATIM_URL` | API | Nominatim base URL. |
| `NWS_USER_AGENT` | API | Identifying User-Agent required by NWS and Nominatim. |
| `COOKIE_SECRET` | API | HMAC key that signs the visitor cookie. Secret. |
| `CORS_ALLOWED_ORIGINS` | API | Comma-separated frontend origins allowed to call the API directly. |
| `API_ORIGIN` | web (build) | Where Next.js proxies `/api/v1/*`. Baked in at build time. |
| `NEXT_PUBLIC_API_URL` | web | Browser API base. Leave empty (same origin) so the cookie stays first-party. |

## Deployment

**Web on Vercel.** Import the GitHub repo in Vercel and set *Root Directory* to
`apps/web` (`apps/web/vercel.json` installs from the monorepo root). Set
`API_ORIGIN` to the Cloud Run API URL. Every push to `main` deploys; pull
requests get preview deployments. The browser only ever talks to the Vercel
domain; Next.js rewrites proxy `/api/v1/*` to Cloud Run, which is what keeps the
visitor cookie first-party.

**API and worker on Google Cloud.**

1. Create the database (see [infra/database/README.md](infra/database/README.md)).
2. Run `PROJECT=… REGION=… GITHUB_REPO=owner/weather-app infra/cloud-run/bootstrap.sh` once. It creates the Artifact Registry repo, service accounts, secrets, GitHub Workload Identity Federation and the hourly Cloud Scheduler trigger, then prints the GitHub variables to set.
3. Store the database URL secret and set the variables listed in [infra/github/README.md](infra/github/README.md).
4. Merge to `main`. `.github/workflows/deploy.yml` builds both images, pushes them to Artifact Registry, runs migrations as a Cloud Run Job, deploys the `weather-api` service and updates the `weather-ingest` job.

CI (`.github/workflows/ci.yml`) runs lint, typecheck, tests, the web build, an
API-types drift check, Playwright E2E and Docker builds on every pull request.

## Weather providers

Providers live in `apps/api/src/weather_api/forecast/providers/` and implement
two methods:

```python
class ForecastProvider:
    def latest_initializations(self, count=1, now=None) -> list[datetime]: ...
    def get_forecast(self, grid_points, initialization_time=None) -> dict[UUID, EnsembleForecast]: ...
```

They return raw ensemble members in SI units. Everything else (percentiles,
rain probabilities, daily summaries, confidence) is computed by shared code, so
a provider never touches the database or the API.

* **`mock`**: synthetic 50-member ensemble, 15 days hourly, new run every 12 h.
  Seeded by grid cell and run time, so it is fully deterministic. It models
  climatology, a diurnal cycle, passing weather systems, run-to-run error that
  shrinks as the target approaches, and spread that grows with lead time.
* **`gefs`**: NOAA's 31-member Global Ensemble Forecast System, real data
  until WeatherNext access arrives. It reads the public `noaa-gefs-pds` S3
  bucket (0.5°, every 6 hours, 16 days), downloading only the six fields the
  app needs with ranged requests, and fills 3- and 6-hourly steps in to hourly.
  It needs the `gefs` extra (`eccodes`), which the Docker image installs. A run
  takes about 1.5 minutes to download, and runs show up 6–8 hours after their
  nominal time. Set `INGESTION_BACKFILL_RUNS` low (2 or 3) so a new location
  doesn't wait on eight downloads.
* **`weathernext`**: the interface and configuration are in place;
  the BigQuery queries are TODOs until dataset access lets us inspect the real
  schema (deliberately not guessed). See [docs/weathernext.md](docs/weathernext.md).
  Switching is `FORECAST_PROVIDER=weathernext`; no frontend change is needed.

## Data model: saved location ≠ weather grid point

```
Ben's Home ──────┐
User B's Home ───┼──▶ weather_grid_point (0.25° cell) ──▶ forecast_runs ──▶ hourly/daily forecasts
User C's Home ───┘
```

A **saved location** is private: a person's name for a place and its exact
coordinates, owned by exactly one visitor (later, user). A **weather grid
point** is a cell of the model grid. Each saved location is snapped to its
grid cell, and forecasts are computed and stored **once per grid cell per model
run**, never per user. A thousand people in one town cost the same as one.
Forecast tables have no owner column at all, so user data and forecast data
cannot leak into each other.

Forecast rows are never updated or deleted: each model run is a new set of
rows. That is what powers the forecast-history page and, later, accuracy
tracking against observations.

More detail: [docs/architecture.md](docs/architecture.md) and
[docs/forecast-methodology.md](docs/forecast-methodology.md).
