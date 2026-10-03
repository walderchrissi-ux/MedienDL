#!/usr/bin/env bash
# MedienDL starten. Ohne Argumente nur lokal (127.0.0.1).
# Mit "start.sh lan" auf 0.0.0.0 (Handy im gleichen WLAN).
set -euo pipefail
cd "$(dirname "$0")"
exec ./.venv/bin/python backend/api.py "$@"
