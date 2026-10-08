# Cloud Run

* `bootstrap.sh`: one-time project setup (APIs, Artifact Registry, service
  accounts, secrets, Workload Identity Federation, hourly Scheduler trigger).
* `deploy.sh`: deploys `migrate` (job), `api` (service) or `worker` (job) for an
  image tag. Used by `.github/workflows/deploy.yml`.

Resources:

| Name | Type | Image | Notes |
| --- | --- | --- | --- |
| `weather-api` | service | `weather-api` | public; scales 0–4; secrets `DATABASE_URL`, `COOKIE_SECRET` |
| `weather-ingest` | job | `forecast-ingestion run` | triggered hourly by `weather-ingest-hourly` |
| `weather-migrate` | job | `forecast-ingestion migrate` | executed by each deploy before the API rolls out |

No Kubernetes and no Terraform for v1; the two scripts are the reproducible
record of the infrastructure.
