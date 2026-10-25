#!/bin/bash
# Runs on invest-server as the app user, from the unpacked bundle (see build-bundle.sh).
set -euo pipefail
. hosting/env.sh
mkdir -p "$TOOLS/bin"

fetch() {  # url sha256 dest
  curl -fsSL "$1" -o "$3.part"
  echo "$2  $3.part" | sha256sum -c --quiet && mv "$3.part" "$3"
}
NODE=v22.22.0
if [ "$("$TOOLS/node/bin/node" -v 2>/dev/null)" != "$NODE" ]; then
  fetch https://nodejs.org/dist/$NODE/node-$NODE-linux-x64.tar.xz \
    9aa8e9d2298ab68c600bd6fb86a6c13bce11a4eca1ba9b39d79fa021755d7c37 "$TOOLS/node.tar.xz"
  rm -rf "$TOOLS/node" && mkdir -p "$TOOLS/node" && tar -xJf "$TOOLS/node.tar.xz" -C "$TOOLS/node" --strip-components=1
  rm "$TOOLS/node.tar.xz"
fi
UV=0.11.32
if [ "$("$TOOLS/bin/uv" --version 2>/dev/null | cut -d' ' -f2)" != "$UV" ]; then
  fetch https://github.com/astral-sh/uv/releases/download/$UV/uv-x86_64-unknown-linux-gnu.tar.gz \
    aab924fd522efd06f1c5f3b93a243864fc453132c94b2dc49f1371b528a4b967 "$TOOLS/uv.tar.gz"
  tar -xzf "$TOOLS/uv.tar.gz" -C "$TOOLS/bin" --strip-components=1 && rm "$TOOLS/uv.tar.gz"
fi

# A fresh virtualenv per install, outside the bundle folder (which is renamed after install).
VENV=$HOME/venvs/$(date +%Y%m%d%H%M%S)
mkdir -p "$HOME/venvs"
UV_PROJECT_ENVIRONMENT=$VENV uv sync --frozen --no-dev --no-editable --python 3.12 --package forecast-ingestion
echo "$VENV" > hosting/.venv-path
(cd apps/api && "$VENV/bin/alembic" upgrade head)
# Keep only this virtualenv and the one before it
ls -1d "$HOME"/venvs/* | sort | head -n -2 | xargs -r rm -rf
echo "weather: installed into $VENV"
