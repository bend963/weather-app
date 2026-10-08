/**
 * Types for the weather API, generated from FastAPI's OpenAPI schema.
 *
 * Regenerate after changing API schemas:  npm run types:generate
 * (CI fails if src/openapi.ts is out of date.)
 */
import type { components, paths } from "./openapi";

export type { components, paths };

type Schemas = components["schemas"];

export type Me = Schemas["Me"];
export type Preferences = Schemas["Preferences"];
export type PreferencesUpdate = Schemas["PreferencesUpdate"];
export type Location = Schemas["Location"];
export type LocationCreate = Schemas["LocationCreate"];
export type LocationUpdate = Schemas["LocationUpdate"];
export type Place = Schemas["Place"];
export type Forecast = Schemas["Forecast"];
export type ForecastStatus = Forecast["status"];
export type Units = Schemas["Units"];
export type ModelRun = Schemas["ModelRun"];
export type CurrentConditions = Schemas["CurrentConditions"];
export type HourlyForecast = Schemas["HourlyForecast"];
export type DailyForecast = Schemas["DailyForecast"];
export type DayConfidence = Schemas["DayConfidence"];
export type Confidence = Schemas["Confidence"];
export type Condition = Schemas["Condition"];
export type RainOutlook = Schemas["RainOutlook"];
export type RainWindow = Schemas["RainWindow"];
export type Range = Schemas["Range"];
export type Spread = Schemas["Spread"];
export type ForecastHistory = Schemas["ForecastHistory"];
export type HistoryEntry = Schemas["HistoryEntry"];
export type HistoryValue = Schemas["HistoryValue"];

export interface ApiErrorBody {
  error: { code: string; message: string; request_id?: string | null };
}
