# MedienDL — Update-Prüfung einrichten

Die App kann selbst nach einer neuen Version schauen. **Standardmäßig ist das
aus** — ohne Konfiguration kontaktiert die App niemanden und lädt nichts nach.

## Wie es funktioniert

1. Du stellst eine kleine JSON-Datei ins Internet, z. B. bei GitHub Pages:

```json
{
  "version": "1.2.0",
  "notes": "Neuer Video-Modus, schnellere MP3-Umwandlung.",
  "url": "https://deine-domain.de/MedienDL-1.2.0.dmg"
}
```

2. Du setzt die Adresse als Umgebungsvariable beim Start der App:

macOS (in der Konsole):
```bash
MEDIENDL_UPDATE_URL="https://deine-domain.de/version.json" open -a MedienDL
```

Windows:
```
set MEDIENDL_UPDATE_URL=https://deine-domain.de/version.json
MedienDL.exe
```

3. Beim Start prüft die App die Adresse. Ist die Version dort höher, erscheint
   oben ein Hinweis mit Download-Knopf. **Installiert wird nichts automatisch** —
   du entscheidest selbst.

## Warum kein automatischer Download

Ein selbstsigniertes Update ohne Prüfung wäre eine Einladung, Anything zu
installieren. Deshalb: Hinweis statt Automatik, nur `https://`/`http://` als
Download-Adresse erlaubt, und ohne konfigurierte Quelle passiert gar nichts.

## Datei `version.json` ins Repository legen

Liegt sie z. B. hier:
```
https://raw.githubusercontent.com/DEIN-NAME/MedienDL/main/version.json
```
dann ist das die Update-URL.

## Version in der App erhöhen

In `backend/core.py`:
```python
__version__ = "1.1.0"   # <- hier
```
Danach neu bauen: `./build_app.sh && ./make_dmg.sh`

## Ohne Update-Quelle

Bleibt alles wie gehabt — die App läuft normal, prüft aber nichts. Das ist der
Standard und für den reinen Eigenbedarf völlig in Ordnung.