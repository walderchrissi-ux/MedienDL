"""MedienDL core — yt-dlp wrapper: Metadaten auslesen, Jobs bauen, Progress parsen.

Läuft ausschliesslich lokal. Keine Proxys, keine Weiterleitung an Dritte.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _find_ytdlp() -> tuple[list[str], str]:
    """Findet yt-dlp: bevorzugt das mitgelieferte Python-Modul, sonst das
    System-Binary. Gibt (argv-Praefix, Beschreibungslabel) zurueck.

    Das gebuendelte Modul hat den Vorteil, dass die Version exakt zur App
    passt — kein Brew-Pflicht, keine Fremdversion auf dem Rechner.
    """
    try:
        import yt_dlp  # noqa: F401

        return [sys.executable, "-m", "yt_dlp"], "mitgeliefert"
    except ImportError:
        pass
    bin = shutil.which("yt-dlp")
    if bin:
        return [bin], "System"
    return ["yt-dlp"], "nicht gefunden"


def _ytdlp_argv() -> list[str]:
    """argv-Praefix, um yt-dlp als eigenen Prozess zu starten.

    Im PyInstaller-Bundle ist sys.executable die App selbst — ein Aufruf
    von "<app> -m yt_dlp" wuerde die App erneut starten statt yt-dlp.
    Deshalb leitet der Launcher das ueber das Flag --yt-dlp durch.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--yt-dlp"]
    return [sys.executable, "-m", "yt_dlp"]


def _find_ffmpeg() -> str | None:
    """ffmpeg-Pfad: System, dann mitgeliefertes imageio-ffmpeg, dann das
    im App-Bundle abgelegte Binary.

    Reihenfolge wichtig: Ohne Treffer kann die App keinen MP3-Export
    machen, das muss also moeglichst zuverlaessig gefunden werden.
    """
    bin = shutil.which("ffmpeg")
    if bin:
        return bin
    try:
        import imageio_ffmpeg

        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and Path(p).exists():
            return p
    except Exception:
        pass
    # Im PyInstaller-Bundle liegen die Tools als Dateien in _MEIPASS.
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        for cand in (
            meipass / "ffmpeg",
            meipass / "ffmpeg.exe",
            Path(sys.executable).resolve().parent / "ffmpeg",
        ):
            if cand.exists() and cand.is_file():
                return str(cand)
    return None


YTDLP_SOURCE = _find_ytdlp()[1]
FFMPEG = _find_ffmpeg()
YTDLP_ARGV = _ytdlp_argv()
FFMPEG_BUNDLED = bool(FFMPEG) and not shutil.which("ffmpeg")
PROGRESS_PREFIX = "HDP|"
FINAL_PREFIX = "HDFINAL|"

# Browser, aus denen yt-dlp Cookies lesen kann. Feste Liste, damit nichts
# frei durchgereicht wird — yt-dlp wertet die Angabe als Dateipfad.
SUPPORTED_BROWSERS = [
    "chrome", "chromium", "brave", "edge", "firefox",
    "opera", "safari", "vivaldi", "whale",
]


def _cookie_args(browser: str | None, cookie_file: str | None) -> list[str]:
    """yt-dlp-Argumente fuer Cookie-Zugriff.

    Wird nur benutzt, wenn der Nutzer es aktiv einschaltet: YouTube
    blockiert den Downloader sonst als Bot, und mit der Browser-Sitzung
    wird man als angemeldeter Nutzer behandelt.
    """
    out: list[str] = []
    if browser:
        b = str(browser).strip().lower()
        if b in SUPPORTED_BROWSERS:
            out += ["--cookies-from-browser", b]
    if cookie_file:
        p = Path(cookie_file).expanduser()
        if p.is_file():
            out += ["--cookies", str(p)]
    return out

OUT_TEMPLATE = "%(title).150B [%(id)s].%(ext)s"

__version__ = "1.1.0"

# Update-Pruefung: wo laesst sich nach einer neuen Version geschaut werden?
# Leer lassen = automatische Update-Pruefung ist aus.
UPDATE_URL = os.environ.get("MEDIENDL_UPDATE_URL", "").strip()


def _ytdlp_version() -> str | None:
    """Version des yt-dlp, das tatsaechlich genutzt wird."""
    try:
        import yt_dlp

        return yt_dlp.version.__version__
    except Exception:
        return None


class UserError(Exception):
    """Fehler, der dem Nutzer verständlich angezeigt werden darf."""


