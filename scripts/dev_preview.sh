#!/usr/bin/env bash
#
# Fast local preview: the Python API (uvicorn, auto-reload) + Next.js dev server
# + a public cloudflared quick tunnel so you can check the app on a phone.
#
#   Usage:   ./scripts/dev_preview.sh           (Ctrl-C tears everything down)
#            DRY_RUN=1 ./scripts/dev_preview.sh (checks the setup, launches nothing)
#            NO_TUNNEL=1 ./scripts/dev_preview.sh (local only)
#
# Reads .env.local (APP_PASSWORD, AUTH_SECRET, ENGINE_API_KEY, ENGINE_URL,
# TURSO_*). The API key given to the Python side is ENGINE_API_KEY. Requires
# node on PATH (or ~/.local/node/bin), uv, and cloudflared for the tunnel:
#   curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz \
#     | tar -xz -C "$HOME/.local/bin" && chmod +x "$HOME/.local/bin/cloudflared"

if [ -z "${BASH_VERSION:-}" ]; then exec bash "$0" "$@"; fi
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
export PATH="$HOME/.local/node/bin:$HOME/.local/bin:$PATH"

WEB_PORT="${PORT:-3000}"
API_PORT="${API_PORT:-8000}"

[ -f .env.local ] || { echo "No .env.local — copy .env.example and fill it in." >&2; exit 1; }
set -a; # shellcheck disable=SC1091
source .env.local; set +a
export BEBOP_API_KEY="${ENGINE_API_KEY:-}"
export BEBOP_ALLOWED_ORIGINS="http://localhost:$WEB_PORT"
[ -n "$BEBOP_API_KEY" ] || export BEBOP_DEV=1
export ENGINE_URL="${ENGINE_URL:-http://127.0.0.1:$API_PORT}"

command -v node >/dev/null || { echo "node not found (install Node 24 under ~/.local/node)" >&2; exit 1; }
command -v uv >/dev/null || { echo "uv not found" >&2; exit 1; }
CLOUDFLARED="$(command -v cloudflared || true)"
if [ -z "$CLOUDFLARED" ] && [ -z "${NO_TUNNEL:-}" ]; then
  echo "cloudflared not found — set NO_TUNNEL=1 for a local-only preview." >&2; exit 1
fi
if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "dry-run OK — root: $ROOT | web :$WEB_PORT | api :$API_PORT | node $(node --version) | tunnel: ${CLOUDFLARED:-none}"
  exit 0
fi

PIDS=()
cleanup() { echo; echo "Shutting down preview..."; kill "${PIDS[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

caffeinate -dis & PIDS+=($!)
echo "Starting the Python API on :$API_PORT (auto-reload)"
uv run uvicorn api.index:app --port "$API_PORT" --reload & PIDS+=($!)
echo "Starting Next.js dev on :$WEB_PORT"
npx next dev -p "$WEB_PORT" & PIDS+=($!)

printf "Waiting for the app"
for _ in $(seq 1 60); do
  curl -sf "http://localhost:$WEB_PORT/login" >/dev/null 2>&1 && break
  printf "."; sleep 1
done
echo
if [ -z "${NO_TUNNEL:-}" ]; then
  echo "Opening the public tunnel — open the trycloudflare URL below on your phone:"
  "$CLOUDFLARED" tunnel --url "http://localhost:$WEB_PORT" & PIDS+=($!)
fi
wait
