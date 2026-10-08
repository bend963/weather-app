#!/usr/bin/env bash
# Deploy one backend component to Cloud Run. Called by .github/workflows/deploy.yml;
# also usable by hand after `gcloud auth login`.
#
#   infra/cloud-run/deploy.sh migrate <image-tag>   run Alembic migrations as a job
#   infra/cloud-run/deploy.sh api     <image-tag>   deploy the FastAPI service
#   infra/cloud-run/deploy.sh worker  <image-tag>   deploy the ingestion job
#
# Required env: PROJECT, REGION, REPO. Optional: WEB_ORIGINS (comma-separated),
# FORECAST_PROVIDER, GEOCODER_PROVIDER, WEATHERNEXT_BIGQUERY_DATASET, NWS_USER_AGENT.
# Secrets (created by bootstrap.sh) are mounted from Secret Manager, never passed here.
set -euo pipefail

target="${1:?usage: deploy.sh migrate|api|worker <tag>}"
tag="${2:?image tag required}"
: "${PROJECT:?}" "${REGION:?}" "${REPO:?}"

registry="$REGION-docker.pkg.dev/$PROJECT/$REPO"
api_sa="weather-api@$PROJECT.iam.gserviceaccount.com"
worker_sa="weather-worker@$PROJECT.iam.gserviceaccount.com"

# "^@^" switches gcloud's list delimiter to "@" so values may contain commas.
env_vars="^@^ENVIRONMENT=production"
env_vars+="@FORECAST_PROVIDER=${FORECAST_PROVIDER:-mock}"
env_vars+="@GEOCODER_PROVIDER=${GEOCODER_PROVIDER:-nominatim}"
env_vars+="@GOOGLE_CLOUD_PROJECT=$PROJECT"
env_vars+="@WEATHERNEXT_BIGQUERY_DATASET=${WEATHERNEXT_BIGQUERY_DATASET:-}"
env_vars+="@NWS_USER_AGENT=${NWS_USER_AGENT:-weathernext-personal-weather-app}"

case "$target" in
  migrate)
    gcloud run jobs deploy weather-migrate \
      --project "$PROJECT" --region "$REGION" \
      --image "$registry/forecast-ingestion:$tag" \
      --args migrate \
      --service-account "$worker_sa" \
      --set-secrets DATABASE_URL=weather-database-url:latest \
      --max-retries 0 --task-timeout 600 \
      --execute-now --wait
    ;;
  api)
    gcloud run deploy weather-api \
      --project "$PROJECT" --region "$REGION" \
      --image "$registry/weather-api:$tag" \
      --service-account "$api_sa" \
      --allow-unauthenticated \
      --set-env-vars "$env_vars@CORS_ALLOWED_ORIGINS=${WEB_ORIGINS:-}" \
      --set-secrets DATABASE_URL=weather-database-url:latest,COOKIE_SECRET=weather-cookie-secret:latest \
      --cpu 1 --memory 512Mi --concurrency 40 \
      --min-instances 0 --max-instances 4 \
      --timeout 60
    ;;
  worker)
    # Mock or WeatherNext ingestion. Triggered hourly by Cloud Scheduler (bootstrap.sh).
    gcloud run jobs deploy weather-ingest \
      --project "$PROJECT" --region "$REGION" \
      --image "$registry/forecast-ingestion:$tag" \
      --args run \
      --service-account "$worker_sa" \
      --set-env-vars "$env_vars" \
      --set-secrets DATABASE_URL=weather-database-url:latest \
      --cpu 1 --memory 2Gi \
      --max-retries 1 --task-timeout 3600
    ;;
  *)
    echo "unknown target: $target" >&2
    exit 2
    ;;
esac
