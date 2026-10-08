# Forecast ingestion worker image (Cloud Run Job). Build from the repository root:
#   docker build -f workers/forecast-ingestion/Dockerfile -t forecast-ingestion .
FROM python:3.12-slim AS build
RUN pip install --no-cache-dir uv==0.11.32
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY workers/forecast-ingestion/pyproject.toml workers/forecast-ingestion/pyproject.toml
RUN mkdir -p apps/api/src/weather_api workers/forecast-ingestion/src/forecast_ingestion \
 && uv sync --frozen --no-dev --no-install-workspace --package forecast-ingestion
COPY apps/api apps/api
COPY workers/forecast-ingestion workers/forecast-ingestion
RUN uv sync --frozen --no-dev --no-editable --package forecast-ingestion

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
COPY --from=build /app/.venv /app/.venv
# Migrations ship with the worker so `forecast-ingestion migrate` can run as a job.
COPY apps/api/alembic.ini /app/apps/api/alembic.ini
COPY apps/api/migrations /app/apps/api/migrations
WORKDIR /app/apps/api
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
ENTRYPOINT ["forecast-ingestion"]
CMD ["run"]
