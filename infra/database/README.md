# Database

Standard PostgreSQL 16; no vendor extensions beyond the built-in
`gen_random_uuid()`.

## Recommended: Supabase Postgres

Simplest inexpensive option (free tier for development, managed backups).

1. Create a project and copy the **connection pooler** URI (transaction mode,
   port 6543) for Cloud Run, which scales to zero and opens short-lived
   connections.
2. Convert it to SQLAlchemy form: `postgresql+psycopg://USER:PASSWORD@HOST:6543/postgres?sslmode=require`.
3. Store it: `printf '%s' "$URL" | gcloud secrets versions add weather-database-url --data-file=-`.

Cloud SQL for PostgreSQL works the same way (use the Cloud SQL connector or a
private IP and the same URL format).

## Migrations

Alembic, in `apps/api/migrations`. The schema is defined in
`apps/api/src/weather_api/models.py`.

```bash
make migrate                                          # local
cd apps/api && uv run alembic revision --autogenerate -m "describe change"   # new migration; review it
```

In production, the deploy workflow runs `forecast-ingestion migrate` as the
`weather-migrate` Cloud Run Job before deploying the API.

## Growth

`hourly_forecasts` is the large table: about 361 rows per active grid point per
run (2 runs/day with the mock). It is never updated, which suits time-based
partitioning on `forecast_time` (or `forecast_run_id`) later. Retention can then
drop old partitions once calibration needs are clear.
