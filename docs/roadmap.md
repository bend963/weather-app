# Roadmap

| Milestone | Status |
| --- | --- |
| 1. Skeleton: monorepo, Next.js, FastAPI, Postgres, Docker, visitor cookie, CI | Done |
| 2. Locations: search, save, delete, default, timezone, grid deduplication | Done |
| 3. Mock weather: provider, ingestion, hourly and daily forecasts | Done |
| 4. Dashboard: current, hourly, daily, rain outlook, confidence, mobile | First version done; polish with real use |
| 5. Google WeatherNext provider | Waiting on access. See `docs/weathernext.md` |
| 6. NOAA/NWS alerts (`NWSProvider`), shown above the forecast | Not started. UI state for "alerts unavailable" exists |
| 7. Forecast evolution | Basic page done (`/weather/[id]/history`); richer charts later |

Later, per the spec: accounts and visitor→user migration, alert rules and
notifications, observation-based current conditions, forecast calibration
against observations, Redis once traffic justifies it.
