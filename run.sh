#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  runtime="${OPENJEV_PYTHON:-python3}"
  "$runtime" -c 'import sys; assert sys.version_info >= (3, 10), "OpenJev requires Python 3.10+"'
  "$runtime" -m venv .venv
fi
if [[ ! -x .venv/bin/openjev ]]; then
  .venv/bin/python -m pip install -e .
fi
exec .venv/bin/python -m openjev serve "$@"
