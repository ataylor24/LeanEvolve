#!/usr/bin/env bash
# tear_down.sh — stop Kimina Lean Server container and clean env vars
#
# Usage:
#   # run in *current* shell so that `unset` persists
#   source tear_down.sh
#
# This script will:
#   1) stop & remove the kimina-lean-server Docker container (if running)
#   2) unset API-key environment variables previously exported by warm_up_env.sh
# -----------------------------------------------------------------------------
set -uo pipefail

# -----------------------------------------------------------------------------
# 1. Unset environment variables (only persists if script is *sourced*)
# -----------------------------------------------------------------------------
for var in OPENAI_API_KEY INCEPTION_API_KEY DEEPSEEK_API_KEY; do
  if [[ -n "${!var-}" ]]; then
    unset "$var"
    echo "[tear_down] Unset $var"
  fi
done

# -----------------------------------------------------------------------------
# 2. Stop & remove Kimina Lean Server container via docker compose
# -----------------------------------------------------------------------------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
KIMINA_DIR="$( realpath "${SCRIPT_DIR}/../../herald_translator/kimina-lean-server" )"

echo "[tear_down] Checking Docker container in ${KIMINA_DIR}"

if command -v docker >/dev/null 2>&1; then
  pushd "${KIMINA_DIR}" >/dev/null

  if docker compose ps --status running | grep -q "kimina-lean-server"; then
    echo "[tear_down] Stopping kimina-lean-server container…"
    docker compose down
  else
    echo "[tear_down] kimina-lean-server not running. Nothing to stop."
  fi

  popd >/dev/null
else
  echo "[tear_down] Docker not found; skipping container shutdown."
fi

echo "[tear_down] Environment teardown complete."
