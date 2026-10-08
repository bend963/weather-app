import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run the real stack: Postgres + FastAPI (mock provider,
 * static geocoder) + the Next.js production build.
 *
 * E2E_DATABASE_URL must point at a disposable database; migrations run on start.
 */
const API_PORT = 8001;
const WEB_PORT = 3001;
const databaseUrl = process.env.E2E_DATABASE_URL ?? "postgresql+psycopg://postgres:postgres@localhost:5432/weather_e2e";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
      : undefined,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: `uv run python ../../scripts/reset_db.py && uv run --directory ../api alembic upgrade head && uv run uvicorn weather_api.app:app --port ${API_PORT}`,
      url: `http://localhost:${API_PORT}/health`,
      env: {
        DATABASE_URL: databaseUrl,
        GEOCODER_PROVIDER: "static",
        FORECAST_PROVIDER: "mock",
        INGESTION_BACKFILL_RUNS: "3",
        CORS_ALLOWED_ORIGINS: `http://localhost:${WEB_PORT}`,
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: process.env.E2E_SKIP_BUILD
        ? `npx next start -p ${WEB_PORT}`
        : `npx next build && npx next start -p ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      env: { API_ORIGIN: `http://localhost:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
