#!/usr/bin/env bash
# Launch the RapidRAW AI connector.
#
# HOST defaults to 0.0.0.0 upstream, which offers an unauthenticated image API
# to the whole LAN. RapidRAW runs on this machine, so .env pins loopback.
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] || { echo "No .env - copy .env.example first" >&2; exit 1; }
set -a; . ./.env; set +a

: "${CONNECTOR_DIR:?set CONNECTOR_DIR in .env}"

exec "$HOME/.local/bin/uv" --directory "$CONNECTOR_DIR" run python main.py
