# MedienDL

Lokaler Downloader für Web-Medien — **Video und MP3**. Läuft komplett auf dem
eigenen Rechner, eine Web-Oberfläche die sich auch auf dem Handy als App
installieren lässt (PWA). Kein Konto, keine Cloud, keine Weiterleitung an
Dritte.

## Funktionen

- **Video** in beliebiger verfügbarer Qualität, oder **nur Audio als MP3**
  (320/256/192/128 kbps oder beste VBR)
- Unterstützt alles, was [yt-dlp](https://github.com/yt-dlp/yt-dlp) kann:
  YouTube, TikTok, Instagram, Vimeo, Twitter/X, SoundCloud, u. a.
- **Live-Fortschritt** mit Speed und Restzeit
- **Browser-Anmeldung** optional: umgeht den Bot-Schutz mancher Seiten
- **Playlists** werden erkannt und auf Wunsch komplett geladen (max. 50)
- **Update-Hinweis**, wenn eine neue Version vorliegt
- Als **PWA** auf dem Handy installierbar

## Datenschutz

Läuft ausschließlich lokal. Dateien werden nirgendwo hochgeladen. Keine
Accounts, keine Telemetrie, keine Server im Hintergrund.

## Grenzen (bewusst so gebaut)

- Kein Umgehen von Bezahlschranken, DRM oder Altersverifikation
- Keine privaten oder nur für Mitglieder verfügbaren Videos
- Lade nur Material, das du sehen darfst — eigene Uploads, CC/PD-Inhalte,
  Podcasts. Die Verbreitung fremder Werke ist nicht Sache dieses Tools.

## Installation

### macOS
`dist/MedienDL-1.1.0.dmg` → Doppelklick → App in „Programme" ziehen.
Beim ersten Start: Rechtsklick auf die App → **Öffnen** (nötig, weil die App
nicht mit einem Apple-Zertifikat signiert ist). Details in [INSTALL.md](INSTALL.md).

### Windows
Siehe [FUER-FREUNDE-WINDOWS.md](FUER-FREUNDE-WINDOWS.md).

### Ohne Installer (für Entwickler)
```bash
python3 -m venv .venv
./.venv/bin/pip install yt-dlp certifi imageio-ffmpeg fastapi "uvicorn[standard]"
./start.sh
```
Dann http://127.0.0.1:8765 aufrufen.

## Bauen

**macOS:**
```bash
./build_app.sh && ./make_dmg.sh
```

**Windows** (nur auf einem Windows-Rechner möglich):
```bat
build_windows.bat
```
Oder automatisch über GitHub Actions — siehe
[`.github/workflows/build-windows.yml`](.github/workflows/build-windows.yml).
Der Build läuft dann auf einem Windows-Server und legt das fertige ZIP unter
*Actions → letzter Lauf → Artifacts* ab.

## Benutzung

1. Link einfügen → **Analysieren** (holt Titel, Dauer, verfügbare Qualitäten)
2. Modus wählen: **Video** oder **Nur Audio (MP3)**
3. **Herunterladen** — Fortschritt, Speed und Restzeit laufen live mit
4. Verlauf unten; Klick auf eine Datei öffnet sie im Dateimanager

## Ausgabe

Alle Dateien landen in `Downloads/MedienDL/`.
Umbenennen statt Standard: Umgebungsvariable `MEDIENDL_OUT` setzen.

## Handy-Zugriff

```bash
open http://$(ipconfig getifaddr en0):8765   # macOS, zeigt die Adresse
```
Dann im Handy-Browser öffnen und über *Teilen → Zum Home-Bildschirm*
installieren. **Nur im eigenen Heimnetz nutzen** — im LAN-Modus kann jedes
Gerät den Downloader bedienen.

## Auto-Update

Standardmäßig **aus**. Einrichten in [UPDATES.md](UPDATES.md).

## Projektstruktur

| Datei | Zweck |
|---|---|
| `backend/core.py` | yt-dlp-Anbindung: Metadaten, Befehlsbau, Progress-Parser |
| `backend/api.py` | FastAPI-Server, SSE-Fortschritt, Ausgabe |
| `backend/launcher.py` | App-Einstieg, Browser öffnen, yt-dlp-Durchreichmodus |
| `backend/test_core.py` | Tests (`./.venv/bin/python backend/test_core.py`) |
| `backend/make_icons.py` | erzeugt PWA-Icons und die Windows-`.ico` |
| `web/index.html` | Oberfläche (PWA, kein Build-Schritt) |
| `MedienDL.spec` / `MedienDL_win.spec` | PyInstaller-Konfiguration |

## Tests

```bash
./.venv/bin/python backend/test_core.py
```

## Hinweis zu yt-dlp

yt-dlp wird aktiv gepflegt; bei „Video unavailable" lohnt sich ein Update
(`brew upgrade yt-dlp`). Die mitgelieferte Version ist bereits aktuell.

## Haftungsausschluss

Wird ohne Gewähr bereitgestellt. Für den Download von Inhalten bist du
selbst verantwortlich — achte auf Urheberrecht und die Bedingungen der
jeweiligen Plattform.