# ---------------------------------------------------------------- Hilfsfunktionen


def fmt_bytes(n: float | None) -> str:
    if not n or n <= 0:
        return "?"
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB"):
        if n < step:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= step
    return f"{n:.1f} TB"


def fmt_duration(seconds: float | None) -> str:
    if not seconds or seconds <= 0:
        return "?"
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise UserError("Bitte eine URL einfügen.")
    if not re.match(r"^https?://", url, re.I):
        raise UserError("Nur http(s)-URLs sind erlaubt.")
    host = urlparse(url).hostname or ""
    if not host:
        raise UserError("URL konnte nicht gelesen werden.")
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise UserError("Lokale Adressen sind nicht erlaubt.")

    # YouTube-Mix/Radio (list=RD...) ist eine ENDLOSE Playlist — die würde
    # sonst hunderte Videos in voller Qualität laden. Blockieren.
    if re.search(r"[?&]list=RD", url, re.I):
        raise UserError(
            "Das ist ein YouTube-Mix (endlose Radio-Playlist) — der lädt "
            "unbegrenzt viele Videos. Öffne stattdessen das einzelne Video "
            "(auf YouTube: Teilen → Link kopieren) oder nutze eine normale Playlist."
        )
    return url


# ---------------------------------------------------------------- Metadaten


def _synth(v: dict) -> str:
    if not v:
        return ""
    h = v.get("height")
    fps = v.get("fps") or 0
    if h and round(fps) and round(fps) != 30:
        return f"{h}p{int(fps)}"
    return f"{h}p" if h else ""


def _summarize(info: dict) -> dict:
    """Ein einzelnes Video auf das Format bringen, das die UI braucht."""
    formats = []
    for f in info.get("formats") or []:
        if f.get("vcodec") in (None, "none") and f.get("acodec") in (None, "none"):
            continue
        size = f.get("filesize") or f.get("filesize_approx")
        formats.append(
            {
                "id": f.get("format_id"),
                "ext": f.get("ext"),
                "res": _synth(f.get("height") and f or {}),
                "height": f.get("height") or 0,
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec"),
                "size": size,
                "size_label": fmt_bytes(size),
                "tbr": round(f.get("tbr") or 0),
                "note": f.get("format_note") or "",
                "is_video": f.get("vcodec") not in (None, "none"),
                "is_audio": f.get("acodec") not in (None, "none"),
            }
        )
    # Video zuerst, dann nach Qualität absteigend; Audio ans Ende
    formats.sort(key=lambda f: (f["is_video"], f["height"], f["tbr"]), reverse=True)

    total = info.get("duration")
    return {
        "id": info.get("id"),
        "title": info.get("title") or "Ohne Titel",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "duration": total,
        "duration_label": fmt_duration(total),
        "thumbnail": info.get("thumbnail") or "",
        "extractor": info.get("extractor_key") or info.get("extractor") or "",
        "webpage": info.get("webpage_url") or "",
        "formats": formats,
    }


def _entry_row(e: dict) -> dict:
    return {
        "id": e.get("id"),
        "title": e.get("title") or "Ohne Titel",
        "uploader": e.get("uploader") or e.get("channel") or "",
        "duration": e.get("duration"),
        "duration_label": fmt_duration(e.get("duration")),
    }


