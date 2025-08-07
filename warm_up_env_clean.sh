#!/usr/bin/env bash
# warm_up_env.sh — export API keys and ensure Kimina Lean Server is running
#
# This script should be sourced *once* before running experiments. It will:
#   1) export the required API keys
#   2) launch (or reconnect to) a Kimina Lean Server container located in
#      ../../herald_translator/kimina-lean-server relative to this file.
# -----------------------------------------------------------------------------
set -uo pipefail

export OPENAI_API_KEY=
export DEEPSEEK_API_KEY=

export CUDA_VISIBLE_DEVICES=

# -----------------------------------------------------------------------------
# Kimina Lean Server
# -----------------------------------------------------------------------------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
KIMINA_DIR="$( realpath "${SCRIPT_DIR}/../../herald_translator/kimina-lean-server" )"

echo "[warm_up_env] Launching Kimina Lean Server from ${KIMINA_DIR}"

pushd "${KIMINA_DIR}" >/dev/null

# Create .env from template if it doesn't exist yet
if [[ ! -f .env && -f .env.template ]]; then
  cp .env.template .env
  echo "[warm_up_env] .env file created from template."
fi

# Start (or reconnect to) the container in detached mode
if docker compose ps --status running | grep -q "kimina-lean-server"; then
  echo "[warm_up_env] Kimina Lean Server already running."
else
  docker compose up -d
fi

popd >/dev/null

echo "[warm_up_env] Kimina Lean Server is ready at http://localhost"