# FastAPI service image (Cloud Run). Build from the repository root:
#   docker build -f apps/api/Dockerfile -t weather-api .
FROM python:3.12-slim AS build
RUN pip install --no-cache-dir uv==0.11.32
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Workspace metadata first so dependency layers cache across code changes.
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY workers/forecast-ingestion/pyproject.toml workers/forecast-ingestion/pyproject.toml
RUN mkdir -p apps/api/src/weather_api workers/forecast-ingestion/src/forecast_ingestion \
 && uv sync --frozen --no-dev --no-install-workspace --package weather-api --extra weathernext
COPY apps/api apps/api
# The weathernext extra (BigQuery client) lets the API backfill new grid points.
RUN uv sync --frozen --no-dev --no-editable --package weather-api --extra weathernext

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app/apps/api
COPY --from=build /app/.venv /app/.venv
COPY apps/api/alembic.ini apps/api/alembic.ini
COPY apps/api/migrations apps/api/migrations
WORKDIR /app/apps/api
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PORT=8080
USER app
EXPOSE 8080
# Cloud Run sets $PORT. --proxy-headers so client IPs (rate limiting) come from X-Forwarded-For.
CMD ["sh", "-c", "exec uvicorn weather_api.app:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
