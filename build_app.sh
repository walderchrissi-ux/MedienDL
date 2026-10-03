#!/usr/bin/env bash
# Baut MedienDL.app — eine eigenstaendige macOS-App, die jeder
# herunterladen und per Doppelklick starten kann.
#
# Ergebnis: dist/MedienDL.app
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Voraussetzungen"
command -v yt-dlp >/dev/null || { echo "  bitte: brew install yt-dlp ffmpeg"; exit 1; }
command -v ffmpeg >/dev/null || { echo "  bitte: brew install ffmpeg"; exit 1; }

echo "==> Abhaengigkeiten"
./.venv/bin/pip install -q --upgrade pyinstaller yt-dlp fastapi "uvicorn[standard]"

echo "==> Icons"
./.venv/bin/python backend/make_icons.py

echo "==> Build (dauert ein paar Minuten)"
rm -rf build dist
./.venv/bin/pyinstaller --noconfirm --clean MedienDL.spec

echo "==> Fertig: dist/MedienDL.app"
du -sh dist/MedienDL.app
echo
echo "Testen:  open dist/MedienDL.app"
echo "Verteilen: den Ordner 'dist/MedienDL.app' zippen und weitergeben."