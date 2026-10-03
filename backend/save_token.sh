#!/usr/bin/env bash
# Legt das Token aus der Zwischenablage im macOS-Schluesselbund ab.
# Gibt NIE das Token aus — nur Laenge und Status.
set -uo pipefail

TOKEN="$(pbpaste 2>/dev/null || true)"
LEN="${#TOKEN}"

if [ "$LEN" -lt 20 ]; then
  echo "FEHLER: Zwischenablage enthaelt kein Token (Laenge: $LEN)"
  exit 1
fi

# Plausibilitaetspruefung: GitHub-Token beginnen mit ghp_/github_pat_/ghu_/gho_
case "$TOKEN" in
  ghp_*|github_pat_*|ghu_*|gho_*) echo "Format: erkannt (${TOKEN%%_*}_…, $LEN Zeichen)" ;;
  *) echo "WARNUNG: unbekanntes Format, trotzdem wird gespeichert ($LEN Zeichen)" ;;
esac

# In den Schluesselbund schreiben. -U = bei Vorhandensein ersetzen.
if security add-internet-password \
      -s github.com \
      -a "$USER" \
      -w "$TOKEN" \
      -U >/dev/null 2>&1; then
  echo "Schluesselbund: gespeichert (Host github.com, Nutzer $USER)"
  TOKEN=""
  exit 0
else
  echo "FEHLER: Keychain-Eintrag konnte nicht angelegt werden"
  TOKEN=""
  exit 1
fi