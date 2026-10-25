# Hosting on invest-server

The app runs on Ben's Google Cloud server next to the research site, at
https://weather.shadowmountainco.com (public). The server side is in bend963/stock-picker
(`deploy/gcp/apps.sh`, `docs/multi-app-hosting.md`).

On the server: a local Postgres database, the FastAPI service on 127.0.0.1:8901, the
Next.js site on `$PORT` (8801, behind the HTTPS load balancer), and `forecast-ingestion run` every hour.
Memory cap 768 MB for the site and API together.

| File | Purpose |
|---|---|
| `build-bundle.sh` | Builds the deploy tarball (the website is prebuilt off the server) |
| `install.sh` | On the server: fetches Node 22 and uv (checksums pinned), builds the Python env, runs migrations |
| `start.sh` | Starts the API and the site |
| `hourly.sh` | Hourly ingestion |
| `env.sh` | Production settings; makes the cookie secret once |
| `runtime`, `needs`, `memory`, `health_path` | Read by the server installer |

Keys (names only; values go in `gs://stock-picker-511413-data/secrets/apps/weather.env`):

- none needed today (mock forecasts).
- For WeatherNext later: `FORECAST_PROVIDER=weathernext`, `GOOGLE_CLOUD_PROJECT`,
  `WEATHERNEXT_BIGQUERY_DATASET`, and BigQuery read access for the server's service account.