async def _ytdlp_json(args: list[str]) -> dict:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=90)
    except asyncio.TimeoutError:
        proc.kill()
        raise UserError("Zeitüberschreitung beim Auslesen der Seite (90s).")
    if proc.returncode != 0:
        msg = err.decode("utf-8", "replace").strip()
        raise UserError(_friendly_error(msg))
    try:
        return json.loads(out.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        raise UserError("Antwort der Seite konnte nicht gelesen werden.")


def _clean_error(msg: str) -> str:
    """yt-dlp-Fehler auf eine Zeile für die UI eindampfen."""
    lines = [ln.strip() for ln in (msg or "").splitlines() if ln.strip()]
    noise = re.compile(r"^\s*(\[[^\]]+\]\s*)?(WARNING|DEBUG|ERROR:)?\s*$", re.I)
    for ln in reversed(lines):
        if not noise.match(ln):
            ln = re.sub(r"^ERROR:\s*", "", ln)
            ln = re.sub(r"^\[[^\]]+\]\s*", "", ln)
            return ln[:400]
    return "Unbekannter Fehler"


# YouTube-Bot-Sperre -> verständliche Meldung statt Roh-Fehler.
_BOT_PATTERNS = [
    (r"Sign in to confirm you.?re not a bot", "youtube_bot"),
    (r"Sign in to confirm your age", "youtube_age"),
    (r"This content isn.t available", "youtube_private"),
    (r"members-only|join this channel", "youtube_members"),
]


def _friendly_error(msg: str) -> str:
    for pattern, kind in _BOT_PATTERNS:
        if re.search(pattern, msg, re.I):
            if kind == "youtube_bot":
                return (
                    "YouTube blockiert den Downloader (Bot-Schutz). Das ist eine "
                    "Sperre von YouTube, kein Fehler der App. Abhilfe: einmalig die "
                    "Browser-Cookies freigeben (Cookie-Zugriff einbauen) — dann "
                    "arbeitet die App mit deinem Login. Oder eine andere Quelle nutzen."
                )
            if kind == "youtube_age":
                return (
                    "YouTube verlangt eine Altersverifikation — das umgeht diese App "
                    "bewusst nicht. Bitte nutze ein anderes Video."
                )
            if kind == "youtube_private":
                return "Dieses Video ist nicht öffentlich verfügbar."
            if kind == "youtube_members":
                return (
                    "Dieses Video ist nur für Kanal-Mitglieder (Mitglieder-Only). "
                    "Diese App umgeht keine Bezahlschranken."
                )
    return _clean_error(msg)


async def probe(url: str, cookies_from_browser: str | None = None) -> dict:
    """Metadaten holen; erkennt automatisch Einzelvideo vs. Playlist."""
    url = validate_url(url)
    # Cookie-Argumente auch fuer die Analyse — sonst scheitert die
    # Vorschau am Bot-Schutz, obwohl der Download koennte.
    cargs = _cookie_args(cookies_from_browser, None)

    flat = await _ytdlp_json(
        [*YTDLP_ARGV, "-J", "--flat-playlist", "--no-warnings", "--ignore-config", *cargs, url]
    )

    entries = [e for e in (flat.get("entries") or []) if e]
    if flat.get("_type") == "playlist" or len(entries) > 1:
        return {
            "kind": "playlist",
            "title": flat.get("title") or "Playlist",
            "uploader": flat.get("uploader") or flat.get("channel") or "",
            "count": len(entries),
            "webpage": flat.get("webpage_url") or url,
            "entries": [_entry_row(e) for e in entries],
        }

    full = await _ytdlp_json(
        [*YTDLP_ARGV, "-J", "--no-warnings", "--ignore-config", *cargs, url]
    )
    result = _summarize(full)
    result["kind"] = "video"
    return result


# ---------------------------------------------------------------- Jobs


@dataclass
class Job:
    id: str
    url: str
    title: str
    mode: str
    status: str = "queued"  # queued | running | done | error | cancelled
    message: str = ""
    progress: float = 0.0
    downloaded: int = 0
    total: int = 0
    error: str = ""
    speed: str = ""
    eta: str = ""
    files: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    proc: Any = None
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "mode": self.mode,
            "status": self.status,
            "message": self.message,
            "progress": round(self.progress, 2),
            "downloaded": self.downloaded,
            "total": self.total,
            "downloaded_label": fmt_bytes(self.downloaded),
            "total_label": fmt_bytes(self.total),
            "speed": self.speed,
            "eta": self.eta,
            "error": self.error,
            "files": self.files,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "running": self.status in ("queued", "running"),
        }

    def emit(self) -> None:
        self.queue.put_nowait(self.snapshot())


