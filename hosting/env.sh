# Sourced by install.sh, start.sh and hourly.sh on invest-server. The server provides PORT,
# APP_DATA_DIR, PGHOST/PGDATABASE/PGUSER (local Postgres, no password) and any keys from
# gs://stock-picker-511413-data/secrets/apps/weather.env.
TOOLS=$HOME/tools
export PATH="$TOOLS/node/bin:$TOOLS/bin:$PATH"
export UV_PYTHON_INSTALL_DIR=$TOOLS/python UV_CACHE_DIR=$TOOLS/uv-cache UV_PYTHON_PREFERENCE=only-managed
export ENVIRONMENT=${ENVIRONMENT:-production}
export DATABASE_URL=${DATABASE_URL:-postgresql+psycopg://$PGUSER@/$PGDATABASE?host=$PGHOST}
export FORECAST_PROVIDER=${FORECAST_PROVIDER:-mock}
export CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS:-https://weather.shadowmountainco.com}
export NWS_USER_AGENT=${NWS_USER_AGENT:-weathernext-personal-weather-app (https://weather.shadowmountainco.com)}
# The visitor-cookie secret is made once on the server and kept with the app's data.
if [ -z "${COOKIE_SECRET:-}" ]; then
  [ -s "$APP_DATA_DIR/cookie_secret" ] || (umask 077; head -c 48 /dev/urandom | base64 -w0 > "$APP_DATA_DIR/cookie_secret")
  export COOKIE_SECRET=$(cat "$APP_DATA_DIR/cookie_secret")
fi
API_PORT=8901   # FastAPI, local only; the Next.js site on $PORT proxies /api/v1 to it
