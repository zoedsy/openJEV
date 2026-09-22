#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export OPENJEV_BACKEND=diffusiongemma
export OPENJEV_DIFFUSION_URL="${OPENJEV_DIFFUSION_URL:-http://127.0.0.1:8008}"
export OPENJEV_DIFFUSION_MAX_TOKENS="${OPENJEV_DIFFUSION_MAX_TOKENS:-8192}"
exec ./run.sh "$@"
