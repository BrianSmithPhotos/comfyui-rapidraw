#!/usr/bin/env bash
# Launch ComfyUI for the RapidRAW connector.
#
# --input-directory is the load-bearing part. The connector writes ABSOLUTE
# paths into the workflow's LoadImage nodes, and ComfyUI rejects any path
# outside its input directory (folder_paths.py, is_within_directory). Pointing
# the input directory at the connector's cache root makes those paths legal:
# sources land in cache/sources/ and masks directly in cache/, both inside it.
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] || { echo "No .env - copy .env.example first" >&2; exit 1; }
set -a; . ./.env; set +a

: "${COMFYUI_DIR:?set COMFYUI_DIR in .env}"
: "${CONNECTOR_DIR:?set CONNECTOR_DIR in .env}"

exec "$HOME/.local/bin/uv" --directory "$COMFYUI_DIR" run python main.py \
  --listen "${COMFY_HOST:-127.0.0.1}" \
  --port "${COMFY_PORT:-8188}" \
  --input-directory "$CONNECTOR_DIR/cache"
