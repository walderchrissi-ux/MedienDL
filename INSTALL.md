# MedienDL — Installer-Anleitung (macOS)

## Installation

1. **MedienDL.app** in den **Programme-Ordner** ziehen
   (oder den DMG öffnen und die App dorthin ziehen).
2. **Doppelklicken.** Der Browser öffnet sich automatisch mit der Oberfläche.

Fertig. Die App enthält alles Nötige — kein Python, kein Homebrew,
kein yt-dlp, kein ffmpeg nötig.

## Falls macOS beim ersten Start meckert

macOS blockiert Apps, die nicht aus dem App Store kommen. Beim ersten
Start erscheint evtl.:

> *„MedienDL wurde vom Mac-Privacy-Schutz blockiert."* oder
> *„App kann nicht geöffnet werden, da der Entwickler nicht überprüft
> werden kann."*

**Lösung — eine von drei Möglichkeiten:**

**A) Rechtsklick → Öffnen** (empfohlen)
Rechtsklick auf die App → **Öffnen** → im Dialog nochmal auf **Öffnen**
klicken. Danach startet sie normal.

**B) Systemeinstellungen**
Apple-Menü → **Systemeinstellungen** → **Datenschutz & Sicherheit** →
unter **Sicherheit** auf **„Trotzdem öffnen"** klicken.

**C) Terminal**
```bash
xattr -cr /Applications/MedienDL.app
```

Danach startet die App ohne Meldung.

## Erste Nutzung

1. Link einer Seite einfügen (z. B. YouTube, TikTok, Instagram, Vimeo …)
2. **Analysieren** — zeigt Titel und verfügbare Qualitäten
3. **Nur Audio (MP3)** wählen, wenn du nur den Ton brauchst (viel kleiner!)
4. **Herunterladen** — Fortschritt läuft live mit

Dateien landen in: `Downloads/MedienDL/`

## Handy-Zugriff

1. App starten
2. Handy und Rechner im selben WLAN
3. Im Terminal:
   ```bash
   open http://$(ipconfig getifaddr en0):8765
   ```
   zeigt die Adresse, die du am Handy eingibst.
4. Im Handy-Browser öffnen → **Teilen** → „Zum Home-Bildschirm"

Dann verhält sich die Seite wie eine App. **Achtung:** Solange das läuft,
kann jedes Gerät im WLAN den Downloader bedienen — nur im eigenen
Heimnetz nutzen.

## Wenn etwas nicht klappt

**„YouTube blockiert den Downloader (Bot-Schutz)"**
YouTube erkennt den Downloader. Das ist eine Sperre von YouTube, kein
Fehler der App. Abhilfe: den Download über deinen Browser starten, der
angemeldet ist — oder eine andere Quelle nutzen.

**Video lädt, aber die Datei ist groß**
Bei **Video** lädt die beste Qualität (teils 1–2 GB). Für Musik und
Vlogs **MP3** wählen — das ist um ein Vielfaches kleiner.

**Kein Ton in der MP3-Datei**
Sehr selten. Bitte melden — dann prüfen wir die ffmpeg-Version.

## Systemvoraussetzungen

- macOS 12 oder neuer (Apple Silicon und Intel)
- ca. 400 MB Festplatte
- Internetzugang

## Was die App nicht kann

- Kein Umgehen von Bezahlschranken, DRM oder Altersverifikationen
- Keine privaten oder nur für Mitglieder verfügbaren Videos
- Läuft ausschließlich lokal auf dem eigenen Rechner — die Dateien werden
  nirgendwo hochgeladen

## Eigenes Build erzeugen

```bash
brew install yt-dlp ffmpeg
git clone <repo> && cd MedienDL
./build_app.sh
```

Ergebnis: `dist/MedienDL.app`