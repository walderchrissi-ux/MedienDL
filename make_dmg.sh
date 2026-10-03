#!/usr/bin/env bash
# Erzeugt das fertige DMG zur Verteilung.
set -euo pipefail
cd "$(dirname "$0")"

APP="dist/MedienDL.app"
VERSION="1.1.0"
DMG="dist/MedienDL-${VERSION}.dmg"

[ -d "$APP" ] || { echo "Kein Build gefunden — erst ./build_app.sh"; exit 1; }

# Icon fuer das DMG-Volumen
cp web/icon-512.png /tmp/.volicon.png 2>/dev/null || true

echo "==> Signieren (ad-hoc)"
codesign --force --deep --sign - "$APP" 2>&1 | tail -1

echo "==> DMG bauen"
rm -f "$DMG"
STAGE=$(mktemp -d)
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp INSTALL.md "$STAGE/Lesen Sie zuerst.txt" 2>/dev/null || true

hdiutil create -volname "MedienDL" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"

echo "==> Fertig"
echo "    $DMG  ($(du -h "$DMG" | cut -f1))"
echo
echo "Verteilen: diese DMG-Datei verschicken. Nutzer: Doppelklick,"
echo "App in Programme ziehen, bei Gatekeeper-Meldung rechtsklick → Öffnen."