#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="/app/share/canvasforge"
VENV_BIN="/app/canvasforge-venv/bin/python"
exec "$VENV_BIN" "$APP_ROOT/main.py" "$@"
