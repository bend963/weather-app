# WeatherNext 3 integration

The provider (`apps/api/src/weather_api/forecast/providers/weathernext.py`)
reads Google DeepMind WeatherNext 3 from BigQuery. Its module docstring has the
details; this page is the setup checklist.

## How the data is read

- Table `weathernext_3_0_0_0p1deg`, linked into your Cloud project by the
  Analytics Hub listing. One row per 0.1° cell per run, partitioned by
  `init_time`, clustered by `geography`, with an hourly `forecast` array.
- Only the 00/06/12/18 UTC runs (15 days, hourly steps) are used. A run is
  picked up once it appears in BigQuery, about 8 h 10 min after its init time.
- The table publishes the mean and 10/25/50/75/90th percentiles across 64
  members, not the members. Each hour's percentiles become 41 "spread paths"
  (`weather_api/forecast/spread_paths.py`) so the usual statistics code runs
  unchanged; hourly percentiles come back exactly, rain keeps its published
  mean. The UI labels these lines as spread, not runs.
- The app grid is 0.1° to match (migration `0002` moved saved locations). Each
  grid node reads the nearest cell centre.
- Each query reads one `init_time` partition, only the needed columns, and the
  cells near the requested nodes. `WEATHERNEXT_MAX_BYTES_BILLED` caps each query.

## Setup checklist

- [ ] Subscribe to the WeatherNext 3 listing in Analytics Hub; note the project
      and the linked dataset's name.
- [ ] Create a service account with BigQuery Job User on the billing project
      and BigQuery Data Viewer on the linked dataset.
- [ ] Set `FORECAST_PROVIDER=weathernext`, `GOOGLE_CLOUD_PROJECT`,
      `WEATHERNEXT_BIGQUERY_DATASET`, and either `WEATHERNEXT_SA_KEY` (the JSON
      key, from a secret store) or Application Default Credentials.
- [ ] Dry-run one forecast query and check the bytes it would read; adjust
      `WEATHERNEXT_MAX_BYTES_BILLED` if needed.
- [ ] Run `forecast-ingestion run` and check one location against the table.

## Terms of use

Real-time WeatherNext data comes under Google's experimental data terms
(https://storage.googleapis.com/weathernext-public/terms-of-use.pdf). In short:
it is not meant for consumer use, may be shared only with known people for
their own internal use, and must carry the disclaimer "This data is intended
for experimental modelling only and is not intended, validated, or approved for
real world use" and the notice "Copyright 2024-6 Google LLC". The web app shows
both whenever the model is WeatherNext. Read the terms before any public
deployment.
