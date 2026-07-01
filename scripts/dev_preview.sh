#!/usr/bin/env bash
#
# Fast local preview loop: run Streamlit + a public cloudflared quick tunnel so you can
# check the app on your phone within seconds of an edit (Streamlit auto-reloads on save).
#
#   Usage:   ./scripts/dev_preview.sh          (preferred)
#            bash scripts/dev_preview.sh
#            zsh  scripts/dev_preview.sh        (auto re-execs under bash)
#   Stop:    Ctrl-C                             (tears down Streamlit, the tunnel, caffeinate)
#   Test:    DRY_RUN=1 ./scripts/dev_preview.sh (checks setup, launches nothing)
#
# Open the printed  https://<random>.trycloudflare.com  URL on your phone. The URL changes
# each launch (quick tunnels are ephemeral); for a stable URL set up a named Cloudflare
# tunnel or `tailscale serve` later.
#
# Run inside the env that has streamlit (e.g. `conda activate sandbox`). Requires cloudflared
# — install (Apple Silicon, no Homebrew):
#   curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz \
#     | tar -xz -C "$HOME/.local/bin" && chmod +x "$HOME/.local/bin/cloudflared"

# Re-exec under bash when launched with another shell (zsh/sh) so bash-only syntax works.
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -euo pipefail

# --- locate repo root (this script lives in <root>/scripts) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

PORT="${PORT:-8501}"

if [ ! -f "$ROOT/Cell_Quizz.py" ]; then
  echo "Error: Cell_Quizz.py not found in $ROOT (run this script from the repo's scripts/ dir)." >&2
  exit 1
fi

# --- locate cloudflared (PATH, then ~/.local/bin) ---
if command -v cloudflared >/dev/null 2>&1; then
  CLOUDFLARED="$(command -v cloudflared)"
elif [ -x "$HOME/.local/bin/cloudflared" ]; then
  CLOUDFLARED="$HOME/.local/bin/cloudflared"
else
  echo "cloudflared not found. See the install one-liner in this script's header." >&2
  exit 1
fi

# --- streamlit must be on PATH (activate the right env first) ---
if ! command -v streamlit >/dev/null 2>&1; then
  echo "streamlit not found on PATH. Activate the env that has it, e.g. 'conda activate sandbox'." >&2
  exit 1
fi

if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "dry-run OK — root: $ROOT | port: $PORT | cloudflared: $CLOUDFLARED | streamlit: $(command -v streamlit)"
  exit 0
fi

# --- tear down every child process on exit ---
CAF_PID=""; ST_PID=""; CF_PID=""
cleanup() {
  echo
  echo "Shutting down preview..."
  kill "$CAF_PID" "$ST_PID" "$CF_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# keep the Mac awake while previewing (so the tunnel stays up); harmless if it exits
caffeinate -dis & CAF_PID=$!

echo "Starting Streamlit on http://localhost:$PORT  (auto-reloads on save)"
# CORS/XSRF disabled here ONLY (local tunnel): Streamlit otherwise rejects the cross-origin
# trycloudflare host and the websocket/uploads break. The hosted deploy keeps secure defaults.
streamlit run Cell_Quizz.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.runOnSave true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --browser.gatherUsageStats false & ST_PID=$!

# wait for Streamlit to be ready before tunnelling (clearer than a refused-origin error)
printf "Waiting for Streamlit to come up"
ready=0
for _ in $(seq 1 45); do
  if curl -sf "http://localhost:$PORT/_stcore/health" >/dev/null 2>&1; then
    ready=1; break
  fi
  if ! kill -0 "$ST_PID" 2>/dev/null; then   # Streamlit already died
    break
  fi
  printf "."
  sleep 1
done
printf "\n"
if [ "$ready" != "1" ]; then
  echo "Streamlit did not become ready on port $PORT — check its output above." >&2
  exit 1
fi

echo
echo "Opening public tunnel via cloudflared — open the trycloudflare URL below on your phone:"
echo
"$CLOUDFLARED" tunnel --url "http://localhost:$PORT" & CF_PID=$!

# block until a child exits or Ctrl-C
wait
