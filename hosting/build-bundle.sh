#!/bin/bash
# Builds the tarball invest-server installs (gs://stock-picker-511413-data/deploy/apps/weather/code.tar.gz).
# Run from the repo root on a machine with Node 22: the website is built here so the small server
# does not have to. Usage: bash hosting/build-bundle.sh [out.tar.gz]
set -euo pipefail
OUT=${1:-code.tar.gz}
B=$(mktemp -d)
npm ci
API_ORIGIN=http://127.0.0.1:8901 NEXT_OUTPUT=standalone NEXT_TELEMETRY_DISABLED=1 npm run build -w @weather/web
mkdir -p "$B/web" "$B/apps"
cp -a apps/web/.next/standalone/. "$B/web/"
mkdir -p "$B/web/apps/web/.next" && cp -a apps/web/.next/static "$B/web/apps/web/.next/static"
[ -d apps/web/public ] && cp -a apps/web/public "$B/web/apps/web/public"
cp -a pyproject.toml uv.lock hosting "$B/"
rm -f "$B/hosting/.venv-path"
mkdir -p "$B/workers" && cp -a workers/forecast-ingestion "$B/workers/"
cp -a apps/api "$B/apps/"
rm -rf "$B/apps/api/tests" "$B/workers/forecast-ingestion/tests"
find "$B" -name __pycache__ -prune -exec rm -rf {} +
git rev-parse HEAD > "$B/hosting/COMMIT"
tar -czf "$OUT" -C "$B" .
rm -rf "$B"
echo "built $OUT ($(du -h "$OUT" | cut -f1)) from $(git rev-parse --short HEAD)"
