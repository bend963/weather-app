#!/bin/bash
# Runs the API (local only) and the website together; if either stops, both stop and systemd restarts them.
set -euo pipefail
. hosting/env.sh
VENV=$(cat hosting/.venv-path)
"$VENV/bin/uvicorn" weather_api.app:app --host 127.0.0.1 --port $API_PORT \
  --proxy-headers --forwarded-allow-ips=127.0.0.1 --workers 1 &
cd web
NODE_ENV=production HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1 node apps/web/server.js &
wait -n
exit 1
