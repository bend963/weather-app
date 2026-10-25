#!/bin/bash
# Hourly forecast ingestion (the Cloud Run Job in the original design).
set -euo pipefail
. hosting/env.sh
exec "$(cat hosting/.venv-path)/bin/forecast-ingestion" run