def build_cmd(
    url: str,
    outdir: Path,
    mode: str = "video",
    fmt: str = "auto",
    audio_quality: str = "320",
    thumbnail: bool = True,
    playlist: bool = False,
    max_items: int = 50,
    cookies_from_browser: str | None = None,
    cookie_file: str | None = None,
) -> list[str]:
    """yt-dlp-Aufruf zusammensetzen. mode: 'video' | 'audio'."""
    cmd = [
        *YTDLP_ARGV,
        "--ignore-config",
        "--newline",
        "--no-warnings",
        "--no-color",
        "-o", str(outdir / OUT_TEMPLATE),
        "--progress-template",
        PROGRESS_PREFIX
        + "%(progress.status)s|%(progress.downloaded_bytes)s|%(progress.total_bytes)s"
        + "|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s",
        # after_move: erst NACH der Umwandlung auswerten — sonst ist
        # %(filepath)s noch nicht gesetzt und liefert "NA".
        "--print",
        "after_move:" + FINAL_PREFIX + "%(filepath)s",
        "--retries", "3",
        "--fragment-retries", "5",
        "--concurrent-fragments", "4",
        "--no-mtime",
        "--yes-playlist" if playlist else "--no-playlist",
    ]

    cmd += _cookie_args(cookies_from_browser, cookie_file)

    # Playlists deckeln: eine 200-Video-Liste darf nicht stillschweigend
    # Gigabytes ziehen. --playlist-items begrenzt die Anzahl.
    if playlist:
        cmd += ["--playlist-items", f"1:{max_items}"]

    if mode == "audio":
        if not FFMPEG:
            raise UserError("ffmpeg fehlt — MP3-Umwandlung ist nicht möglich.")
        cmd += ["-x", "--audio-format", "mp3", "--audio-quality", str(audio_quality)]
    else:
        if fmt in (None, "", "auto"):
            cmd += ["-f", "bv*+ba/b"]
        else:
            cmd += ["-f", f"{fmt}+bestaudio/b"]
        if thumbnail:
            cmd += ["--write-thumbnail", "--convert-thumbnails", "jpg"]

    # Video+Audio zusammenfuehren und Thumbnails erzeugen braucht ffmpeg.
    # Wenn wir es selbst mitbringen, muss yt-dlp den Pfad kennen.
    if FFMPEG and (mode == "audio" or fmt in (None, "", "auto") or thumbnail):
        cmd += ["--ffmpeg-location", str(FFMPEG)]

    cmd.append(url)
    return cmd


def _parse_progress(line: str, job: Job) -> bool:
    """True, wenn die Zeile eine Progress-Zeile war."""
    if not line.startswith(PROGRESS_PREFIX):
        return False
    parts = line[len(PROGRESS_PREFIX):].split("|")
    parts += [""] * (6 - len(parts))
    status, dl, total, est, speed, eta = parts[:6]

    def _int(v: str) -> int:
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return 0

    job.downloaded = _int(dl)
    job.total = _int(total) or _int(est)
    job.speed = fmt_bytes(_int(speed)) + "/s" if _int(speed) else ""
    job.eta = f"{int(_int(eta))}s" if _int(eta) else ""
    if job.total > 0:
        job.progress = min(99.5, job.downloaded / job.total * 100)
    if status == "finished":
        job.progress = 99.5
        job.message = "Wird verarbeitet …"
    return True


async def run_job(job: Job, cmd: list[str]) -> None:
    job.status = "running"
    job.message = "Verbinde …"
    job.emit()

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        job.status, job.message = "error", "yt-dlp wurde nicht gefunden."
        job.finished_at = time.time()
        job.emit()
        return

    job.proc = proc
    last = 0.0
    try:
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if _parse_progress(line, job):
                now = time.time()
                if now - last > 0.2:  # SSE nicht fluten
                    last = now
                    job.emit()
            elif line.startswith(FINAL_PREFIX):
                path = line[len(FINAL_PREFIX):].strip()
                if path:
                    job.files.append(path)
            elif line.startswith("ERROR:"):
                # yt-dlp-Fehler einsammeln, damit die UI den Grund zeigt
                # statt "Verbinde ..." stehen zu lassen.
                err = _friendly_error(re.sub(r"^ERROR:\s*", "", line))
                job.error = err
                job.message = err[:120]
            elif line.startswith("["):
                # "[download] Destination:" / "[ExtractAudio]" / Post-Processing
                m = re.search(r"\]\s*(.+)$", line)
                if m:
                    job.message = m.group(1)[:120]
    except asyncio.CancelledError:
        proc.terminate()
        raise
    finally:
        job.proc = None

    rc = await proc.wait()
    job.finished_at = time.time()

    if job.status == "cancelled":
        job.emit()
        return

    # Nur Pfade, die wirklich auf der Platte liegen, zählen als Erfolg —
    # sonst meldet die App "fertig", obwohl nichts geschrieben wurde.
    job.files = [f for f in job.files if Path(f).exists()]

    if rc == 0 and job.files:
        job.status = "done"
        job.progress = 100.0
        job.message = f"Fertig — {len(job.files)} Datei(en)"
        job.speed, job.eta = "", ""
    else:
        job.status = "error"
        job.progress = 0.0
        job.message = job.error or job.message or "Download fehlgeschlagen."
    job.emit()
