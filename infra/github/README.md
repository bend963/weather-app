# GitHub configuration

## Actions variables (Settings → Secrets and variables → Actions → Variables)

Printed by `infra/cloud-run/bootstrap.sh`:

| Variable | Example |
| --- | --- |
| `GCP_PROJECT_ID` | `weather-prod-123` |
| `GCP_REGION` | `us-central1` |
| `GCP_ARTIFACT_REPO` | `weather` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/123/locations/global/workloadIdentityPools/github/providers/github` |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | `github-deployer@weather-prod-123.iam.gserviceaccount.com` |
| `WEB_ORIGINS` | `https://weather.example.com,https://weather-app.vercel.app` |
| `FORECAST_PROVIDER` | `mock` until WeatherNext is wired, then `weathernext` |
| `WEATHERNEXT_BIGQUERY_DATASET` | dataset id once granted |
| `NWS_USER_AGENT` | `weather-app (you@example.com)` |

No secrets are stored in GitHub: deployment authenticates with Workload
Identity Federation, and runtime secrets live in Secret Manager. The deploy job
is skipped until `GCP_PROJECT_ID` is set, so CI works on a fresh fork.

## Branch protection (recommended)

Require the `CI` workflow's checks on `main`.

## Vercel

Connect the repository in Vercel with root directory `apps/web` and set
`API_ORIGIN` (Production and Preview) to the Cloud Run URL of `weather-api`.
