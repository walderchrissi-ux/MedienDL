# Windows-Build — Anleitung

## Wichtiger Hinweis vorab

Diese Dateien sind **auf macOS geschrieben, aber nicht getestet**. PyInstaller
kompiliert nur für das System, auf dem es läuft — eine Windows-Datei kann auf
dem Mac nicht entstehen. Der Build muss auf einem Windows-Rechner stattfinden.

Ich habe die Windows-spezifischen Stellen (Pfade für Browser-Cookies,
`explorer` zum Öffnen, `.exe`-Binaries, `.ico`-Icon, Batch-Skript) bereits
berücksichtigt — verifizieren kann ich es hier aber nicht.

## Voraussetzungen auf dem Windows-Rechner

**1. Python installieren**
Von https://www.python.org/downloads/ — bei der Installation **„Add Python to
PATH"** anhaken.

**2. ffmpeg installieren** (für MP3 zwingend nötig)
PowerShell als Administrator:
```powershell
winget install Gyan.FFmpeg
```
Danach PowerShell neu öffnen, damit der PATH greift.

Prüfen:
```powershell
ffmpeg -version
ffprobe -version
```

## Bauen

Repository holen und das Skript starten:
```bat
git clone <repo> MedienDL
cd MedienDL
build_windows.bat
```

Das Skript legt das venv an, installiert alles, erzeugt die Icons und baut
danach. Dauert ein paar Minuten.

## Ergebnis

```
dist\MedienDL\MedienDL.exe
```

**Wichtig fürs Verteilen:** Nicht nur die `.exe` verschicken — der ganze Ordner
`dist\MedienDL` gehört zusammen. Darin liegen Python, yt-dlp, ffmpeg und
ffprobe. Am besten den Ordner als ZIP packen.

## Bekannte Stolperstellen

| Problem | Ursache | Lösung |
|---|---|---|
| MP3-Export scheitert | `ffprobe` fehlt | `winget install Gyan.FFmpeg`, prüfen mit `where ffprobe` |
| „python wurde nicht gefunden" | PATH fehlt | Python neu installieren mit „Add to PATH" |
| HTTPS schlägt fehl | Zertifikate | Baut das Skript mit ein; Update auf neueste Version bauen |
| Fenster öffnet sich nicht | Firewall | Windows → Sicherheit → Firewall → App erlauben |

## Chrome-Cookies unter Windows

Funktioniert, liest aus `%LOCALAPPDATA%\Google\Chrome\User Data`. Chrome muss
dafür **nicht** laufen — abgeschlossene Cookie-Dateien genügen.

## Was ich nicht getestet habe

- Der Build selbst (kein Windows-Rechner verfügbar)
- Die Installer-Schritte
- Browser-Erkennung und Datei-öffnen unter Windows

Wenn beim ersten Build etwas klemmt, sag mir die Fehlermeldung — die Ursache
ist dann meist `ffprobe` oder der Python-PATH, beides oben abgedeckt.