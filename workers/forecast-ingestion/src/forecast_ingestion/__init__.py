"""Cloud Run Job entrypoint for forecast ingestion.

The ingestion logic itself lives in weather_api.forecast.ingestion so the API
can reuse it to backfill a newly saved location immediately.
"""
