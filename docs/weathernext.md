# WeatherNext integration (Milestone 5)

Access to Google DeepMind WeatherNext is pending. Everything except the two
data-access methods is ready.

## What to implement

`apps/api/src/weather_api/forecast/providers/weathernext.py`:

1. `latest_initializations(count)`: newest fully published initialization
   times in the granted dataset.
2. `get_forecast(grid_points, initialization_time)`: for the requested grid
   nodes only, every ensemble member's values for 2 m temperature, 2 m dewpoint,
   10 m u/v wind, precipitation and total cloud cover, returned as
   `EnsembleForecast` arrays shaped `(members, times)` in SI units.
3. `available()`: return `bool(self.project and self.dataset)`.

## Checklist once access is granted

- [ ] Inspect the dataset schema (`bq show --schema`) and document it in the provider module.
- [ ] Confirm grid resolution and longitude convention match `weather_api/grid.py` (0.25°, 0–360). If not, update the grid module and add a migration.
- [ ] Confirm units: Kelvin → °C, metres of water → mm, accumulated vs per-step precipitation.
- [ ] Confirm the native time step. If coarser than hourly, store native steps (the schema allows gaps) or interpolate; document the choice.
- [ ] Confirm the forecast horizon and member count; set `horizon_hours`.
- [ ] Filter queries by init time partition and the requested grid nodes only. Never scan the globe. Check bytes billed with a dry run.
- [ ] Grant the `weather-api` and `weather-worker` service accounts read access to the dataset.
- [ ] Add a recorded-response test (a small fixture of real rows) for the reshaping code.
- [ ] Set `FORECAST_PROVIDER=weathernext` and `WEATHERNEXT_BIGQUERY_DATASET` (GitHub variables) and deploy.

Mock and WeatherNext runs are stored under different `forecast_runs.model`
values, so switching providers never mixes their data, and grid points carry
over unchanged.
