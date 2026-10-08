#!/usr/bin/env bash
# One-time Google Cloud setup for the backend. Safe to re-run; existing
# resources are left alone. Review before running:
#
#   PROJECT=my-project REGION=us-central1 GITHUB_REPO=bend963/weather-app \
#     infra/cloud-run/bootstrap.sh
#
# Creates: Artifact Registry repo, runtime + deploy service accounts, Secret
# Manager secrets, GitHub Workload Identity Federation, and the hourly
# Cloud Scheduler trigger for the ingestion job.
set -euo pipefail

: "${PROJECT:?}" "${REGION:?}" "${GITHUB_REPO:?owner/name}"
REPO="${REPO:-weather}"
gc() { gcloud --project "$PROJECT" "$@"; }
exists() { "$@" >/dev/null 2>&1; }

echo "Enabling APIs…"
gc services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com \
  cloudscheduler.googleapis.com iamcredentials.googleapis.com iam.googleapis.com \
  bigquery.googleapis.com sts.googleapis.com

echo "Artifact Registry…"
exists gc artifacts repositories describe "$REPO" --location "$REGION" ||
  gc artifacts repositories create "$REPO" --location "$REGION" --repository-format docker

echo "Service accounts…"
for sa in weather-api weather-worker github-deployer; do
  exists gc iam service-accounts describe "$sa@$PROJECT.iam.gserviceaccount.com" ||
    gc iam service-accounts create "$sa"
done
api_sa="weather-api@$PROJECT.iam.gserviceaccount.com"
worker_sa="weather-worker@$PROJECT.iam.gserviceaccount.com"
deploy_sa="github-deployer@$PROJECT.iam.gserviceaccount.com"

bind() { gc projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$1" --role "$2" --condition None >/dev/null; }
# Runtime: read secrets; query WeatherNext in BigQuery (API backfills new grid points too).
for sa in "$api_sa" "$worker_sa"; do
  bind "$sa" roles/secretmanager.secretAccessor
  bind "$sa" roles/bigquery.jobUser
done
# Deployer (GitHub Actions): push images, deploy services/jobs, act as runtime accounts.
bind "$deploy_sa" roles/run.admin
bind "$deploy_sa" roles/artifactregistry.writer
for sa in "$api_sa" "$worker_sa"; do
  gc iam service-accounts add-iam-policy-binding "$sa" \
    --member "serviceAccount:$deploy_sa" --role roles/iam.serviceAccountUser >/dev/null
done

echo "Secrets…"
for secret in weather-database-url weather-cookie-secret; do
  if ! exists gc secrets describe "$secret"; then
    gc secrets create "$secret" --replication-policy automatic
    if [[ "$secret" == weather-cookie-secret ]]; then
      openssl rand -base64 48 | tr -d '\n' | gc secrets versions add "$secret" --data-file=-
    else
      echo "  -> add a value: printf '%s' 'postgresql+psycopg://…' | gcloud secrets versions add $secret --data-file=-"
    fi
  fi
done

echo "Workload Identity Federation for GitHub Actions…"
pool=github
exists gc iam workload-identity-pools describe "$pool" --location global ||
  gc iam workload-identity-pools create "$pool" --location global --display-name "GitHub Actions"
exists gc iam workload-identity-pools providers describe github --location global --workload-identity-pool "$pool" ||
  gc iam workload-identity-pools providers create-oidc github \
    --location global --workload-identity-pool "$pool" \
    --issuer-uri https://token.actions.githubusercontent.com \
    --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition "assertion.repository == '$GITHUB_REPO'"
project_number=$(gc projects describe "$PROJECT" --format 'value(projectNumber)')
provider="projects/$project_number/locations/global/workloadIdentityPools/$pool/providers/github"
gc iam service-accounts add-iam-policy-binding "$deploy_sa" \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$project_number/locations/global/workloadIdentityPools/$pool/attribute.repository/$GITHUB_REPO" >/dev/null

echo "Hourly ingestion schedule…"
# The job itself is created by the first deploy; the scheduler just triggers it.
bind "$worker_sa" roles/run.invoker
exists gc scheduler jobs describe weather-ingest-hourly --location "$REGION" ||
  gc scheduler jobs create http weather-ingest-hourly \
    --location "$REGION" --schedule "15 * * * *" --time-zone UTC \
    --uri "https://run.googleapis.com/v2/projects/$PROJECT/locations/$REGION/jobs/weather-ingest:run" \
    --http-method POST --oauth-service-account-email "$worker_sa"

cat <<DONE

Done. Set these GitHub repository variables (Settings → Secrets and variables → Actions → Variables):
  GCP_PROJECT_ID                  $PROJECT
  GCP_REGION                      $REGION
  GCP_ARTIFACT_REPO               $REPO
  GCP_WORKLOAD_IDENTITY_PROVIDER  $provider
  GCP_DEPLOY_SERVICE_ACCOUNT      $deploy_sa
  WEB_ORIGINS                     https://your-app.vercel.app
DONE
